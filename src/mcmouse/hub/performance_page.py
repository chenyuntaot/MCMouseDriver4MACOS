"""性能设置页：模式、休眠、回报率、LOD、防抖、旋转、三开关。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..devices import MODEL_CAPS
from ..protocol.old import (
    RATE_TABLES,
    sensor_game_mode,
    sensor_line,
    sensor_lod,
    sensor_motion_sync,
    sensor_ripple,
)
from .theme import GAME_MODE_LABELS, apply_hub_font, palette
from .widgets import (
    HubCard,
    HubCheck,
    HubSlider,
    RadioPills,
    RotateGauge,
    ToggleSwitch,
    labeled_block,
    muted_label,
)

Submit = Callable[..., None]


class _ToggleRow(QWidget):
    def __init__(self, title: str, hint: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        text = QVBoxLayout()
        text.setSpacing(2)
        lab = QLabel(title)
        apply_hub_font(lab, 13, QFont.Weight.DemiBold)
        text.addWidget(lab)
        text.addWidget(muted_label(hint))
        layout.addLayout(text, 1)
        self.toggle = ToggleSwitch()
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)


class PerformancePage(QWidget):
    def __init__(self, submit: Submit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._submit = submit
        self._updating = False
        self._lod_keys: list[int] = []
        self.setObjectName("PerformancePage")

        root = QGridLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(12)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 1)

        self._mode = RadioPills()
        self._mode.setObjectName("GameMode")
        self._mode.set_items(list(GAME_MODE_LABELS), 0)
        self._mode.changed.connect(lambda _: self._commit_sensor())
        root.addWidget(labeled_block("模式选择", self._mode), 0, 0)

        sleep_row = QHBoxLayout()
        self._sleep = HubSlider(1, 30)
        self._sleep.setObjectName("SleepSlider")
        self._sleep_val = muted_label("3 分钟")
        self._sleep.moved.connect(self._on_sleep_moved)
        self._sleep.committed.connect(self._on_sleep_commit)
        self._never = HubCheck("永不休眠")
        self._never.setObjectName("NeverSleep")
        self._never.toggled.connect(self._on_never)
        sleep_inner = QWidget()
        col = QVBoxLayout(sleep_inner)
        col.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.addWidget(self._sleep_val)
        head.addStretch()
        head.addWidget(self._never)
        col.addLayout(head)
        col.addWidget(self._sleep)
        sleep_row.addWidget(sleep_inner)
        wrap = QWidget()
        wrap.setLayout(sleep_row)
        root.addWidget(labeled_block("休眠设置", wrap), 1, 0)

        self._rate = RadioPills()
        self._rate.setObjectName("RatePills")
        self._rate.changed.connect(self._on_rate)
        root.addWidget(labeled_block("回报率设置", self._rate), 2, 0)

        self._lod = RadioPills()
        self._lod.setObjectName("LodPills")
        self._lod.changed.connect(lambda _: self._commit_sensor())
        root.addWidget(labeled_block("LOD 静默高度", self._lod), 3, 0)

        debounce_box = QWidget()
        d_l = QVBoxLayout(debounce_box)
        d_l.setContentsMargins(0, 0, 0, 0)
        self._debounce_lab = muted_label("8 ms")
        d_l.addWidget(self._debounce_lab)
        self._debounce = HubSlider(0, 20)
        self._debounce.setObjectName("DebounceSlider")
        self._debounce.moved.connect(lambda v: self._debounce_lab.setText(f"{v} ms"))
        self._debounce.committed.connect(self._on_debounce)
        d_l.addWidget(self._debounce)
        root.addWidget(labeled_block("按键消抖时间", debounce_box), 4, 0)

        self._rotate = RotateGauge()
        self._rotate.setObjectName("RotateGauge")
        self._rotate.committed.connect(self._on_rotate)
        root.addWidget(
            labeled_block(
                "旋转",
                muted_label("调整传感器角度与握持方式匹配，实现更精准的移动控制"),
                self._rotate,
            ),
            0,
            1,
            3,
            1,
        )

        self._ripple = _ToggleRow("波纹控制", "减少高速移动时的波纹残影")
        self._ripple.toggle.toggled.connect(lambda _: self._commit_sensor())
        self._line = _ToggleRow("直线修正", "沿轴向移动时吸附为直线")
        self._line.toggle.toggled.connect(lambda _: self._commit_sensor())
        self._motion = _ToggleRow("移动同步", "传感器与回报率同步采样")
        self._motion.toggle.toggled.connect(lambda _: self._commit_sensor())
        root.addWidget(
            self._as_card(self._ripple, self._line, self._motion), 3, 1, 2, 1
        )

    def _as_card(self, *rows: QWidget) -> HubCard:
        card = HubCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        p = palette()
        for i, row in enumerate(rows):
            if i:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(1)
                line.setStyleSheet(f"background: {p.border}; border: none;")
                layout.addWidget(line)
            layout.addWidget(row)
        return card

    def set_updating(self, updating: bool) -> None:
        self._updating = updating

    def on_snapshot(self, snap) -> None:  # noqa: ANN001
        cfg = snap.config
        if cfg is None:
            return
        self._mode.set_index(sensor_game_mode(cfg.sensor), emit=False)
        minutes = cfg.sleep_minutes
        never = minutes == 0
        self._never.blockSignals(True)
        self._never.setChecked(never)
        self._never.blockSignals(False)
        self._sleep.setEnabled(not never)
        if not never:
            self._sleep.set_value(max(1, min(30, minutes)))
            self._sleep_val.setText(f"{minutes} 分钟")
        else:
            self._sleep_val.setText("永不休眠")
        rates = RATE_TABLES[snap.variant.rate_table]
        wired = snap.variant.role == "wired"
        rate_cur = cfg.usb_rate_index if wired else cfg.g_rate_index
        self._rate.set_items([f"{hz} Hz" for hz in rates], rate_cur)
        caps = MODEL_CAPS.get(snap.variant.model)
        labels = caps.lod_labels if caps else {1: "1mm", 2: "2mm"}
        self._lod_keys = list(labels)
        lod = sensor_lod(cfg.sensor)
        lod_index = self._lod_keys.index(lod) if lod in self._lod_keys else 0
        self._lod.set_items([labels[k] for k in self._lod_keys], lod_index)
        self._debounce.set_value(cfg.key_debounce)
        self._debounce_lab.setText(f"{cfg.key_debounce} ms")
        self._ripple.toggle.set_on(sensor_ripple(cfg.sensor))
        self._line.toggle.set_on(sensor_line(cfg.sensor))
        self._motion.toggle.set_on(sensor_motion_sync(cfg.sensor))
        self._rotate.set_degrees(cfg.rotate_degrees)

    def _on_sleep_moved(self, value: int) -> None:
        self._sleep_val.setText(f"{value} 分钟")

    def _on_sleep_commit(self, value: int) -> None:
        if self._updating or self._never.isChecked():
            return
        self._submit("sleep", value)

    def _on_never(self, checked: bool) -> None:
        self._sleep.setEnabled(not checked)
        if self._updating:
            return
        if checked:
            self._sleep_val.setText("永不休眠")
            self._submit("sleep", 0)
        else:
            self._submit("sleep", self._sleep.value())

    def _on_debounce(self, value: int) -> None:
        if self._updating:
            return
        self._submit("debounce", value)

    def _on_rate(self, index: int) -> None:
        if self._updating:
            return
        self._submit("rate", index)

    def _on_rotate(self, degrees: int) -> None:
        self._commit_sensor(rotate_degrees=degrees)

    def _commit_sensor(self, rotate_degrees: int | None = None) -> None:
        if self._updating:
            return
        lod = 1
        if self._lod_keys and 0 <= self._lod.index() < len(self._lod_keys):
            lod = self._lod_keys[self._lod.index()]
        payload: dict[str, object] = {
            "lod": lod,
            "ripple": self._ripple.toggle.is_on(),
            "line": self._line.toggle.is_on(),
            "motion_sync": self._motion.toggle.is_on(),
            "game_mode": max(0, self._mode.index()),
        }
        # 只有用户真的动过刻度盘才写角度：设备量程（±120°）比刻度盘（±28°）大，
        # 若每次都带上盘面读数，会把官方软件设过的大角度静默改小。
        if rotate_degrees is not None:
            payload["rotate_degrees"] = rotate_degrees
        self._submit("sensor", payload)
