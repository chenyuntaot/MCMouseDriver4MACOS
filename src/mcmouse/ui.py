"""macOS 原生观感：色板、卡片、侧栏、电量与托盘图标。

不全局覆盖 QPushButton/QComboBox/QSpinBox，以免丢掉 Cocoa 原生控件。
只给自定义容器（卡片、侧栏、弹层药丸按钮）上样式。
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
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
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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
    """只作用在托盘弹层上（药丸按钮 / 菜单行）。"""
    accent = accent_color().name()
    if is_dark():
        pill_bg = "rgba(255, 255, 255, 0.08)"
        menu_hover = "rgba(255, 255, 255, 0.08)"
    else:
        pill_bg = "rgba(0, 0, 0, 0.05)"
        menu_hover = "rgba(0, 0, 0, 0.05)"
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


def make_tray_icon() -> QIcon:
    """菜单栏模板图标：鼠标剪影，随菜单栏深浅自动反色。"""
    pix = QPixmap(22, 22)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(Qt.GlobalColor.black, 1.3))
    painter.setBrush(Qt.GlobalColor.black)
    path = QPainterPath()
    path.addRoundedRect(QRectF(5.5, 3.5, 11, 15.5), 5.5, 5.5)
    painter.drawPath(path)
    painter.setPen(QPen(Qt.GlobalColor.white, 1.2))
    painter.drawLine(11, 6, 11, 10)
    painter.end()
    icon = QIcon(pix)
    icon.setIsMask(True)
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
