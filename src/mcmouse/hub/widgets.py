"""HUB 自定义控件：卡片、分段、开关、滑块、标签页。避开 Cocoa NSMenu（kb/0008）。"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from ..protocol.old import ROTATE_MAX_DEGREES, ROTATE_UNIT_DEGREES
from .theme import apply_hub_font, hub_font, palette


def _fusion(widget: QWidget) -> None:
    style = QStyleFactory.create("Fusion")
    if style is not None:
        widget.setStyle(style)


class HubCard(QFrame):
    """白底圆角卡片，可选选中描边。"""

    clicked = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, clickable: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HubCard")
        self._active = False
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        border = p.accent if self._active else p.border
        width = 2 if self._active else 1
        self.setStyleSheet(
            f"""
            QFrame#HubCard {{
                background: {p.card};
                border: {width}px solid {border};
                border-radius: 12px;
            }}
            """
        )

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._apply()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {p.accent};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 600;
                min-height: 36px;
            }}
            QPushButton:hover {{ background: #2563EB; }}
            QPushButton:pressed {{ background: #1D4ED8; }}
            QPushButton:disabled {{ background: {p.border}; color: {p.muted}; }}
            """
        )


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {p.card};
                color: {p.text};
                border: 1px solid {p.border};
                border-radius: 10px;
                padding: 7px 12px;
                font-size: 13px;
                min-height: 34px;
            }}
            QPushButton:hover {{ background: {p.accent_soft}; }}
            QPushButton:disabled {{ color: {p.muted}; }}
            """
        )


class GhostButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {p.accent};
                border: none;
                font-size: 13px;
                padding: 4px 6px;
            }}
            QPushButton:hover {{ color: #2563EB; }}
            """
        )


class SegmentedBar(QWidget):
    """互斥分段（档位数量 1–6 等）。"""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: list[QPushButton] = []
        for i, text in enumerate(labels):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, i=i: self.set_index(i, emit=True))
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch()
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())
        self.set_index(0, emit=False)

    def _apply(self) -> None:
        p = palette()
        n = len(self._buttons)
        for i, btn in enumerate(self._buttons):
            tl = "10px" if i == 0 else "0"
            tr = "10px" if i == n - 1 else "0"
            bl = tl
            br = tr
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {p.input_bg};
                    color: {p.text};
                    border: 1px solid {p.border};
                    border-top-left-radius: {tl};
                    border-top-right-radius: {tr};
                    border-bottom-left-radius: {bl};
                    border-bottom-right-radius: {br};
                    padding: 5px 14px;
                    min-width: 36px;
                    min-height: 28px;
                    font-size: 13px;
                }}
                QPushButton:checked {{
                    background: {p.accent};
                    color: white;
                    border-color: {p.accent};
                    font-weight: 600;
                }}
                """
            )

    def index(self) -> int:
        return self._index

    def set_index(self, index: int, *, emit: bool = False) -> None:
        index = max(0, min(index, len(self._buttons) - 1))
        self._index = index
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        if emit:
            self.changed.emit(index)


class RadioPills(QWidget):
    """单选药丸组（回报率、LOD、模式）。"""

    changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = -1
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._buttons: list[QPushButton] = []
        self._stretch = True
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def set_items(self, labels: list[str], current: int = 0) -> None:
        for btn in self._buttons:
            btn.deleteLater()
        self._buttons.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, text in enumerate(labels):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=i: self.set_index(i, emit=True))
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        if self._stretch:
            self._layout.addStretch()
        self._apply()
        self.set_index(current, emit=False)

    def _apply(self) -> None:
        p = palette()
        for btn in self._buttons:
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {p.input_bg};
                    color: {p.text};
                    border: 1px solid {p.border};
                    border-radius: 10px;
                    padding: 8px 16px;
                    min-height: 34px;
                    font-size: 13px;
                }}
                QPushButton:checked {{
                    background: {p.accent_soft};
                    color: {p.accent};
                    border-color: {p.accent};
                    font-weight: 600;
                }}
                """
            )

    def index(self) -> int:
        return self._index

    def set_index(self, index: int, *, emit: bool = False) -> None:
        if not self._buttons:
            self._index = -1
            return
        index = max(0, min(index, len(self._buttons) - 1))
        changed = index != self._index
        self._index = index
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        if emit and changed:
            self.changed.emit(index)


