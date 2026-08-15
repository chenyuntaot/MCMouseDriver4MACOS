"""按键配置页：可搜索功能列表 + 自绘鼠标 + 宏 / 录制键。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import custom_keys
from ..keycapture import KeyCaptureDialog
from ..protocol.buttons import BUTTON_PRESETS, HID_USAGE_NAMES, describe_button
from ..protocol.macros import TRIGGER_MODES, parse_events_dsl
from .theme import PHYSICAL_BUTTON_NAMES, apply_hub_font, palette
from .widgets import (
    GhostButton,
    HubCard,
    PrimaryButton,
    RadioPills,
    SecondaryButton,
    muted_label,
)

Submit = Callable[..., None]

_KEY_TOKENS: dict[str, int] = {v.lower(): k for k, v in HID_USAGE_NAMES.items()}
_KEY_TOKENS.update({"up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4F})

TRIGGER_LABELS: dict[str, str] = {
    "once": "执行一次",
    "hold-loop": "按住时循环",
    "until-same-key": "循环至相同键",
    "until-any-key": "循环至任意键",
}

TAB_LABELS = ("全部", "系统按键", "键盘按键", "快捷键", "快捷指令")


@dataclass(frozen=True)
class FuncItem:
    category: str  # all filter key
    group: str
    label: str
    button_type: int
    value: int


def catalog() -> list[FuncItem]:
    return [
        FuncItem("mouse", "鼠标", "左键", *BUTTON_PRESETS["left"]),
        FuncItem("mouse", "鼠标", "右键", *BUTTON_PRESETS["right"]),
        FuncItem("mouse", "鼠标", "中键", *BUTTON_PRESETS["middle"]),
        FuncItem("mouse", "鼠标", "前进", *BUTTON_PRESETS["forward"]),
        FuncItem("mouse", "鼠标", "后退", *BUTTON_PRESETS["back"]),
        FuncItem("mouse", "鼠标", "滚轮上", *BUTTON_PRESETS["wheel-up"]),
        FuncItem("mouse", "鼠标", "滚轮下", *BUTTON_PRESETS["wheel-down"]),
        FuncItem("system", "系统功能", "亮度 +", 8, 0x0C6F00),
        FuncItem("system", "系统功能", "亮度 −", 8, 0x0C7000),
        FuncItem("system", "系统功能", "复制", 8, 0x070106),
        FuncItem("system", "系统功能", "剪切", 8, 0x07011B),
        FuncItem("system", "系统功能", "粘贴", 8, 0x070119),
        FuncItem("keys", "键盘", "Ctrl", *BUTTON_PRESETS["ctrl"]),
        FuncItem("keys", "键盘", "Shift", *BUTTON_PRESETS["shift"]),
        FuncItem("keys", "键盘", "Option", *BUTTON_PRESETS["option"]),
        FuncItem("keys", "键盘", "Cmd", *BUTTON_PRESETS["cmd"]),
        FuncItem("shortcut", "DPI", "DPI 切换", *BUTTON_PRESETS["dpi-switch"]),
        FuncItem("shortcut", "DPI", "DPI +", *BUTTON_PRESETS["dpi-plus"]),
        FuncItem("shortcut", "DPI", "DPI −", *BUTTON_PRESETS["dpi-minus"]),
        FuncItem("shortcut", "媒体", "音量 +", *BUTTON_PRESETS["volume-up"]),
        FuncItem("shortcut", "媒体", "音量 −", *BUTTON_PRESETS["volume-down"]),
        FuncItem("shortcut", "媒体", "静音", *BUTTON_PRESETS["mute"]),
        FuncItem("shortcut", "媒体", "播放/暂停", *BUTTON_PRESETS["play-pause"]),
        FuncItem("onboard", "板载配置", "板载配置 1", 10, 0x010000),
        FuncItem("onboard", "板载配置", "板载配置 2", 10, 0x020000),
        FuncItem("onboard", "板载配置", "板载配置 3", 10, 0x030000),
        FuncItem("onboard", "板载配置", "板载循环切换", 10, 0x040000),
        FuncItem("command", "快捷指令", "默认", *BUTTON_PRESETS["default"]),
        FuncItem("command", "快捷指令", "禁用", *BUTTON_PRESETS["disable"]),
    ]


_TAB_FILTER: dict[int, frozenset[str] | None] = {
    0: None,
    1: frozenset({"system"}),
    2: frozenset({"keys"}),
    3: frozenset({"shortcut", "onboard"}),
    4: frozenset({"command"}),
}


class _FuncRow(QPushButton):
    def __init__(self, item: FuncItem, current: bool = False) -> None:
        super().__init__(item.label)
        self.item = item
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        apply_hub_font(
            self, 13, QFont.Weight.DemiBold if current else QFont.Weight.Normal
        )
        p = palette()
        bg = p.accent_soft if current else "transparent"
        fg = p.accent if current else p.text
        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                padding: 8px 10px;
                border: none;
                border-radius: 8px;
                background: {bg};
                color: {fg};
            }}
            QPushButton:hover {{ background: {p.accent_soft}; }}
            """
        )


