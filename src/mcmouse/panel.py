"""设置面板（M2，FR-2/3/5/6）：系统设置风侧栏 + 分组卡片。

只组装任务交给 gui.DeviceWorker 执行；状态通过 on_snapshot 回灌。
控件尽量用 Cocoa 原生样式；用户改动即时下发（DPI 表除外，多字段需一次提交）。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import profiles
from .devices import MODEL_CAPS
from .protocol.buttons import (
    BUTTON_NAMES,
    BUTTON_PRESETS,
    HID_USAGE_NAMES,
    describe_button,
)
from .protocol.macros import TRIGGER_MODES, parse_events_dsl
from .protocol.old import (
    RATE_TABLES,
    MouseConfig,
    sensor_game_mode,
    sensor_line,
    sensor_lod,
    sensor_motion_sync,
    sensor_ripple,
)
from .ui import (
    Card,
    Hairline,
    HeaderBar,
    NavList,
    caption,
    footer_row,
    labeled_row,
    page_column,
    section_title,
    wrap_scroll,
)

Submit = Callable[..., None]

_KEY_TOKENS: dict[str, int] = {v.lower(): k for k, v in HID_USAGE_NAMES.items()}
_KEY_TOKENS.update({"up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4F})

PRESET_LABELS: dict[str, str] = {
    "default": "默认",
    "left": "左键",
    "right": "右键",
    "middle": "中键",
    "back": "后退",
    "forward": "前进",
    "wheel-up": "滚轮上",
    "wheel-down": "滚轮下",
    "dpi-switch": "DPI 切换",
    "dpi-plus": "DPI +",
    "dpi-minus": "DPI −",
    "volume-up": "音量 +",
    "volume-down": "音量 −",
    "mute": "静音",
    "play-pause": "播放/暂停",
    "disable": "禁用",
}

TRIGGER_LABELS: dict[str, str] = {
    "once": "执行一次",
    "hold-loop": "按住时循环",
    "until-same-key": "循环至相同键",
    "until-any-key": "循环至任意键",
}

DSL_HINT = (
    "逗号分隔：a 点按、+a/−a 按下/释放、delay:50 延迟、"
    "mouse:left 鼠标键、wheel:up 滚轮。例：+ctrl,+c,-c,-ctrl"
)

NAV_ITEMS = ("基本", "按键", "宏", "配置")


class Panel(QMainWindow):
    def __init__(self, submit: Submit) -> None:
        super().__init__()
        self._submit = submit
        self._snapshot = None
        self._updating = False
        self.setWindowTitle("A7 设置")
        self.resize(740, 580)
        self.setMinimumSize(640, 480)

        self._header = HeaderBar()

        self._nav = NavList(list(NAV_ITEMS))
        self._stack = QStackedWidget()
        self._stack.addWidget(wrap_scroll(self._build_basic_tab()))
        self._stack.addWidget(wrap_scroll(self._build_buttons_tab()))
        self._stack.addWidget(wrap_scroll(self._build_macro_tab()))
        self._stack.addWidget(wrap_scroll(self._build_profiles_tab()))
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._nav)
        body_layout.addWidget(Hairline(vertical=True))
        body_layout.addWidget(self._stack, 1)

        content = QWidget()
        content.setObjectName("ContentPane")
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header)
        root.addWidget(body, 1)
        self.setCentralWidget(content)

    # ================= 基本 tab =================

    def _build_basic_tab(self) -> QWidget:
        self._dpi_spins: list[QSpinBox] = []
        dpi_rows: list[QWidget] = []
        self._dpi_count = QComboBox()
        self._dpi_count.addItems([str(i) for i in range(1, 7)])
        self._dpi_count.setMinimumWidth(88)
        self._dpi_count.currentIndexChanged.connect(self._sync_dpi_enabled)
        dpi_rows.append(labeled_row("有效档数", self._dpi_count))

        self._dpi_stage = QComboBox()
        self._dpi_stage.setMinimumWidth(88)
        self._dpi_stage.activated.connect(
            lambda: self._submit("dpi_stage", self._dpi_stage.currentIndex())
        )
        dpi_rows.append(labeled_row("当前档位", self._dpi_stage))

        for i in range(6):
            spin = QSpinBox()
            spin.setRange(100, 52000)
            spin.setSingleStep(50)
            spin.setMinimumWidth(108)
            spin.setGroupSeparatorShown(True)
            self._dpi_spins.append(spin)
            dpi_rows.append(labeled_row(f"第 {i + 1} 档", spin))

        apply_dpi = QPushButton("应用 DPI")
        apply_dpi.clicked.connect(self._apply_dpi)
        dpi_rows.append(footer_row(apply_dpi))

        self._rate = QComboBox()
        self._rate.setMinimumWidth(108)
        self._rate.activated.connect(
            lambda: self._submit("rate", self._rate.currentIndex())
        )

        self._lod = QComboBox()
        self._lod.setMinimumWidth(108)
        self._lod.activated.connect(lambda: self._apply_sensor())
        self._game = QComboBox()
        self._game.addItems(["模式 0", "模式 1", "模式 2"])
        self._game.setMinimumWidth(108)
        self._game.activated.connect(lambda: self._apply_sensor())
        self._ripple = QCheckBox()
        self._ripple.clicked.connect(lambda: self._apply_sensor())
        self._line = QCheckBox()
        self._line.clicked.connect(lambda: self._apply_sensor())
        self._motion = QCheckBox()
        self._motion.clicked.connect(lambda: self._apply_sensor())

        self._sleep = QSpinBox()
        self._sleep.setRange(0, 255)
        self._sleep.setSpecialValueText("从不")
        self._sleep.setSuffix(" 分钟")
        self._sleep.setMinimumWidth(108)
        self._sleep.editingFinished.connect(
            lambda: self._submit("sleep", self._sleep.value())
        )
        self._debounce = QSpinBox()
        self._debounce.setRange(0, 20)
        self._debounce.setMinimumWidth(108)
        self._debounce.editingFinished.connect(
            lambda: self._submit("debounce", self._debounce.value())
        )

        return page_column(
            section_title("DPI"),
            Card(*dpi_rows),
            section_title("回报率"),
            Card(labeled_row("回报率", self._rate)),
            section_title("传感器"),
            Card(
                labeled_row("LOD", self._lod),
                labeled_row("电竞模式", self._game),
                labeled_row("波纹控制", self._ripple),
                labeled_row("直线修正", self._line),
                labeled_row("Motion Sync", self._motion),
            ),
            section_title("电源与按键"),
            Card(
                labeled_row("休眠", self._sleep),
                labeled_row("按键防抖", self._debounce),
            ),
        )

    def _sync_dpi_enabled(self) -> None:
        count = self._dpi_count.currentIndex() + 1
        for i, spin in enumerate(self._dpi_spins):
            spin.setEnabled(i < count)

    def _apply_dpi(self) -> None:
        cfg = self._config()
        if cfg is None:
            return
        count = self._dpi_count.currentIndex() + 1
        dpis = tuple(spin.value() for spin in self._dpi_spins)
        index = max(0, self._dpi_stage.currentIndex())
        self._submit("dpi_table", dpis, count, index)

    def _apply_sensor(self) -> None:
        if self._updating:
            return
        lod = self._lod.currentData()
        if lod is None:
            return
        self._submit(
            "sensor",
            {
                "lod": lod,
                "ripple": self._ripple.isChecked(),
                "line": self._line.isChecked(),
                "motion_sync": self._motion.isChecked(),
                "game_mode": self._game.currentIndex(),
            },
        )

    # ================= 按键 tab =================

    def _build_buttons_tab(self) -> QWidget:
        self._button_combos: list[QComboBox] = []
        rows: list[QWidget] = []
        for i in range(6):
            combo = QComboBox()
            combo.setMinimumWidth(160)
            for key, label in PRESET_LABELS.items():
                if key in BUTTON_PRESETS:
                    combo.addItem(label, key)
            combo.activated.connect(lambda _=0, i=i: self._apply_button(i))
            rows.append(
                labeled_row(BUTTON_NAMES.get(i, f"键{i}"), combo, stretch_control=True)
            )
            self._button_combos.append(combo)
        return page_column(
            section_title("按键映射"),
            Card(*rows),
            caption("选择后立即写入鼠标。未列出的自定义键码请用 CLI。"),
        )

    def _apply_button(self, index: int) -> None:
        key = self._button_combos[index].currentData()
        if key is None:
            return
        button_type, value = BUTTON_PRESETS[key]
        self._submit("button", index, button_type, value)

    # ================= 宏 tab =================

    def _build_macro_tab(self) -> QWidget:
        self._macro_key = QComboBox()
        self._macro_key.addItems([BUTTON_NAMES.get(i, f"键{i}") for i in range(6)])
        self._macro_key.setMinimumWidth(160)
        self._macro_mode = QComboBox()
        self._macro_mode.setMinimumWidth(160)
        for key, label in TRIGGER_LABELS.items():
            if key in TRIGGER_MODES:
                self._macro_mode.addItem(label, key)
        self._macro_name = QLineEdit("我的宏")
        self._macro_name.setMinimumWidth(160)
        self._macro_dsl = QLineEdit()
        self._macro_dsl.setPlaceholderText("+a,delay:100,-a")
        write_btn = QPushButton("写入宏")
        write_btn.clicked.connect(self._apply_macro)
        return page_column(
            section_title("板载宏"),
            Card(
                labeled_row("目标键", self._macro_key),
                labeled_row("触发方式", self._macro_mode),
                labeled_row("宏名", self._macro_name, stretch_control=True),
                labeled_row("事件", self._macro_dsl, stretch_control=True),
                footer_row(write_btn),
            ),
            caption(DSL_HINT),
        )

    def _apply_macro(self) -> None:
        try:
            events = parse_events_dsl(self._macro_dsl.text(), _KEY_TOKENS)
        except ValueError as exc:
            QMessageBox.warning(self, "宏事件错误", str(exc))
            return
        mode_key = self._macro_mode.currentData()
        if mode_key is None:
            return
        self._submit(
            "macro",
            self._macro_key.currentIndex(),
            events,
            TRIGGER_MODES[mode_key],
            self._macro_name.text() or "macro",
        )

    # ================= 配置 tab =================

    def _build_profiles_tab(self) -> QWidget:
        save_wrap = QWidget()
        save_layout = QHBoxLayout(save_wrap)
        save_layout.setContentsMargins(12, 8, 12, 8)
        save_layout.setSpacing(8)
        self._profile_name = QLineEdit()
        self._profile_name.setPlaceholderText("配置名，如：办公")
        save_btn = QPushButton("保存当前")
        save_btn.clicked.connect(self._save_profile)
        save_layout.addWidget(self._profile_name)
        save_layout.addWidget(save_btn)

        self._profile_list = QListWidget()
        self._profile_list.setMinimumHeight(180)
        self._profile_list.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        list_wrap = QWidget()
        list_layout = QVBoxLayout(list_wrap)
        list_layout.setContentsMargins(8, 8, 8, 8)
        list_layout.addWidget(self._profile_list)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(12, 8, 12, 8)
        actions_layout.setSpacing(8)
        for text, fn in (
            ("应用", self._apply_profile),
            ("删除", self._delete_profile),
            ("导出…", self._export_profile),
            ("导入…", self._import_profile),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(fn)
            actions_layout.addWidget(btn)
        actions_layout.addStretch()

        self._reload_profiles()
        return page_column(
            section_title("本地配置"),
            Card(save_wrap, list_wrap, actions),
            caption("配置保存在本机，写入鼠标后断电仍然有效。"),
        )

    def _selected_profile(self) -> str | None:
        item = self._profile_list.currentItem()
        return item.text() if item else None

    def _save_profile(self) -> None:
        name = self._profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入配置名")
            return
        self._submit("save_profile", name)
        self._reload_profiles()

    def _apply_profile(self) -> None:
        name = self._selected_profile()
        if not name:
            return
        try:
            cfg = profiles.config_from_dict(profiles.load_profiles()[name])
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "配置无效", str(exc))
            return
        self._submit("apply_config", cfg)

    def _delete_profile(self) -> None:
        name = self._selected_profile()
        if name:
            profiles.delete_profile(name)
            self._reload_profiles()

    def _export_profile(self) -> None:
        name = self._selected_profile()
        if not name:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", f"{name}.json", "JSON (*.json)"
        )
        if path:
            profiles.export_profile(name, Path(path))

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            cfg = profiles.import_profile(Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._submit("apply_config", cfg)

    def _reload_profiles(self) -> None:
        self._profile_list.clear()
        self._profile_list.addItems(sorted(profiles.load_profiles()))

    # ================= 状态回灌 =================

    def _config(self) -> MouseConfig | None:
        return self._snapshot.config if self._snapshot else None

    def show_error(self, message: str) -> None:
        self._header.set_error(message)

    def on_snapshot(self, snap) -> None:  # noqa: ANN001 - 避免与 gui 循环导入
        self._snapshot = snap
        cfg = snap.config
        sleeping = cfg is None
        self._header.set_device(
            snap.variant.model,
            f"{_role_name(snap.variant.role)} · 固件 {snap.firmware}",
            snap.battery,
            bool(snap.charge_status),
            sleeping=sleeping,
        )
        if sleeping:
            return
        self._updating = True
        try:
            for i, spin in enumerate(self._dpi_spins):
                spin.setValue(cfg.dpis[i])
            self._dpi_count.setCurrentIndex(cfg.dpi_count - 1)
            self._dpi_stage.clear()
            self._dpi_stage.addItems([f"第 {i + 1} 档" for i in range(cfg.dpi_count)])
            wired = snap.variant.role == "wired"
            self._dpi_stage.setCurrentIndex(
                cfg.usb_dpi_index if wired else cfg.g_dpi_index
            )
            self._sync_dpi_enabled()
            rates = RATE_TABLES[snap.variant.rate_table]
            self._rate.clear()
            self._rate.addItems([f"{hz} Hz" for hz in rates])
            self._rate.setCurrentIndex(
                cfg.usb_rate_index if wired else cfg.g_rate_index
            )
            caps = MODEL_CAPS.get(snap.variant.model)
            if caps and caps.lod_labels:
                self._lod.clear()
                for key, label in caps.lod_labels.items():
                    self._lod.addItem(label, key)
                lod = sensor_lod(cfg.sensor)
                idx = self._lod.findData(lod)
                self._lod.setCurrentIndex(max(idx, 0))
            self._ripple.setChecked(sensor_ripple(cfg.sensor))
            self._line.setChecked(sensor_line(cfg.sensor))
            self._motion.setChecked(sensor_motion_sync(cfg.sensor))
            self._game.setCurrentIndex(sensor_game_mode(cfg.sensor))
            self._sleep.setValue(cfg.sleep_minutes)
            self._debounce.setValue(cfg.key_debounce)
            preset_rev = {v: k for k, v in BUTTON_PRESETS.items()}
            for i, b in enumerate(cfg.buttons):
                combo = self._button_combos[i]
                name = preset_rev.get((b.button_type, b.value))
                if name is not None:
                    idx = combo.findData(name)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.setToolTip(describe_button(b))
        finally:
            self._updating = False


def _role_name(role: str) -> str:
    return {
        "wired": "有线",
        "receiver-1k": "2.4G（1K）",
        "receiver-8k": "2.4G（8K）",
    }.get(role, role)
