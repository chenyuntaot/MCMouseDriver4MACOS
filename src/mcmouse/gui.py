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
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from .devices import DeviceVariant
from .panel import Panel
from .profiles import save_profile
from .protocol.old import RATE_TABLES, MouseConfig
from .session import OldProtocolSession
from .transport import HidInterface, pick_config_interface

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


def _make_icon() -> QIcon:
    """程序化生成菜单栏图标（模板图，自动适配深浅菜单栏）。"""
    pix = QPixmap(22, 22)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setPen(Qt.GlobalColor.black)
    font = painter.font()
    font.setPixelSize(13)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "A7")
    painter.end()
    icon = QIcon(pix)
    icon.setIsMask(True)
    return icon


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


class TrayPopup(QFrame):
    """托盘弹层（替代 NSMenu，kb/0008）：状态 + DPI/回报率快捷切换。"""

    def __init__(
        self, submit: Callable[..., None], on_panel: Callable[[], None]
    ) -> None:
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._submit = submit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        self._title = QLabel("MCMouseDriver")
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)
        layout.addWidget(self._title)
        self._info = QLabel("")
        layout.addWidget(self._info)

        layout.addWidget(QLabel("DPI 档位"))
        self._dpi_row = QHBoxLayout()
        layout.addLayout(self._dpi_row)
        layout.addWidget(QLabel("回报率"))
        self._rate_row = QHBoxLayout()
        layout.addLayout(self._rate_row)

        actions = QHBoxLayout()
        for text, fn in (
            ("设置面板…", on_panel),
            ("刷新", lambda: submit("refresh")),
            ("退出", QApplication.instance().quit),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(fn)
            actions.addWidget(btn)
        layout.addLayout(actions)

    def _fill_row(
        self,
        row: QHBoxLayout,
        items: list[str],
        current: int,
        on_pick: Callable[[int], None],
    ) -> None:
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, text in enumerate(items):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setChecked(i == current)
            btn.clicked.connect(lambda _=False, i=i: on_pick(i))
            row.addWidget(btn)

    def update_snapshot(self, snap: DeviceSnapshot | None) -> None:
        """按快照刷新弹层内容。"""
        if snap is None:
            self._title.setText("读取设备中…")
            self._info.setText("")
            self._fill_row(self._dpi_row, [], -1, lambda i: None)
            self._fill_row(self._rate_row, [], -1, lambda i: None)
            return
        role = ROLE_NAMES.get(snap.variant.role, snap.variant.role)
        self._title.setText(f"{snap.variant.model}（{role}）")
        charge = " · 充电中" if snap.charge_status else ""
        self._info.setText(f"固件 {snap.firmware} · 电量 {snap.battery}%{charge}")
        cfg = snap.config
        wired = snap.variant.role == "wired"
        if cfg is None:
            self._fill_row(self._dpi_row, ["休眠/未连接"], -1, lambda i: None)
            self._fill_row(self._rate_row, [], -1, lambda i: None)
            return
        dpi_cur = cfg.usb_dpi_index if wired else cfg.g_dpi_index
        self._fill_row(
            self._dpi_row,
            [f"{cfg.dpis[i]}" for i in range(cfg.dpi_count)],
            dpi_cur,
            lambda i: self._submit("dpi_stage", i),
        )
        rates = RATE_TABLES[snap.variant.rate_table]
        rate_cur = cfg.usb_rate_index if wired else cfg.g_rate_index
        self._fill_row(
            self._rate_row,
            [f"{hz}" for hz in rates],
            rate_cur,
            lambda i: self._submit("rate", i),
        )


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

        self._tray = QSystemTrayIcon(_make_icon(), app)
        self._tray.setToolTip("MCMouseDriver")
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
        rect = self._tray.geometry()
        self._popup.adjustSize()
        x = rect.x() + rect.width() // 2 - self._popup.width() // 2
        self._popup.move(max(x, 8), rect.bottom() + 4)
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
        if self._snapshot is None:
            self._popup.update_snapshot(None)
        if self._panel is not None:
            self._panel.statusBar().showMessage(message, 5000)

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
    tray = TrayApp(app)
    app.aboutToQuit.connect(tray.quit)
    return app.exec()
