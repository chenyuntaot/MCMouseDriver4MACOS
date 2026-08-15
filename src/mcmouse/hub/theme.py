"""HUB 设置窗口色板与窗口级样式。浅色对齐官方截图，深色跟随系统。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QWidget

from ..ui import is_dark

# DPI 档位色点（官方六档：红 / 蓝 / 绿 / 金 / 青 / 紫）
DPI_STAGE_COLORS: tuple[str, ...] = (
    "#EF4444",
    "#3B82F6",
    "#22C55E",
    "#EAB308",
    "#06B6D4",
    "#A855F7",
)

GAME_MODE_LABELS: tuple[str, ...] = ("性能模式", "电竞模式", "超竞模式")

ROLE_NAMES: dict[str, str] = {
    "wired": "有线",
    "receiver-1k": "2.4G",
    "receiver-8k": "2.4G",
}

PHYSICAL_BUTTON_NAMES: dict[int, str] = {
    0: "左键",
    1: "中键",
    2: "右键",
    3: "前进键",
    4: "后退键",
    5: "DPI 键",
}


@dataclass(frozen=True)
class HubPalette:
    bg: str
    sidebar: str
    card: str
    accent: str
    accent_soft: str
    text: str
    muted: str
    border: str
    input_bg: str
    danger: str
    shadow: QColor


def palette() -> HubPalette:
    """当前外观下的 HUB 色板。"""
    if is_dark():
        return HubPalette(
            bg="#1c1c1e",
            sidebar="#232326",
            card="#2c2c2e",
            accent="#3B82F6",
            accent_soft="#1e3a5f",
            text="#f5f5f7",
            muted="#98989d",
            border="rgba(255,255,255,0.10)",
            input_bg="#3a3a3c",
            danger="#ff453a",
            shadow=QColor(0, 0, 0, 90),
        )
    return HubPalette(
        bg="#F3F4F6",
        sidebar="#EEF0F5",
        card="#FFFFFF",
        accent="#3B82F6",
        accent_soft="#E8F1FF",
        text="#1F2937",
        muted="#6B7280",
        border="rgba(15,23,42,0.08)",
        input_bg="#F8FAFC",
        danger="#EF4444",
        shadow=QColor(15, 23, 42, 28),
    )


def hub_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(".AppleSystemUIFont", size)
    font.setWeight(weight)
    return font


def apply_hub_font(
    widget: QWidget,
    size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> None:
    widget.setFont(hub_font(size, weight))


def window_stylesheet() -> str:
    """只作用在设置窗口上，不污染托盘弹层。"""
    p = palette()
    return f"""
    QWidget#HubRoot {{
        background: {p.bg};
        color: {p.text};
    }}
    QWidget#HubSidebar {{
        background: {p.sidebar};
    }}
    QWidget#HubMain {{
        background: {p.bg};
    }}
    QLineEdit, QSpinBox {{
        background: {p.input_bg};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 4px 8px;
        min-height: 28px;
        selection-background-color: {p.accent};
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """
