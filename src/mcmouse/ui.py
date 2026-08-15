"""macOS 原生观感：色板、卡片、侧栏、电量与托盘图标。

不全局覆盖 QPushButton/QComboBox/QSpinBox，以免丢掉 Cocoa 原生控件。
只给自定义容器（卡片、侧栏、弹层药丸按钮）上样式。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .devices import DPI_MIN, DPI_STEP, clamp_dpi

POPUP_SHADOW = 16
POPUP_RADIUS = 12
POPOVER_WIDTH = 300


def is_dark() -> bool:
    """当前是否深色外观。"""
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def accent_color() -> QColor:
    """系统强调色（跟随用户在「外观」里选的色）。"""
    return QGuiApplication.palette().color(QPalette.ColorRole.Highlight)


def secondary_text() -> str:
    return "#98989d" if is_dark() else "#86868b"


def apply_macos_app(app: QApplication) -> None:
    """启用 macOS 原生样式与系统字体。不设全局 QSS，以免毁掉 Cocoa 控件。"""
    app.setStyle("macos")
    app.setFont(QFont(".AppleSystemUIFont", 13))


def hairline_color() -> QColor:
    if is_dark():
        return QColor(255, 255, 255, 22)
    return QColor(60, 60, 67, 31)


def nav_stylesheet() -> str:
    """只作用在侧栏 QListWidget 上。"""
    sel = "rgba(255, 255, 255, 0.12)" if is_dark() else "rgba(0, 0, 0, 0.06)"
    return f"""
    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
        font-size: 13px;
        padding: 8px 0 8px 6px;
    }}
    QListWidget::item {{
        height: 32px;
        padding: 0 10px 0 8px;
        margin: 1px 8px;
        border-radius: 6px;
    }}
    QListWidget::item:selected {{
        background: {sel};
    }}
    """


def popup_stylesheet() -> str:
    """只作用在托盘弹层上（药丸按钮 / 菜单行 / DPI 滑块）。"""
    accent = accent_color().name()
    if is_dark():
        pill_bg = "rgba(255, 255, 255, 0.08)"
        menu_hover = "rgba(255, 255, 255, 0.08)"
        groove = "rgba(255, 255, 255, 0.14)"
        handle_bg = "#f5f5f7"
        handle_border = "rgba(255, 255, 255, 0.18)"
    else:
        pill_bg = "rgba(0, 0, 0, 0.05)"
        menu_hover = "rgba(0, 0, 0, 0.05)"
        groove = "rgba(0, 0, 0, 0.12)"
        handle_bg = "#ffffff"
        handle_border = "rgba(0, 0, 0, 0.12)"
    return f"""
    QPushButton#Pill {{
        border: none;
        border-radius: 6px;
        padding: 3px 8px;
        background: {pill_bg};
        font-size: 12px;
        min-height: 24px;
    }}
    QPushButton#Pill:checked {{
        background: {accent};
        color: white;
        font-weight: 600;
    }}
    QPushButton#MenuRow {{
        border: none;
        text-align: left;
        padding: 7px 10px;
        border-radius: 6px;
        font-size: 13px;
        background: transparent;
    }}
    QPushButton#MenuRow:hover {{
        background: {menu_hover};
    }}
    QSlider#DpiSlider::groove:horizontal {{
        height: 4px;
        border-radius: 2px;
        background: {groove};
    }}
    QSlider#DpiSlider::sub-page:horizontal {{
        height: 4px;
        border-radius: 2px;
        background: {accent};
    }}
    QSlider#DpiSlider::handle:horizontal {{
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
        background: {handle_bg};
        border: 1px solid {handle_border};
    }}
    """


def style_label(
    lab: QLabel,
    *,
    size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
    secondary: bool = False,
) -> QLabel:
    font = QFont(".AppleSystemUIFont", size)
    font.setWeight(weight)
    lab.setFont(font)
    if secondary:
        lab.setForegroundRole(QPalette.ColorRole.PlaceholderText)
    return lab


def popup_body_color() -> QColor:
    if is_dark():
        return QColor(36, 36, 38, 245)
    return QColor(246, 246, 246, 245)


def popup_border_color() -> QColor:
    if is_dark():
        return QColor(255, 255, 255, 28)
    return QColor(0, 0, 0, 28)


def format_hz(hz: int) -> str:
    """回报率紧凑标签：8000 → 8K。"""
    if hz >= 1000 and hz % 1000 == 0:
        return f"{hz // 1000}K"
    return str(hz)


def safe_combo(parent: QWidget | None = None) -> QComboBox:
    """避开 Cocoa QComboBox 的 NSMenu（macOS 27 / QTBUG-147449，kb/0008）。

    Fusion 弹出层由 Qt 自己画，不走 NSMenuTrackingSession。
    """
    combo = QComboBox(parent)
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        combo.setStyle(fusion)
    return combo


def wrap_scroll(page: QWidget) -> QScrollArea:
    """设置页滚动容器：无边框，跟系统设置一致。"""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setWidget(page)
    return scroll


def section_title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setContentsMargins(2, 0, 2, 2)
    return style_label(lab, size=11, weight=QFont.Weight.DemiBold, secondary=True)


def caption(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    return style_label(lab, size=11, secondary=True)


class Hairline(QWidget):
    def __init__(
        self, *, vertical: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), hairline_color())


class Card(QWidget):
    """系统设置风的圆角分组。"""

    def __init__(self, *rows: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        for i, row in enumerate(rows):
            if i:
                self._layout.addWidget(Hairline())
            self._layout.addWidget(row)

    def add_row(self, row: QWidget) -> None:
        if self._layout.count():
            self._layout.addWidget(Hairline())
        self._layout.addWidget(row)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if is_dark():
            fill = QColor(255, 255, 255, 16)
            border = QColor(255, 255, 255, 22)
        else:
            fill = QColor(255, 255, 255, 235)
            border = QColor(60, 60, 67, 31)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        painter.fillPath(path, fill)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)


def labeled_row(
    title: str,
    widget: QWidget,
    *,
    stretch_control: bool = False,
) -> QWidget:
    """左标签、右控件的设置行。"""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 7, 12, 7)
    layout.setSpacing(12)
    lab = QLabel(title)
    lab.setMinimumWidth(84)
    layout.addWidget(lab)
    if stretch_control:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(widget, 1)
    else:
        layout.addStretch()
        widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(widget)
    return row


def footer_row(button: QPushButton) -> QWidget:
    """卡片底部右对齐操作按钮。"""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.addStretch()
    layout.addWidget(button)
    return row


def page_column(*widgets: QWidget) -> QWidget:
    """设置页内容列：边距 + 分组间距 + 底部弹性空白。"""
    page = QWidget()
    page.setAutoFillBackground(False)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(20, 16, 20, 24)
    layout.setSpacing(14)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch()
    return page


class BatteryView(QWidget):
    """菜单栏/标题栏用电量胶囊。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level = 0
        self._charging = False
        self.setFixedSize(52, 16)
        self.setToolTip("电量")

    def set_battery(self, level: int, charging: bool) -> None:
        self._level = max(0, min(100, level))
        self._charging = charging
        self.setToolTip(f"电量 {self._level}%{' · 充电中' if charging else ''}")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRect(0, 3, 22, 10)
        painter.setPen(QPen(QColor(secondary_text()), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 2.5, 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(secondary_text()))
        painter.drawRoundedRect(QRect(22, 6, 2, 4), 0.8, 0.8)
        inset = QRect(2, 5, 18, 6)
        fill_w = max(1, int(inset.width() * self._level / 100)) if self._level else 0
        if self._level <= 15 and not self._charging:
            fill = QColor("#ff3b30")
        elif self._charging:
            fill = QColor("#32d74b")
        else:
            fill = accent_color()
        painter.setBrush(fill)
        painter.drawRoundedRect(
            QRect(inset.x(), inset.y(), fill_w, inset.height()), 1, 1
        )
        painter.setPen(QColor(secondary_text()))
        font = painter.font()
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(
            QRect(26, 0, 26, 16),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{self._level}%",
        )


class HeaderBar(QWidget):
    """设置窗口顶部：设备名、连接方式、电量。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        self._glyph = QLabel()
        self._glyph.setFixedSize(40, 40)
        layout.addWidget(self._glyph)

        text = QVBoxLayout()
        text.setSpacing(1)
        self._title = style_label(
            QLabel("正在读取设备…"), size=17, weight=QFont.Weight.DemiBold
        )
        self._sub = style_label(
            QLabel("请用有线或 2.4G 接收器连接鼠标"), size=11, secondary=True
        )
        text.addWidget(self._title)
        text.addWidget(self._sub)
        layout.addLayout(text, 1)

        self._battery = BatteryView()
        self._battery.hide()
        layout.addWidget(self._battery, 0, Qt.AlignmentFlag.AlignVCenter)
        self._set_glyph(muted=True)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        fill = QColor(255, 255, 255, 10) if is_dark() else QColor(0, 0, 0, 8)
        painter.fillRect(self.rect(), fill)
        painter.fillRect(
            self.rect().adjusted(0, self.height() - 1, 0, 0), hairline_color()
        )

    def _set_glyph(self, *, muted: bool) -> None:
        pix = QPixmap(40, 40)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(secondary_text()) if muted else accent_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(0, 0, 40, 40, 10, 10)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(12, 8, 16, 24, 7, 7)
        painter.setPen(QPen(fill, 1.2))
        painter.drawLine(20, 12, 20, 18)
        painter.end()
        self._glyph.setPixmap(pix)

    def set_loading(self) -> None:
        self._title.setText("正在读取设备…")
        self._sub.setText("请用有线或 2.4G 接收器连接鼠标")
        self._battery.hide()
        self._set_glyph(muted=True)

    def set_error(self, message: str) -> None:
        self._title.setText("未连接")
        self._sub.setText(message)
        self._battery.hide()
        self._set_glyph(muted=True)

    def set_device(
        self,
        title: str,
        subtitle: str,
        battery: int,
        charging: bool,
        *,
        sleeping: bool,
    ) -> None:
        self._title.setText(title)
        if sleeping:
            self._sub.setText(f"{subtitle} · 鼠标休眠，晃动后刷新")
        else:
            extra = " · 充电中" if charging else ""
            self._sub.setText(f"{subtitle}{extra}")
        self._battery.set_battery(battery, charging)
        self._battery.show()
        self._set_glyph(muted=sleeping)


class NavList(QListWidget):
    """系统设置风侧栏。"""

    def __init__(self, items: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavList")
        self.setFixedWidth(184)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSpacing(0)
        self._apply_style()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._apply_style()
        )
        for label in items:
            self.addItem(label)
        self.setCurrentRow(0)

    def _apply_style(self) -> None:
        self.setStyleSheet(nav_stylesheet())


TRAY_ICON_SIZE = 22  # 菜单栏逻辑像素
LOW_BATTERY_PERCENT = 15  # 低电量改红色、取消模板着色


def tray_icon_tooltip(battery: int | None, *, charging: bool = False) -> str:
    """菜单栏图标悬停文案。"""
    if battery is None:
        return "未连接"
    extra = " · 充电中" if charging else ""
    return f"电量 {battery}%{extra}"


def _lightning_path(box: QRectF) -> QPainterPath:
    """充电闪电（归一化折线映射到 box）。"""
    pts = (
        (0.58, 0.00),
        (0.20, 0.52),
        (0.46, 0.52),
        (0.38, 1.00),
        (0.82, 0.42),
        (0.54, 0.42),
    )
    path = QPainterPath()
    path.moveTo(box.x() + pts[0][0] * box.width(), box.y() + pts[0][1] * box.height())
    for x, y in pts[1:]:
        path.lineTo(box.x() + x * box.width(), box.y() + y * box.height())
    path.closeSubpath()
    return path


def paint_mouse_glyph(
    painter: QPainter,
    *,
    size: float,
    battery: int | None,
    charging: bool,
    color: QColor,
) -> None:
    """空心鼠标：轮廓 + 自底向上的电量填充。battery 为 None 时只描边。"""
    s = size / TRAY_ICON_SIZE
    ink = QColor(color)
    if battery is None:
        ink.setAlpha(150)
    body = QRectF(5.4 * s, 2.0 * s, 11.2 * s, 17.8 * s)
    radius = body.width() / 2
    pen_w = max(1.35 * s, 1.15)

    outline = QPainterPath()
    outline.addRoundedRect(body, radius, radius)

    inset = pen_w * 0.92
    inner = body.adjusted(inset, inset, -inset, -inset)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner, inner.width() / 2, inner.width() / 2)

    if battery is not None and battery > 0:
        level = max(0, min(100, battery))
        fill_h = max(inner.height() * level / 100, 1.3 * s)
        fill_h = min(fill_h, inner.height())
        fill_path = QPainterPath()
        fill_path.addRect(
            QRectF(inner.x(), inner.bottom() - fill_h, inner.width(), fill_h)
        )
        painter.fillPath(inner_path.intersected(fill_path), ink)

    if charging:
        bolt_box = QRectF(
            body.center().x() - 2.15 * s,
            body.center().y() - 3.5 * s,
            4.3 * s,
            7.4 * s,
        )
        bolt = _lightning_path(bolt_box)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationOut
        )
        painter.fillPath(bolt, Qt.GlobalColor.black)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(
            QPen(
                ink,
                max(0.85 * s, 0.8),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(bolt)
    else:
        painter.setPen(
            QPen(
                ink,
                max(pen_w * 0.85, 1.0),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        x = body.center().x()
        painter.drawLine(
            QPointF(x, body.top() + 3.8 * s), QPointF(x, body.top() + 7.0 * s)
        )

    painter.setPen(
        QPen(
            ink,
            pen_w,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(outline)


def render_tray_mouse(
    pixel_size: int,
    battery: int | None,
    *,
    charging: bool = False,
    color: QColor | None = None,
) -> QPixmap:
    """离屏画菜单栏鼠标（测试与 make_tray_icon 共用）。"""
    pix = QPixmap(pixel_size, pixel_size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_mouse_glyph(
        painter,
        size=float(pixel_size),
        battery=battery,
        charging=charging,
        color=color or QColor(Qt.GlobalColor.black),
    )
    painter.end()
    return pix


def make_tray_icon(battery: int | None = None, *, charging: bool = False) -> QIcon:
    """菜单栏空心鼠标。电量用内部填充表示；低电量改红色，其余为模板图标。"""
    low = battery is not None and battery <= LOW_BATTERY_PERCENT and not charging
    color = QColor("#ff3b30") if low else QColor(Qt.GlobalColor.black)
    icon = QIcon()
    for dpr in (1, 2):
        pix = render_tray_mouse(
            TRAY_ICON_SIZE * dpr, battery, charging=charging, color=color
        )
        pix.setDevicePixelRatio(dpr)
        icon.addPixmap(pix)
    icon.setIsMask(not low)
    return icon


def paint_popover(widget: QWidget, painter: QPainter) -> None:
    """自绘圆角 popover（含轻阴影），替代 NSMenu。"""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    shadow = POPUP_SHADOW
    rect = QRectF(widget.rect()).adjusted(shadow, shadow - 2, -shadow, -shadow)
    for i in range(10, 0, -1):
        path = QPainterPath()
        path.addRoundedRect(
            rect.adjusted(-i * 0.35, 1, i * 0.35, i * 0.55),
            POPUP_RADIUS + i * 0.2,
            POPUP_RADIUS + i * 0.2,
        )
        painter.fillPath(path, QColor(0, 0, 0, 2 + i))
    body = QPainterPath()
    body.addRoundedRect(rect, POPUP_RADIUS, POPUP_RADIUS)
    painter.fillPath(body, popup_body_color())
    painter.setPen(QPen(popup_border_color(), 1))
    painter.drawPath(body)


def pill_button(text: str, checked: bool) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("Pill")
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return btn


def menu_row(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("MenuRow")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setFlat(True)
    return btn


class DpiSlider(QWidget):
    """菜单栏弹层用 DPI 滑块：拖动只改显示，松手再写入当前档（kb/0005 §3.1）。"""

    value_committed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dragging = False
        self._committed: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 0, 2, 4)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(caption("DPI"))
        header.addStretch()
        self._value = style_label(QLabel("—"), size=13, weight=QFont.Weight.DemiBold)
        header.addWidget(self._value)
        root.addLayout(header)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("DpiSlider")
        self._slider.setRange(DPI_MIN, 26000)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(DPI_STEP)
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.sliderPressed.connect(self._on_pressed)
        self._slider.sliderReleased.connect(self._on_released)
        self._slider.valueChanged.connect(self._on_changed)
        root.addWidget(self._slider)

    def set_limits(self, dpi_max: int) -> None:
        self._slider.setRange(DPI_MIN, dpi_max)

    def set_dpi(self, value: int) -> None:
        """回灌设备当前值；拖动中忽略，避免把正在调的滑块拽回去。"""
        if self._dragging:
            return
        clamped = clamp_dpi(value, self._slider.maximum())
        self._committed = clamped
        self._slider.blockSignals(True)
        self._slider.setValue(clamped)
        self._slider.blockSignals(False)
        self._value.setText(str(clamped))

    def _on_pressed(self) -> None:
        self._dragging = True

    def _on_changed(self, value: int) -> None:
        self._value.setText(str(value))

    def _on_released(self) -> None:
        self._dragging = False
        clamped = clamp_dpi(self._slider.value(), self._slider.maximum())
        self._slider.blockSignals(True)
        self._slider.setValue(clamped)
        self._slider.blockSignals(False)
        self._value.setText(str(clamped))
        if clamped != self._committed:
            self._committed = clamped
            self.value_committed.emit(clamped)
