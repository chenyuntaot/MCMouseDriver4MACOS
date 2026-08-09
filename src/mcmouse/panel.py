"""设置面板（M2，FR-2/3/5/6）：基本设置、按键映射、宏、命名配置。

只组装任务交给 gui.DeviceWorker 执行；状态通过 on_snapshot 回灌。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
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

Submit = Callable[..., None]

_KEY_TOKENS: dict[str, int] = {v.lower(): k for k, v in HID_USAGE_NAMES.items()}
_KEY_TOKENS.update({"up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4F})

DSL_HINT = (
    "事件 DSL（逗号分隔）：a 点按、+a/-a 按下/释放、delay:50 延迟、"
    "mouse:left 鼠标键、wheel:up 滚轮；例：+ctrl,+c,-c,-ctrl"
)


class Panel(QMainWindow):
    def __init__(self, submit: Submit) -> None:
        super().__init__()
        self._submit = submit
        self._snapshot = None
        self._updating = False  # 回灌时屏蔽控件信号
        self.setWindowTitle("MCMouseDriver 设置")
        self.resize(520, 560)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_basic_tab(), "基本")
        tabs.addTab(self._build_buttons_tab(), "按键")
        tabs.addTab(self._build_macro_tab(), "宏")
        tabs.addTab(self._build_profiles_tab(), "配置")
        self.setCentralWidget(tabs)
        self.statusBar()

    # ================= 基本 tab =================

    def _build_basic_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        dpi_box = QWidget()
        dpi_layout = QVBoxLayout(dpi_box)
        dpi_layout.setContentsMargins(0, 0, 0, 0)
        self._dpi_spins: list[QSpinBox] = []
        for i in range(6):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"第 {i + 1} 档"))
            spin = QSpinBox()
            spin.setRange(100, 52000)
            spin.setSingleStep(50)
            self._dpi_spins.append(spin)
            row.addWidget(spin)
            dpi_layout.addLayout(row)
        apply_dpi = QPushButton("应用 DPI")
        apply_dpi.clicked.connect(self._apply_dpi)
        dpi_layout.addWidget(apply_dpi)
        form.addRow("DPI（100-52000）", dpi_box)

        self._dpi_count = QComboBox()
        self._dpi_count.addItems([str(i) for i in range(1, 7)])
        form.addRow("有效档数", self._dpi_count)

        self._dpi_stage = QComboBox()
        form.addRow("当前档位", self._dpi_stage)

        self._rate = QComboBox()
        rate_apply = QPushButton("应用")
        rate_apply.clicked.connect(
            lambda: self._submit("rate", self._rate.currentIndex())
        )
        rate_row = QHBoxLayout()
        rate_row.addWidget(self._rate)
        rate_row.addWidget(rate_apply)
        form.addRow("回报率", rate_row)

        self._lod = QComboBox()
        form.addRow("LOD", self._lod)
        self._ripple = QCheckBox("波纹控制")
        self._line = QCheckBox("直线修正")
        self._motion = QCheckBox("Motion Sync")
        sensor_row = QHBoxLayout()
        sensor_row.addWidget(self._ripple)
        sensor_row.addWidget(self._line)
        sensor_row.addWidget(self._motion)
        form.addRow("开关", sensor_row)
        self._game = QComboBox()
        self._game.addItems(["模式 0", "模式 1", "模式 2"])
        form.addRow("电竞模式", self._game)
        apply_sensor = QPushButton("应用性能设置")
        apply_sensor.clicked.connect(self._apply_sensor)
        form.addRow(apply_sensor)

        self._sleep = QSpinBox()
        self._sleep.setRange(0, 255)
        self._sleep.setSuffix(" 分钟（0=从不）")
        sleep_apply = QPushButton("应用")
        sleep_apply.clicked.connect(lambda: self._submit("sleep", self._sleep.value()))
        sleep_row = QHBoxLayout()
        sleep_row.addWidget(self._sleep)
        sleep_row.addWidget(sleep_apply)
        form.addRow("休眠", sleep_row)

        self._debounce = QSpinBox()
        self._debounce.setRange(0, 20)
        debounce_apply = QPushButton("应用")
        debounce_apply.clicked.connect(
            lambda: self._submit("debounce", self._debounce.value())
        )
        debounce_row = QHBoxLayout()
        debounce_row.addWidget(self._debounce)
        debounce_row.addWidget(debounce_apply)
        form.addRow("按键防抖", debounce_row)
        return page

    def _apply_dpi(self) -> None:
        cfg = self._config()
        if cfg is None:
            return
        count = self._dpi_count.currentIndex() + 1
        dpis = tuple(spin.value() for spin in self._dpi_spins)
        index = self._dpi_stage.currentIndex()
        self._submit("dpi_table", dpis, count, index)

    def _apply_sensor(self) -> None:
        self._submit(
            "sensor",
            {
                "lod": self._lod.currentData(),
                "ripple": self._ripple.isChecked(),
                "line": self._line.isChecked(),
                "motion_sync": self._motion.isChecked(),
                "game_mode": self._game.currentIndex(),
            },
        )

    # ================= 按键 tab =================

    def _build_buttons_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._button_combos: list[QComboBox] = []
        presets = list(BUTTON_PRESETS)
        for i in range(6):
            combo = QComboBox()
            combo.addItems(presets)
            apply_btn = QPushButton("应用")
            apply_btn.clicked.connect(lambda _=False, i=i: self._apply_button(i))
            row = QHBoxLayout()
            row.addWidget(combo)
            row.addWidget(apply_btn)
            form.addRow(BUTTON_NAMES.get(i, f"键{i}"), row)
            self._button_combos.append(combo)
        return page

    def _apply_button(self, index: int) -> None:
        button_type, value = BUTTON_PRESETS[self._button_combos[index].currentText()]
        self._submit("button", index, button_type, value)

    # ================= 宏 tab =================

    def _build_macro_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._macro_key = QComboBox()
        self._macro_key.addItems([BUTTON_NAMES.get(i, f"键{i}") for i in range(6)])
        form.addRow("目标键", self._macro_key)
        self._macro_dsl = QLineEdit()
        self._macro_dsl.setPlaceholderText("+a,delay:100,-a")
        form.addRow("事件", self._macro_dsl)
        hint = QLabel(DSL_HINT)
        hint.setWordWrap(True)
        form.addRow(hint)
        self._macro_mode = QComboBox()
        self._macro_mode.addItems(list(TRIGGER_MODES))
        form.addRow("触发方式", self._macro_mode)
        self._macro_name = QLineEdit("我的宏")
        form.addRow("宏名", self._macro_name)
        apply_btn = QPushButton("写入宏")
        apply_btn.clicked.connect(self._apply_macro)
        form.addRow(apply_btn)
        return page

    def _apply_macro(self) -> None:
        try:
            events = parse_events_dsl(self._macro_dsl.text(), _KEY_TOKENS)
        except ValueError as exc:
            QMessageBox.warning(self, "宏事件错误", str(exc))
            return
        self._submit(
            "macro",
            self._macro_key.currentIndex(),
            events,
            TRIGGER_MODES[self._macro_mode.currentText()],
            self._macro_name.text() or "macro",
        )

    # ================= 配置 tab =================

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        save_row = QHBoxLayout()
        self._profile_name = QLineEdit()
        self._profile_name.setPlaceholderText("配置名，如：办公")
        save_btn = QPushButton("保存当前配置")
        save_btn.clicked.connect(self._save_profile)
        save_row.addWidget(self._profile_name)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        self._profile_list = QListWidget()
        layout.addWidget(self._profile_list)

        btn_row = QHBoxLayout()
        for text, fn in (
            ("应用", self._apply_profile),
            ("删除", self._delete_profile),
            ("导出…", self._export_profile),
            ("导入…", self._import_profile),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(fn)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)
        self._reload_profiles()
        return page

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

    def on_snapshot(self, snap) -> None:
        self._snapshot = snap
        cfg = snap.config
        self._updating = True
        try:
            if cfg is None:
                self.statusBar().showMessage(
                    "鼠标休眠或未连接——晃动鼠标后点托盘菜单刷新"
                )
                return
            self.statusBar().showMessage(
                f"{snap.variant.model}  固件 {snap.firmware}  电量 {snap.battery}%"
            )
            for i, spin in enumerate(self._dpi_spins):
                spin.setValue(cfg.dpis[i])
            self._dpi_count.setCurrentIndex(cfg.dpi_count - 1)
            self._dpi_stage.clear()
            self._dpi_stage.addItems([f"第 {i + 1} 档" for i in range(cfg.dpi_count)])
            wired = snap.variant.role == "wired"
            self._dpi_stage.setCurrentIndex(
                cfg.usb_dpi_index if wired else cfg.g_dpi_index
            )
            rates = RATE_TABLES[snap.variant.rate_table]
            self._rate.clear()
            self._rate.addItems([f"{hz}Hz" for hz in rates])
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
                    combo.setCurrentText(name)
                combo.setToolTip(describe_button(b))
        finally:
            self._updating = False
