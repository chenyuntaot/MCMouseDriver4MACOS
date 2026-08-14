"""macOS 菜单栏应用（M2，FR-5）：托盘图标 + Qt 弹层 + 设置面板。

注意（kb/0008）：macOS 27 上 QSystemTrayIcon 的原生菜单点击必崩
（QTBUG-147449，Qt ≤6.12 未修），因此不用 NSMenu，托盘点击改为
弹出自绘 Qt 弹层（纯 QWidget，不经 NSMenu）。设备操作全部在工作线程。
"""

from __future__ import annotations

import ctypes
import queue
import sys
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QCursor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .devices import DeviceVariant
from .panel import Panel
from .profiles import save_profile
from .protocol.old import RATE_TABLES, MouseConfig
from .session import OldProtocolSession
from .transport import HidInterface, pick_config_interface
from .ui import (
    POPOVER_WIDTH,
    POPUP_SHADOW,
    BatteryView,
    Hairline,
    apply_macos_app,
    caption,
    format_hz,
    make_tray_icon,
    menu_row,
    paint_popover,
    pill_button,
    popup_stylesheet,
    style_label,
)

if TYPE_CHECKING:
    from collections.abc import Callable

ROLE_NAMES = {"wired": "有线", "receiver-1k": "2.4G（1K）", "receiver-8k": "2.4G（8K）"}


@dataclass
class DeviceSnapshot:
    """一次设备状态抓取（config 为 None 表示鼠标休眠）。"""

    variant: DeviceVariant
    firmware: str
    battery: int
    charge_status: int
    config: MouseConfig | None


class DeviceWorker(QThread):
    """HID 操作工作线程：串行处理任务，产出状态快照。"""

    snapshot_ready = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._tasks: queue.Queue[tuple] = queue.Queue()
        self._iface: HidInterface | None = None

    def submit(self, *task: object) -> None:
        self._tasks.put(task)

    def stop(self) -> None:
        self._tasks.put(("stop",))

    def run(self) -> None:
        session: OldProtocolSession | None = None
        while True:
            task = self._tasks.get()
            if task[0] == "stop":
                break
            try:
                if session is None:
                    session, self._iface = self._open()
                snapshot = self._handle(task, session)
                if snapshot is not None:
                    self.snapshot_ready.emit(snapshot)
            except Exception as exc:  # noqa: BLE001 - 工作线程兜底，失败即重建会话
                if session is not None:
                    try:
                        session.close()
                    except Exception:  # noqa: BLE001
                        pass
                session = None
                self.failed.emit(str(exc))
        if session is not None:
            session.close()

    def _open(self) -> tuple[OldProtocolSession, HidInterface]:
        iface = pick_config_interface()
        if iface is None or iface.variant is None:
            raise RuntimeError("未发现迈从设备，请连接鼠标")
        if iface.variant.protocol != "old":
            raise RuntimeError(f"{iface.variant.model} 使用新协议（kb/0004），暂不支持")
        return OldProtocolSession.open(iface), iface

    def _snapshot(self, session: OldProtocolSession) -> DeviceSnapshot:
        assert self._iface is not None and self._iface.variant is not None
        firmware = session.read_firmware()
        info = session.read_device_info()
        cfg = session.read_config()
        return DeviceSnapshot(
            self._iface.variant,
            firmware,
            info.battery_level,
            info.charge_status,
            cfg if cfg.dpi_count > 0 else None,  # 全零=休眠（kb/0007 §3）
        )

    def _handle(
        self, task: tuple, session: OldProtocolSession
    ) -> DeviceSnapshot | None:
        """执行任务；写任务完成后回读快照。"""
        assert self._iface is not None and self._iface.variant is not None
        wired = self._iface.variant.role == "wired"
        kind = task[0]
        if kind == "refresh":
            pass
        elif kind == "dpi_stage":
            cfg = session.read_config()
            session.write_dpi(
                replace(cfg, usb_dpi_index=task[1], g_dpi_index=task[1]), wired
            )
        elif kind == "dpi_table":  # (dpis, count, index)
            dpis, count, index = task[1], task[2], task[3]
            cfg = session.read_config()
            session.write_dpi(
                replace(
                    cfg,
                    dpis=dpis,
                    dpi_count=count,
                    dpi_vals=dpis,
                    usb_dpi_index=index,
                    g_dpi_index=index,
                ),
                wired,
            )
        elif kind == "rate":
            session.write_rate(task[1], wired)
        elif kind == "sensor":  # dict of changes
            session.write_sensor(session.read_config(), **task[1])
        elif kind == "sleep":
            session.write_sleep(task[1])
        elif kind == "debounce":
            session.write_debounce(task[1])
        elif kind == "button":
            session.write_button(task[1], task[2], task[3])
        elif kind == "macro":  # (index, events_logical, condition, name)
            session.write_button(task[1], 4, 0)  # 先绑（0x52 清槽，kb/0007 §7）
            session.write_macro(task[1], task[2], task[3], task[4])
        elif kind == "apply_config":  # 导入的整份配置（0x57 全量写）
            from .protocol.old import build_write_config

            report_id, payload = build_write_config(task[1])
            session.send_write(report_id, payload)
        elif kind == "save_profile":
            save_profile(task[1], session.read_config())
            return None
        else:
            raise ValueError(f"未知任务: {kind}")
        return self._snapshot(session)


