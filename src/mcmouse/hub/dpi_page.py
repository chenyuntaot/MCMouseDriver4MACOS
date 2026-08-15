"""DPI 设置页：档位卡片、分段档数、X/Y 独立、恢复默认。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from ..devices import DPI_MIN, MODEL_CAPS, clamp_dpi
from .theme import DPI_STAGE_COLORS, apply_hub_font, palette
from .widgets import (
    GhostButton,
    HubCard,
    HubCheck,
    HubSlider,
    SegmentedBar,
    muted_label,
)

Submit = Callable[..., None]


def _fusion_spin(spin: QSpinBox) -> None:
    style = QStyleFactory.create("Fusion")
    if style is not None:
        spin.setStyle(style)


class DpiStageCard(HubCard):
    """单档 DPI：色点 + 滑块 + 数值。XY 开启时显示第二滑块。"""

    def __init__(
        self,
        index: int,
        on_select: Callable[[int], None],
        on_commit: Callable[[], None],
    ) -> None:
        super().__init__(clickable=True)
        self._index = index
        self._on_commit = on_commit
        self._xy = False
        self.clicked.connect(lambda: on_select(index))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        head = QHBoxLayout()
        self._dot = QLabel("●")
        self._dot.setStyleSheet(
            f"color: {DPI_STAGE_COLORS[index]}; background: transparent;"
        )
        apply_hub_font(self._dot, 12)
        self._title = QLabel(f"第 {index + 1} 档")
        apply_hub_font(self._title, 13, QFont.Weight.DemiBold)
        head.addWidget(self._dot)
        head.addWidget(self._title)
        head.addStretch()
        self._check = QLabel("✓")
        apply_hub_font(self._check, 14, QFont.Weight.DemiBold)
        self._check.hide()
        head.addWidget(self._check)
        root.addLayout(head)

        x_row = QHBoxLayout()
        self._x_lab = muted_label("X")
        self._x_lab.hide()
        self._x_slider = HubSlider(DPI_MIN, 26000)
        self._x_spin = QSpinBox()
        _fusion_spin(self._x_spin)
        self._x_spin.setRange(DPI_MIN, 26000)
        self._x_spin.setSingleStep(50)
        self._x_spin.setFixedWidth(88)
        self._x_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        x_row.addWidget(self._x_lab)
        x_row.addWidget(self._x_slider, 1)
        x_row.addWidget(self._x_spin)
        root.addLayout(x_row)

        y_row = QHBoxLayout()
        self._y_lab = muted_label("Y")
        self._y_slider = HubSlider(DPI_MIN, 26000)
        self._y_spin = QSpinBox()
        _fusion_spin(self._y_spin)
        self._y_spin.setRange(DPI_MIN, 26000)
        self._y_spin.setSingleStep(50)
        self._y_spin.setFixedWidth(88)
        self._y_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        y_row.addWidget(self._y_lab)
        y_row.addWidget(self._y_slider, 1)
        y_row.addWidget(self._y_spin)
        self._y_wrap = QWidget()
        self._y_wrap.setLayout(y_row)
        self._y_wrap.hide()
        root.addWidget(self._y_wrap)

        self._x_slider.moved.connect(self._x_spin.setValue)
        self._x_slider.committed.connect(self._on_x_slider)
        self._x_spin.editingFinished.connect(self._on_x_spin)
        self._y_slider.moved.connect(self._y_spin.setValue)
        self._y_slider.committed.connect(self._on_y_slider)
        self._y_spin.editingFinished.connect(self._on_y_spin)
        self._style_spin()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._style_spin()
        )

    def _style_spin(self) -> None:
        p = palette()
        qss = f"""
            QSpinBox {{
                background: {p.input_bg};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 4px 8px;
                min-height: 28px;
            }}
        """
        self._x_spin.setStyleSheet(qss)
        self._y_spin.setStyleSheet(qss)
        self._check.setStyleSheet(f"color: {p.accent}; background: transparent;")

    def set_limits(self, dpi_max: int) -> None:
        self._x_slider.set_range(DPI_MIN, dpi_max)
        self._y_slider.set_range(DPI_MIN, dpi_max)
        self._x_spin.setRange(DPI_MIN, dpi_max)
        self._y_spin.setRange(DPI_MIN, dpi_max)

    def set_xy(self, enabled: bool) -> None:
        self._xy = enabled
        self._x_lab.setVisible(enabled)
        self._y_wrap.setVisible(enabled)

    def set_current(self, current: bool) -> None:
        self.set_active(current)
        self._check.setVisible(current)

    def set_values(self, x: int, y: int) -> None:
        self._x_slider.set_value(x)
        self._y_slider.set_value(y)
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)

    def x_value(self) -> int:
        return self._x_spin.value()

    def y_value(self) -> int:
        return self._y_spin.value() if self._xy else self._x_spin.value()

    def _on_x_slider(self, value: int) -> None:
        self._x_spin.setValue(value)
        self._on_commit()

    def _on_y_slider(self, value: int) -> None:
        self._y_spin.setValue(value)
        self._on_commit()

    def _on_x_spin(self) -> None:
        self._x_slider.set_value(self._x_spin.value())
        self._on_commit()

    def _on_y_spin(self) -> None:
        self._y_slider.set_value(self._y_spin.value())
        self._on_commit()


class DpiPage(QWidget):
    def __init__(self, submit: Submit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._submit = submit
        self._updating = False
        self._dpi_max = 26000
        self._model = ""
        self.setObjectName("DpiPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(14)

        bar = QHBoxLayout()
        bar.addWidget(muted_label("档位数量"))
        self._count = SegmentedBar([str(i) for i in range(1, 7)])
        self._count.setObjectName("DpiCount")
        self._count.changed.connect(self._on_count)
        bar.addWidget(self._count)
        bar.addSpacing(16)
        self._xy = HubCheck("X/Y 单独设置")
        self._xy.setObjectName("DpiXY")
        self._xy.toggled.connect(self._on_xy)
        bar.addWidget(self._xy)
        bar.addStretch()
        restore = GhostButton("恢复默认")
        restore.setObjectName("DpiRestore")
        restore.clicked.connect(self._on_restore)
        bar.addWidget(restore)
        root.addLayout(bar)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._cards: list[DpiStageCard] = []
        for i in range(6):
            card = DpiStageCard(i, self._on_select, self._commit_table)
            card.setObjectName(f"DpiCard{i}")
            self._cards.append(card)
            grid.addWidget(card, i // 2, i % 2)
        root.addLayout(grid)
        root.addStretch()

    def set_updating(self, updating: bool) -> None:
        self._updating = updating

    def on_snapshot(self, snap) -> None:  # noqa: ANN001
        cfg = snap.config
        if cfg is None:
            return
        self._model = snap.variant.model
        caps = MODEL_CAPS.get(snap.variant.model)
        self._dpi_max = caps.dpi_max if caps else 26000
        wired = snap.variant.role == "wired"
        index = cfg.usb_dpi_index if wired else cfg.g_dpi_index
        index = max(0, min(index, cfg.dpi_count - 1))
        xy = any(cfg.dpis[i] != cfg.dpi_vals[i] for i in range(max(1, cfg.dpi_count)))
        self._xy.blockSignals(True)
        self._xy.setChecked(xy)
        self._xy.blockSignals(False)
        self._count.set_index(cfg.dpi_count - 1, emit=False)
        for i, card in enumerate(self._cards):
            card.set_limits(self._dpi_max)
            card.set_xy(xy)
            card.set_values(cfg.dpis[i], cfg.dpi_vals[i])
            card.set_current(i == index)
            card.setVisible(i < cfg.dpi_count)
            card.setEnabled(i < cfg.dpi_count)

    def current_index(self) -> int:
        for i, card in enumerate(self._cards):
            if card._active:  # noqa: SLF001 - 选中态存在卡片上
                return i
        return 0

    def select_stage(self, index: int) -> None:
        """测试与点击共用。"""
        self._on_select(index)

    def _on_select(self, index: int) -> None:
        if self._updating:
            return
        count = self._count.index() + 1
        if index >= count:
            return
        for i, card in enumerate(self._cards):
            card.set_current(i == index)
        self._submit("dpi_stage", index)

    def _on_count(self, index: int) -> None:
        if self._updating:
            return
        count = index + 1
        current = min(self.current_index(), count - 1)
        for i, card in enumerate(self._cards):
            card.setVisible(i < count)
            card.setEnabled(i < count)
            card.set_current(i == current)
        self._commit_table()

    def _on_xy(self, checked: bool) -> None:
        for card in self._cards:
            card.set_xy(checked)
        if self._updating:
            return
        self._commit_table()

    def _on_restore(self) -> None:
        if self._updating:
            return
        caps = MODEL_CAPS.get(self._model)
        defaults = caps.default_dpis if caps else (200, 1200, 2200, 3200, 4200, 26000)
        dpis = tuple(
            defaults[i] if i < len(defaults) else defaults[-1] for i in range(6)
        )
        self._submit("dpi_table", dpis, 6, 2, dpis)  # 默认当前档=2，见 kb/0005 §3.1

    def _commit_table(self) -> None:
        if self._updating:
            return
        count = self._count.index() + 1
        index = min(self.current_index(), count - 1)
        dpis = []
        vals = []
        for card in self._cards:
            x = clamp_dpi(card.x_value(), self._dpi_max)
            y = clamp_dpi(card.y_value(), self._dpi_max)
            dpis.append(x)
            vals.append(y if self._xy.isChecked() else x)
        self._submit("dpi_table", tuple(dpis), count, index, tuple(vals))