class ToggleSwitch(QWidget):
    """iOS 风开关。"""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on = False
        self.setFixedSize(42, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def is_on(self) -> bool:
        return self._on

    def set_on(self, on: bool, *, emit: bool = False) -> None:
        if self._on == on:
            return
        self._on = on
        self.update()
        if emit:
            self.toggled.emit(on)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_on(not self._on, emit=True)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = palette()
        track = QRectF(1, 3, 40, 18)
        path = QPainterPath()
        path.addRoundedRect(track, 9, 9)
        painter.fillPath(path, QColor(p.accent if self._on else p.border))
        cx = 31 if self._on else 11
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPointF(cx, 12), 8, 8)


class HubSlider(QWidget):
    """带松手提交的横向滑块。"""

    committed = Signal(int)
    moved = Signal(int)

    def __init__(self, lo: int, hi: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dragging = False
        self._committed: int | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        _fusion(self._slider)
        self._slider.setRange(lo, hi)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.sliderPressed.connect(self._on_pressed)
        self._slider.sliderReleased.connect(self._on_released)
        self._slider.valueChanged.connect(self._on_changed)
        root.addWidget(self._slider)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        self._slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 6px;
                border-radius: 3px;
                background: {p.border};
            }}
            QSlider::sub-page:horizontal {{
                height: 6px;
                border-radius: 3px;
                background: {p.accent};
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
                background: white;
                border: 1px solid {p.border};
            }}
            """
        )

    def set_range(self, lo: int, hi: int) -> None:
        self._slider.setRange(lo, hi)

    def value(self) -> int:
        return self._slider.value()

    def set_value(self, value: int, *, commit: bool = True) -> None:
        if self._dragging:
            return
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        if commit:
            self._committed = value

    def _on_pressed(self) -> None:
        self._dragging = True

    def _on_changed(self, value: int) -> None:
        self.moved.emit(value)

    def _on_released(self) -> None:
        self._dragging = False
        value = self._slider.value()
        if value != self._committed:
            self._committed = value
            self.committed.emit(value)


class HubCheck(QCheckBox):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _fusion(self)
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())

    def _apply(self) -> None:
        p = palette()
        self.setStyleSheet(
            f"""
            QCheckBox {{
                color: {p.text};
                spacing: 8px;
                font-size: 13px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {p.border};
                background: {p.input_bg};
            }}
            QCheckBox::indicator:checked {{
                background: {p.accent};
                border-color: {p.accent};
            }}
            """
        )


class HubTabBar(QWidget):
    """顶部四标签，选中项蓝色下划线。"""

    currentChanged = Signal(int)

    def __init__(
        self, items: list[tuple[str, str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(56)
        self._index = 0
        self._items = items
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(4)
        self._buttons: list[QPushButton] = []
        for i, (_icon, label) in enumerate(items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            apply_hub_font(btn, 13, QFont.Weight.Medium)
            btn.clicked.connect(lambda _=False, i=i: self.set_index(i, emit=True))
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch()
        self._apply()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply())
        self.set_index(0, emit=False)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        painter = QPainter(self)
        p = palette()
        painter.fillRect(0, self.height() - 1, self.width(), 1, QColor(p.border))
        if 0 <= self._index < len(self._buttons):
            btn = self._buttons[self._index]
            painter.fillRect(
                btn.x() + 12,
                self.height() - 3,
                max(btn.width() - 24, 24),
                3,
                QColor(p.accent),
            )

    def _apply(self) -> None:
        p = palette()
        for i, btn in enumerate(self._buttons):
            color = p.accent if i == self._index else p.muted
            weight = "600" if i == self._index else "500"
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    color: {color};
                    border: none;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: {weight};
                }}
                """
            )
        self.update()

    def index(self) -> int:
        return self._index

    def set_index(self, index: int, *, emit: bool = False) -> None:
        index = max(0, min(index, len(self._buttons) - 1))
        changed = index != self._index
        self._index = index
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        self._apply()
        if emit and changed:
            self.currentChanged.emit(index)