def _set_accessory_policy() -> None:
    """把进程切成 accessory（无 Dock 图标）。仅 macOS；打包后由 Info.plist 兜底。"""
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls = objc.objc_getClass(b"NSApplication")
        nsapp = objc.objc_msgSend(cls, objc.sel_registerName(b"sharedApplication"))
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        objc.objc_msgSend(nsapp, objc.sel_registerName(b"setActivationPolicy:"), 1)
    except Exception:  # noqa: BLE001 - 失败则保持普通模式，不影响功能
        pass


class TrayPopup(QWidget):
    """托盘弹层（替代 NSMenu，kb/0008）：状态 + DPI/回报率快捷切换。"""

    def __init__(
        self, submit: Callable[..., None], on_panel: Callable[[], None]
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(POPOVER_WIDTH + POPUP_SHADOW * 2)
        self._submit = submit
        self._apply_style()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._apply_style()
        )
        pad = POPUP_SHADOW + 14
        layout = QVBoxLayout(self)
        layout.setContentsMargins(pad, pad - 2, pad, pad)
        layout.setSpacing(8)

        head = QVBoxLayout()
        head.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 2, 0)
        self._title = style_label(
            QLabel("MCMouseDriver"), size=13, weight=QFont.Weight.DemiBold
        )
        self._title.setWordWrap(True)
        title_row.addWidget(self._title, 1)
        self._battery = BatteryView()
        self._battery.hide()
        title_row.addWidget(self._battery, 0, Qt.AlignmentFlag.AlignTop)
        head.addLayout(title_row)
        self._info = caption("")
        self._info.setContentsMargins(2, 0, 2, 0)
        head.addWidget(self._info)
        layout.addLayout(head)

        self._dpi_label = caption("DPI")
        layout.addWidget(self._dpi_label)
        self._dpi_grid = QGridLayout()
        self._dpi_grid.setSpacing(4)
        self._dpi_group = QButtonGroup(self)
        self._dpi_group.setExclusive(True)
        layout.addLayout(self._dpi_grid)

        self._rate_label = caption("回报率")
        layout.addWidget(self._rate_label)
        self._rate_grid = QGridLayout()
        self._rate_grid.setSpacing(4)
        self._rate_group = QButtonGroup(self)
        self._rate_group.setExclusive(True)
        layout.addLayout(self._rate_grid)

        layout.addWidget(Hairline())

        for text, fn in (
            ("设置…", on_panel),
            ("刷新", lambda: submit("refresh")),
            ("退出", QApplication.instance().quit),
        ):
            btn = menu_row(text)
            btn.clicked.connect(fn)
            layout.addWidget(btn)

    def _apply_style(self) -> None:
        self.setStyleSheet(popup_stylesheet())
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        paint_popover(self, painter)

    def _fill_grid(
        self,
        grid: QGridLayout,
        group: QButtonGroup,
        items: list[str],
        current: int,
        on_pick: Callable[[int], None],
        columns: int,
    ) -> None:
        for btn in group.buttons():
            group.removeButton(btn)
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        cols = max(columns, 1)
        for i, text in enumerate(items):
            btn = pill_button(text, i == current)
            group.addButton(btn, i)
            btn.clicked.connect(lambda _=False, i=i: on_pick(i))
            grid.addWidget(btn, i // cols, i % cols)

    def _clear_pills(self) -> None:
        self._fill_grid(self._dpi_grid, self._dpi_group, [], -1, lambda i: None, 3)
        self._fill_grid(self._rate_grid, self._rate_group, [], -1, lambda i: None, 4)

    def show_error(self, message: str) -> None:
        self._title.setText("未连接")
        self._info.setText(message)
        self._battery.hide()
        self._clear_pills()
        self._dpi_label.hide()
        self._rate_label.hide()
        self.adjustSize()

    def update_snapshot(self, snap: DeviceSnapshot | None) -> None:
        """按快照刷新弹层内容。"""
        if snap is None:
            self._title.setText("正在读取设备…")
            self._info.setText("请用有线或 2.4G 接收器连接鼠标")
            self._battery.hide()
            self._dpi_label.hide()
            self._rate_label.hide()
            self._clear_pills()
            self.adjustSize()
            return
        role = ROLE_NAMES.get(snap.variant.role, snap.variant.role)
        self._title.setText(snap.variant.model)
        self._info.setText(f"{role} · 固件 {snap.firmware}")
        self._battery.set_battery(snap.battery, bool(snap.charge_status))
        self._battery.show()
        cfg = snap.config
        wired = snap.variant.role == "wired"
        if cfg is None:
            self._info.setText(f"{role} · 鼠标休眠，晃动后刷新")
            self._dpi_label.hide()
            self._rate_label.hide()
            self._clear_pills()
            self.adjustSize()
            return
        self._dpi_label.show()
        self._rate_label.show()
        dpi_cur = cfg.usb_dpi_index if wired else cfg.g_dpi_index
        dpi_items = [f"{cfg.dpis[i]}" for i in range(cfg.dpi_count)]
        self._fill_grid(
            self._dpi_grid,
            self._dpi_group,
            dpi_items,
            dpi_cur,
            lambda i: self._submit("dpi_stage", i),
            3 if len(dpi_items) > 3 else max(len(dpi_items), 1),
        )
        rates = RATE_TABLES[snap.variant.rate_table]
        rate_cur = cfg.usb_rate_index if wired else cfg.g_rate_index
        self._fill_grid(
            self._rate_grid,
            self._rate_group,
            [format_hz(hz) for hz in rates],
            rate_cur,
            lambda i: self._submit("rate", i),
            4 if len(rates) >= 7 else 3,
        )
        self.adjustSize()


class TrayApp(QObject):
    """托盘应用：图标 + 弹层 + 设置面板入口。"""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._snapshot: DeviceSnapshot | None = None
        self._panel: Panel | None = None

        self._worker = DeviceWorker()
        self._worker.snapshot_ready.connect(self._on_snapshot)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

        self._popup = TrayPopup(self._worker.submit, self.show_panel)
        self._popup.update_snapshot(None)

        self._tray = QSystemTrayIcon(make_tray_icon(), app)
        self._tray.setToolTip("A7")
        # 不设原生菜单（kb/0008：macOS 27 点击即崩），点击改弹 Qt 弹层
        self._tray.activated.connect(self._on_activated)
        self._tray.show()
        self.refresh()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason not in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            return
        if self._popup.isVisible():
            self._popup.hide()
            return
        self.refresh()
        self._popup.adjustSize()
        rect = self._tray.geometry()
        if not rect.isValid() or rect.isEmpty():
            pos = QCursor.pos()
            x = pos.x() - self._popup.width() // 2
            y = pos.y() + 6
        else:
            x = rect.x() + rect.width() // 2 - self._popup.width() // 2
            y = rect.bottom() - POPUP_SHADOW + 6
        self._popup.move(max(x, 8), y)
        self._popup.show()
        self._popup.raise_()

    def refresh(self) -> None:
        self._worker.submit("refresh")

    def _on_snapshot(self, snap: DeviceSnapshot) -> None:
        self._snapshot = snap
        self._popup.update_snapshot(snap)
        if self._panel is not None:
            self._panel.on_snapshot(snap)

    def _on_failed(self, message: str) -> None:
        self._popup.show_error(message)
        if self._panel is not None:
            self._panel.show_error(message)

    def show_panel(self) -> None:
        self._popup.hide()
        if self._panel is None:
            self._panel = Panel(self._worker.submit)
            if self._snapshot is not None:
                self._panel.on_snapshot(self._snapshot)
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def quit(self) -> None:
        self._worker.stop()
        self._worker.wait(3000)
        self._app.quit()


def run() -> int:
    """菜单栏应用入口。"""
    _set_accessory_policy()
    app = QApplication(sys.argv)
    app.setApplicationName("MCMouseDriver")
    app.setQuitOnLastWindowClosed(False)
    apply_macos_app(app)
    tray = TrayApp(app)
    app.aboutToQuit.connect(tray.quit)
    return app.exec()
