"""设置面板：官方 HUB 风格左栏 + 顶栏四标签。只组装任务交给 DeviceWorker。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .hub.buttons_page import ButtonsPage
from .hub.dpi_page import DpiPage
from .hub.other_page import OtherPage
from .hub.performance_page import PerformancePage
from .hub.sidebar import Sidebar
from .hub.theme import window_stylesheet
from .hub.widgets import HubTabBar

Submit = Callable[..., None]

_TABS = (
    ("mouse", "按键配置"),
    ("dpi", "DPI 设置"),
    ("perf", "性能设置"),
    ("other", "其他设置"),
)


def _scroll(page: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setWidget(page)
    return scroll


class Panel(QMainWindow):
    """HUB 风格设置窗口。关闭不退出菜单栏应用。"""

    def __init__(self, submit: Submit) -> None:
        super().__init__()
        self._submit = submit
        self._snapshot = None
        self._updating = False
        self.setWindowTitle("MCMouseDriver")
        self.resize(1080, 720)
        self.setMinimumSize(960, 640)

        self._sidebar = Sidebar(self._emit)
        self._dpi = DpiPage(self._emit)
        self._buttons = ButtonsPage(self._emit)
        self._perf = PerformancePage(self._emit)
        self._other = OtherPage(self._emit)
        self._pages = (self._buttons, self._dpi, self._perf, self._other)

        self._tabs = HubTabBar(list(_TABS))
        self._tabs.setObjectName("HubTabs")
        self._stack = QStackedWidget()
        self._stack.addWidget(_scroll(self._buttons))
        self._stack.addWidget(_scroll(self._dpi))
        self._stack.addWidget(_scroll(self._perf))
        self._stack.addWidget(_scroll(self._other))
        self._tabs.currentChanged.connect(self._stack.setCurrentIndex)

        main = QWidget()
        main.setObjectName("HubMain")
        main_l = QVBoxLayout(main)
        main_l.setContentsMargins(0, 0, 0, 0)
        main_l.setSpacing(0)
        main_l.addWidget(self._tabs)
        main_l.addWidget(self._stack, 1)

        root = QWidget()
        root.setObjectName("HubRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(main, 1)
        self.setCentralWidget(root)
        self._apply_style()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._apply_style()
        )

    def _apply_style(self) -> None:
        self.setStyleSheet(window_stylesheet())

    def _emit(self, *task: object) -> None:
        if self._updating:
            return
        snap = self._snapshot
        sleeping = snap is None or getattr(snap, "config", None) is None
        if sleeping and task[0] != "factory_reset":
            return
        self._submit(*task)

    def set_updating(self, updating: bool) -> None:
        self._updating = updating
        self._sidebar.set_updating(updating)
        for page in self._pages:
            page.set_updating(updating)

    def show_error(self, message: str) -> None:
        self._sidebar.show_error(message)
        self._other.show_error(message)

    def on_snapshot(self, snap) -> None:  # noqa: ANN001 - 避免与 gui 循环导入
        self._snapshot = snap
        self.setWindowTitle(snap.variant.model.replace("MCHOSE ", ""))
        self.set_updating(True)
        try:
            self._sidebar.on_snapshot(snap)
            self._dpi.on_snapshot(snap)
            self._buttons.on_snapshot(snap)
            self._perf.on_snapshot(snap)
            self._other.on_snapshot(snap)
        finally:
            self.set_updating(False)