# 旋转量程：协议 rotateVal 就是度数（kb/0005 §3.3），盘面每一格都能原样写进设备。
ROTATE_STEP = ROTATE_UNIT_DEGREES
ROTATE_LIMIT = ROTATE_MAX_DEGREES  # 与线上量程一致，±30°
ROTATE_MAJOR = 10  # 带数字的长刻度间隔
_SWEEP = 250.0  # 整个量程占的屏幕弧度
_MINOR_TICK = 2  # 每 2° 一根细刻度，避免 1° 一根糊成一片
_KNOB_GRAB = 14.0  # 圆钮的抓取半径（可见半径 11px + 少量余量）
_RING_GRAB = 10.0  # 刻度环的抓取带宽（相对半径）
_ZERO_DETENT = 1.0  # 0° 磁吸半宽：指针落点 ±1° 内都算 0，保证能稳稳停在 0


def _rotate_angle(degrees: float) -> float:
    """角度值 → 屏幕角（数学约定，0°=正右，逆时针为正）。0 在正上方。"""
    return 90.0 - degrees * (_SWEEP / (ROTATE_LIMIT * 2))


def _rotate_majors() -> list[int]:
    """带数字的长刻度：以 0 为中心对称。"""
    count = ROTATE_LIMIT // ROTATE_MAJOR
    return [i * ROTATE_MAJOR for i in range(-count, count + 1)]


def _snap_rotate(degrees: float) -> int:
    stepped = int(round(degrees / ROTATE_STEP)) * ROTATE_STEP
    return max(-ROTATE_LIMIT, min(ROTATE_LIMIT, stepped))


def _detent_zero(degrees: float) -> float:
    """0° 磁吸：指针落点在 ±_ZERO_DETENT 内视为 0。

    1° 在盘面上只有 ~6px，没有磁吸几乎不可能停在 0 上。
    代价是盘面拖动设不出 ±1°，用两侧步进按钮可达（kb/0010 §5）。
    """
    return 0.0 if abs(degrees) <= _ZERO_DETENT else degrees


class _RotateDial(QWidget):
    """刻度盘本体：刻度环 + 可拖动的圆钮 + 中心角度读数。"""

    moved = Signal(int)
    committed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._degrees = 0
        self._dragging = False
        self._drag_from = 0
        self._drag_offset = 0.0
        self.setMinimumSize(210, 210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)  # 悬停到可拖动区域才变手型

    def degrees(self) -> int:
        return self._degrees

    def set_degrees(self, degrees: float) -> None:
        """显示设备读回的角度：原样保留，不做吸附与截断。

        盘面量程与线上量程一致（±30°），超出说明解码有误，按量程收口，
        圆钮停在端点，以免显示出荒唐角度。拖动进行中忽略回填，
        否则 60s 轮询快照会把用户手里的圆钮拽走。
        """
        if self._dragging:
            return
        self._degrees = max(-ROTATE_MAX_DEGREES, min(ROTATE_MAX_DEGREES, int(degrees)))
        self.update()

    def _knob_degrees(self) -> int:
        return max(-ROTATE_LIMIT, min(ROTATE_LIMIT, self._degrees))

    def set_user_degrees(self, degrees: float) -> bool:
        """用户输入的角度：吸附到协议可写入的整度网格。返回是否有变化。"""
        value = _snap_rotate(degrees)
        if value == self._degrees:
            return False
        self._degrees = value
        self.update()
        return True

    # ---------- 几何 ----------

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2 + 6)

    def _radius(self) -> float:
        return max(56.0, min(self.width(), self.height()) / 2 - 34)

    def _point_at(self, degrees: float, radius: float) -> QPointF:
        rad = math.radians(_rotate_angle(degrees))
        c = self._center()
        return QPointF(c.x() + radius * math.cos(rad), c.y() - radius * math.sin(rad))

    def _value_at_float(self, pos: QPointF) -> float:
        """指针位置 → 未吸附的角度值（浮点）。"""
        c = self._center()
        angle = math.degrees(math.atan2(c.y() - pos.y(), pos.x() - c.x())) % 360.0
        lo, hi = _rotate_angle(ROTATE_LIMIT) % 360.0, _rotate_angle(-ROTATE_LIMIT)
        # 量程之外（正下方的缺口）就近吸附到两端
        if hi < angle < lo:
            angle = lo if angle - hi > lo - angle else hi
        if angle >= lo:
            angle -= 360.0
        return (90.0 - angle) / (_SWEEP / (ROTATE_LIMIT * 2))

    def _value_at(self, pos: QPointF) -> int:
        return _snap_rotate(_detent_zero(self._value_at_float(pos)))

    # ---------- 交互 ----------

    def _on_knob(self, pos: QPointF) -> bool:
        radius = self._radius()
        knob = self._point_at(self._knob_degrees(), radius + 2)
        return math.hypot(pos.x() - knob.x(), pos.y() - knob.y()) <= _KNOB_GRAB

    def _is_grab(self, pos: QPointF) -> bool:
        """只有按在圆钮上或刻度环附近才算拖动。

        控件矩形远大于刻度环，若整块都能拖，点一下卡片空白处圆钮就会跳到
        那个方位（并顺带下发一次写）。命中带宽必须贴近可见元素：
        圆钮可见半径 11px、刻度最多伸进环内 15px，带子再宽就会把
        「看起来空白」的地方也算进来，误触跳角度（kb/0010 §3/§5）。
        """
        if self._on_knob(pos):
            return True
        c = self._center()
        dist = math.hypot(pos.x() - c.x(), pos.y() - c.y())
        if abs(dist - self._radius()) > _RING_GRAB:
            return False
        return self._within_sweep(pos)

    def _within_sweep(self, pos: QPointF) -> bool:
        """排除正下方量程之外的缺口。"""
        c = self._center()
        angle = math.degrees(math.atan2(c.y() - pos.y(), pos.x() - c.x())) % 360.0
        lo, hi = _rotate_angle(ROTATE_LIMIT) % 360.0, _rotate_angle(-ROTATE_LIMIT)
        return not hi < angle < lo

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if not self._is_grab(pos):
            event.ignore()
            return
        self._dragging = True
        self._drag_from = self._degrees
        if self._on_knob(pos):
            # 抓的是圆钮：保留指针相对圆钮的角差，拖动时圆钮不会瞬移到指针下。
            # 否则 1° 只有 ~6px，按下瞬间指针偏一点，值就跳 ±1~3°（kb/0010 §5）。
            self._drag_offset = self._value_at_float(pos) - self._knob_degrees()
        else:
            self._drag_offset = 0.0  # 点刻度环：绝对跳到落点角度
        self._apply_drag(pos)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._dragging:
            self._apply_drag(event.position())
            return
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._is_grab(event.position())
            else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        del event
        if not self._dragging:
            return
        self._dragging = False
        if self._degrees != self._drag_from:  # 没改动就不下发多余的写
            self.committed.emit(self._degrees)

    def _apply_drag(self, pos: QPointF) -> None:
        target = _snap_rotate(
            _detent_zero(self._value_at_float(pos) - self._drag_offset)
        )
        if self.set_user_degrees(target):
            self.moved.emit(self._degrees)

    # ---------- 绘制 ----------

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = palette()
        c, radius = self._center(), self._radius()
        inner = radius - 16

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.input_bg))
        painter.drawEllipse(c, inner, inner)

        # 中心十字虚线
        dash = QPen(QColor(p.border), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(dash)
        painter.drawLine(QPointF(c.x() - inner, c.y()), QPointF(c.x() + inner, c.y()))
        painter.drawLine(QPointF(c.x(), c.y() - inner), QPointF(c.x(), c.y() + inner))

        self._paint_ticks(painter, radius)
        self._paint_mouse(painter, c, inner)

        painter.setPen(QColor(p.text))
        painter.setFont(hub_font(max(16, int(inner * 0.28)), QFont.Weight.Bold))
        painter.drawText(
            QRectF(c.x() - inner, c.y() - inner * 0.05, inner * 2, inner * 0.5),
            int(Qt.AlignmentFlag.AlignCenter),
            f"{self._degrees}°",
        )

        knob = self._point_at(self._knob_degrees(), radius + 2)
        painter.setPen(QPen(QColor(p.card), 2))
        painter.setBrush(QColor(p.accent))
        painter.drawEllipse(knob, 9, 9)

    def _paint_ticks(self, painter: QPainter, radius: float) -> None:
        p = palette()
        painter.setFont(hub_font(11, QFont.Weight.Medium))
        fine = QPen(QColor(p.border), 1.2)
        majors = set(_rotate_majors()) | {-ROTATE_LIMIT, ROTATE_LIMIT}
        for value in range(-ROTATE_LIMIT, ROTATE_LIMIT + 1, _MINOR_TICK):
            if value in majors:
                continue
            painter.setPen(fine)
            painter.drawLine(
                self._point_at(value, radius - 7), self._point_at(value, radius)
            )
        painter.setPen(QPen(QColor(p.muted), 2.2))
        for end in (-ROTATE_LIMIT, ROTATE_LIMIT):  # 量程端点也用长刻度收口
            painter.drawLine(
                self._point_at(end, radius - 15), self._point_at(end, radius)
            )
        for value in _rotate_majors():
            painter.setPen(QPen(QColor(p.muted), 2.2))
            painter.drawLine(
                self._point_at(value, radius - 15), self._point_at(value, radius)
            )
            label = self._point_at(value, radius + 22)
            painter.setPen(QColor(p.muted))
            painter.drawText(
                QRectF(label.x() - 26, label.y() - 11, 52, 22),
                int(Qt.AlignmentFlag.AlignCenter),
                f"{value}°",
            )

    def _paint_mouse(self, painter: QPainter, c: QPointF, inner: float) -> None:
        """中心随角度转动的鼠标示意。"""
        p = palette()
        half_w, half_h = inner * 0.30, inner * 0.46
        painter.save()
        painter.translate(c)
        painter.rotate(self._knob_degrees())
        painter.setPen(QPen(QColor(p.muted), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(-half_w, -half_h, half_w * 2, half_h * 2), half_w * 0.9, half_w
        )
        wheel_w = half_w * 0.22
        painter.drawRoundedRect(
            QRectF(-wheel_w, -half_h * 0.72, wheel_w * 2, half_h * 0.34),
            wheel_w,
            wheel_w,
        )
        painter.restore()


class RotateGauge(QWidget):
    """角度旋转：左右加减按钮 + 中间可拖动刻度盘。

    步进 1°，量程 ±30°（kb/0005 §3.3）。
    """

    committed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(10)
        self._minus = SecondaryButton("−")
        self._minus.setFixedSize(48, 48)
        apply_hub_font(self._minus, 20)
        self._plus = SecondaryButton("+")
        self._plus.setFixedSize(48, 48)
        apply_hub_font(self._plus, 20)
        self._minus.clicked.connect(lambda: self._nudge(-ROTATE_STEP))
        self._plus.clicked.connect(lambda: self._nudge(ROTATE_STEP))
        self._dial = _RotateDial()
        self._dial.committed.connect(self.committed.emit)
        row.addWidget(self._minus, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._dial, 1)
        row.addWidget(self._plus, 0, Qt.AlignmentFlag.AlignVCenter)

    def degrees(self) -> int:
        return self._dial.degrees()

    def set_degrees(self, degrees: int) -> None:
        self._dial.set_degrees(degrees)

    def _nudge(self, delta: int) -> None:
        # 设备值可能超出盘面量程，先落回端点再步进，避免一步跳过整个量程
        base = max(-ROTATE_LIMIT, min(ROTATE_LIMIT, self._dial.degrees()))
        if self._dial.set_user_degrees(base + delta):
            self.committed.emit(self._dial.degrees())


def labeled_block(title: str, *widgets: QWidget) -> QWidget:
    """卡片标题 + 内容。"""
    box = HubCard()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    lab = QLabel(title)
    apply_hub_font(lab, 13, QFont.Weight.DemiBold)
    layout.addWidget(lab)
    for w in widgets:
        layout.addWidget(w)
    return box


def muted_label(text: str) -> QLabel:
    lab = QLabel(text)
    apply_hub_font(lab, 12)
    p = palette()
    lab.setStyleSheet(f"color: {p.muted};")
    lab.setWordWrap(True)
    return lab