class _AssignRow(QFrame):
    """右栏一行：物理键名 + 当前功能，点击即选中该键。"""

    clicked = Signal(int)

    def __init__(self, index: int, name: str) -> None:
        super().__init__()
        self.index = index
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)
        self._name = QLabel(name)
        apply_hub_font(self._name, 13, QFont.Weight.DemiBold)
        self._func = QLabel("—")
        apply_hub_font(self._func, 13)
        self._func.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._name, 0)
        layout.addStretch(1)
        layout.addWidget(self._func, 0)
        self._restyle()

    def set_function(self, text: str) -> None:
        self._func.setText(text)

    def set_selected(self, selected: bool) -> None:  # noqa: FBT001
        if selected == self._selected:
            return
        self._selected = selected
        self._restyle()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def _restyle(self) -> None:
        p = palette()
        bg = p.accent_soft if self._selected else p.input_bg
        border = p.accent if self._selected else p.border
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {border};"
            f" border-radius: 10px; }}"
        )
        name_color = p.accent if self._selected else p.text
        self._name.setStyleSheet(f"color: {name_color}; border: none;")
        self._func.setStyleSheet(f"color: {p.muted}; border: none;")


class MacroDialog(QDialog):
    """板载宏 DSL 编辑。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("写入宏")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.events: list[bytes] | None = None
        self.condition = TRIGGER_MODES["once"]
        self.macro_name = "我的宏"
        layout = QVBoxLayout(self)
        layout.addWidget(muted_label("触发方式"))
        self._mode = RadioPills()
        self._mode_keys = [k for k in TRIGGER_LABELS if k in TRIGGER_MODES]
        self._mode.set_items([TRIGGER_LABELS[k] for k in self._mode_keys], 0)
        layout.addWidget(self._mode)
        layout.addWidget(muted_label("宏名"))
        self._name = QLineEdit("我的宏")
        layout.addWidget(self._name)
        layout.addWidget(
            muted_label("事件（逗号分隔）：a 点按、+a/−a、delay:50、mouse:left")
        )
        self._dsl = QLineEdit()
        self._dsl.setPlaceholderText("+ctrl,+c,-c,-ctrl")
        layout.addWidget(self._dsl)
        row = QHBoxLayout()
        row.addStretch()
        cancel = SecondaryButton("取消")
        cancel.clicked.connect(self.reject)
        ok = PrimaryButton("写入")
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addLayout(row)

    def _accept(self) -> None:
        idx = max(0, self._mode.index())
        key = self._mode_keys[idx]
        try:
            events = parse_events_dsl(self._dsl.text(), _KEY_TOKENS)
        except ValueError as exc:
            QMessageBox.warning(self, "宏事件错误", str(exc))
            return
        self.events = events
        self.condition = TRIGGER_MODES[key]
        self.macro_name = self._name.text().strip() or "macro"
        self.accept()


class ButtonsPage(QWidget):
    def __init__(self, submit: Submit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._submit = submit
        self._updating = False
        self._selected = 0
        self._bindings: list[tuple[int, int]] = [(0, 0)] * 6
        self.setObjectName("ButtonsPage")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)

        left = HubCard()
        left.setMinimumWidth(300)
        left.setMaximumWidth(360)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(14, 14, 14, 14)
        left_l.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索功能")
        self._search.setObjectName("ButtonSearch")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(32)
        apply_hub_font(self._search, 13)
        p0 = palette()
        self._search.setStyleSheet(
            f"""
            QLineEdit {{
                border: 1px solid {p0.border};
                border-radius: 8px;
                padding: 0 10px;
                background: {p0.input_bg};
                color: {p0.text};
            }}
            QLineEdit:focus {{ border-color: {p0.accent}; }}
            """
        )
        self._search.textChanged.connect(self._rebuild_list)
        left_l.addWidget(self._search)

        tabs = QHBoxLayout()
        tabs.setSpacing(4)
        self._tab_btns: list[QPushButton] = []
        self._tab = 0
        for i, label in enumerate(TAB_LABELS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            apply_hub_font(btn, 11)
            btn.clicked.connect(lambda _=False, i=i: self._set_tab(i))
            tabs.addWidget(btn)
            self._tab_btns.append(btn)
        tabs.addStretch()
        left_l.addLayout(tabs)

        self._list_host = QVBoxLayout()
        self._list_host.setContentsMargins(0, 0, 4, 0)
        self._list_host.setSpacing(2)
        scroll_inner = QWidget()
        scroll_inner.setLayout(self._list_host)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scroll_inner)
        scroll.setStyleSheet(
            f"""
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p0.border};
                border-radius: 4px;
                min-height: 32px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )
        left_l.addWidget(scroll, 1)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(8)
        add_key = SecondaryButton("添加键盘按键")
        add_key.setObjectName("AddKeyboard")
        add_key.clicked.connect(self._add_keyboard)
        macro_btn = SecondaryButton("写入宏")
        macro_btn.setObjectName("WriteMacro")
        macro_btn.clicked.connect(self._write_macro)
        cap_row.addWidget(add_key)
        cap_row.addWidget(macro_btn)
        left_l.addLayout(cap_row)

        right = HubCard()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(18, 16, 18, 16)
        right_l.setSpacing(8)
        head = QLabel("按键分配")
        apply_hub_font(head, 15, QFont.Weight.DemiBold)
        right_l.addWidget(head)
        right_l.addWidget(muted_label("先选中一个按键，再从左侧列表点选要写入的功能"))
        right_l.addSpacing(4)

        self._rows: list[_AssignRow] = []
        for i in range(6):
            row = _AssignRow(i, PHYSICAL_BUTTON_NAMES.get(i, f"键{i}"))
            row.clicked.connect(self._on_select_button)
            right_l.addWidget(row)
            self._rows.append(row)
        right_l.addStretch(1)

        restore = GhostButton("全部恢复默认")
        restore.setObjectName("ButtonsRestore")
        restore.clicked.connect(self._restore_all)
        right_l.addWidget(restore, 0, Qt.AlignmentFlag.AlignRight)

        root.addWidget(left, 0)
        root.addWidget(right, 1)
        self._rebuild_list()
        self._sync_tab_style()
        self._sync_rows()

    def set_updating(self, updating: bool) -> None:
        self._updating = updating

    def selected_button(self) -> int:
        return self._selected

    def select_button(self, index: int) -> None:
        self._on_select_button(index)

    def assign(self, button_type: int, value: int) -> None:
        """测试与列表点击共用。"""
        if self._updating:
            return
        self._submit("button", self._selected, button_type, value)

    def on_snapshot(self, snap) -> None:  # noqa: ANN001
        cfg = snap.config
        if cfg is None:
            return
        self._bindings = []
        for i, b in enumerate(cfg.buttons):
            name = describe_button(b)
            # type=0 表示保持出厂功能，标注成「默认（物理键名）」更好读
            physical = PHYSICAL_BUTTON_NAMES.get(i, f"键{i}")
            self._rows[i].set_function(
                f"默认（{physical}）" if name == "默认" else name
            )
            self._bindings.append((b.button_type, b.value))
        self._sync_rows()
        self._rebuild_list()

    def _sync_rows(self) -> None:
        for i, row in enumerate(self._rows):
            row.set_selected(i == self._selected)

    def _set_tab(self, index: int) -> None:
        self._tab = index
        self._sync_tab_style()
        self._rebuild_list()

    def _sync_tab_style(self) -> None:
        p = palette()
        for i, btn in enumerate(self._tab_btns):
            color = p.accent if i == self._tab else p.muted
            btn.setChecked(i == self._tab)
            btn.setStyleSheet(
                f"QPushButton {{ color: {color}; border: none; padding: 4px 3px; }}"
            )

    def _rebuild_list(self) -> None:
        while self._list_host.count():
            item = self._list_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        query = self._search.text().strip().lower()
        allowed = _TAB_FILTER[self._tab]
        bound = (
            self._bindings[self._selected]
            if self._selected < len(self._bindings)
            else (-1, -1)
        )
        items = list(catalog())
        for extra in custom_keys.load_custom_keys():
            items.append(
                FuncItem("keys", "自定义", extra.label, extra.button_type, extra.value)
            )
        current_group = None
        for item in items:
            if allowed is not None and item.category not in allowed:
                continue
            if query and (
                query not in item.label.lower() and query not in item.group.lower()
            ):
                continue
            if item.group != current_group:
                current_group = item.group
                head = QLabel(item.group)
                apply_hub_font(head, 11, QFont.Weight.DemiBold)
                p = palette()
                head.setStyleSheet(f"color: {p.muted}; padding: 8px 8px 2px;")
                self._list_host.addWidget(head)
            row = _FuncRow(item, current=(item.button_type, item.value) == bound)
            row.clicked.connect(
                lambda _=False, it=item: self.assign(it.button_type, it.value)
            )
            self._list_host.addWidget(row)
        self._list_host.addStretch()

    def _on_select_button(self, index: int) -> None:
        self._selected = max(0, min(5, index))
        self._sync_rows()
        self._rebuild_list()

    def _add_keyboard(self) -> None:
        dlg = KeyCaptureDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.captured is None:
            return
        button_type, value, label = dlg.captured
        custom_keys.add_custom_key(label, button_type, value)
        self._rebuild_list()
        self.assign(button_type, value)

    def _write_macro(self) -> None:
        dlg = MacroDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.events is None:
            return
        self._submit(
            "macro",
            self._selected,
            dlg.events,
            dlg.condition,
            dlg.macro_name,
        )

    def _restore_all(self) -> None:
        if self._updating:
            return
        t, v = BUTTON_PRESETS["default"]
        for i in range(6):
            self._submit("button", i, t, v)
