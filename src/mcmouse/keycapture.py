"""从 Qt 键盘事件解析 HID 键盘绑定（kb/0006 §1.2 type=2）。

键码表来自 USB HID Usage Tables，不是官方软件素材。
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .protocol.keyboard import (
    BUTTON_TYPE_KEYBOARD,
    encode_keyboard,
    keyboard_label,
)

# Qt.Key → HID keyboard usage ID（未列出的键无法录制）
_QT_TO_USAGE: dict[int, int] = {
    **{int(Qt.Key.Key_A) + i: 0x04 + i for i in range(26)},
    int(Qt.Key.Key_1): 0x1E,
    int(Qt.Key.Key_2): 0x1F,
    int(Qt.Key.Key_3): 0x20,
    int(Qt.Key.Key_4): 0x21,
    int(Qt.Key.Key_5): 0x22,
    int(Qt.Key.Key_6): 0x23,
    int(Qt.Key.Key_7): 0x24,
    int(Qt.Key.Key_8): 0x25,
    int(Qt.Key.Key_9): 0x26,
    int(Qt.Key.Key_0): 0x27,
    int(Qt.Key.Key_Return): 0x28,
    int(Qt.Key.Key_Enter): 0x58,
    int(Qt.Key.Key_Escape): 0x29,
    int(Qt.Key.Key_Backspace): 0x2A,
    int(Qt.Key.Key_Tab): 0x2B,
    int(Qt.Key.Key_Space): 0x2C,
    int(Qt.Key.Key_Minus): 0x2D,
    int(Qt.Key.Key_Equal): 0x2E,
    int(Qt.Key.Key_BracketLeft): 0x2F,
    int(Qt.Key.Key_BracketRight): 0x30,
    int(Qt.Key.Key_Backslash): 0x31,
    int(Qt.Key.Key_Semicolon): 0x33,
    int(Qt.Key.Key_Apostrophe): 0x34,
    int(Qt.Key.Key_QuoteLeft): 0x35,
    int(Qt.Key.Key_Comma): 0x36,
    int(Qt.Key.Key_Period): 0x37,
    int(Qt.Key.Key_Slash): 0x38,
    int(Qt.Key.Key_CapsLock): 0x39,
    **{int(Qt.Key.Key_F1) + i: 0x3A + i for i in range(12)},
    int(Qt.Key.Key_Print): 0x46,
    int(Qt.Key.Key_ScrollLock): 0x47,
    int(Qt.Key.Key_Pause): 0x48,
    int(Qt.Key.Key_Insert): 0x49,
    int(Qt.Key.Key_Home): 0x4A,
    int(Qt.Key.Key_PageUp): 0x4B,
    int(Qt.Key.Key_Delete): 0x4C,
    int(Qt.Key.Key_End): 0x4D,
    int(Qt.Key.Key_PageDown): 0x4E,
    int(Qt.Key.Key_Right): 0x4F,
    int(Qt.Key.Key_Left): 0x50,
    int(Qt.Key.Key_Down): 0x51,
    int(Qt.Key.Key_Up): 0x52,
    int(Qt.Key.Key_NumLock): 0x53,
}

_NUMPAD_USAGE: dict[int, int] = {
    int(Qt.Key.Key_0): 0x62,
    int(Qt.Key.Key_1): 0x59,
    int(Qt.Key.Key_2): 0x5A,
    int(Qt.Key.Key_3): 0x5B,
    int(Qt.Key.Key_4): 0x5C,
    int(Qt.Key.Key_5): 0x5D,
    int(Qt.Key.Key_6): 0x5E,
    int(Qt.Key.Key_7): 0x5F,
    int(Qt.Key.Key_8): 0x60,
    int(Qt.Key.Key_9): 0x61,
    int(Qt.Key.Key_Period): 0x63,
    int(Qt.Key.Key_Slash): 0x54,
    int(Qt.Key.Key_Asterisk): 0x55,
    int(Qt.Key.Key_Minus): 0x56,
    int(Qt.Key.Key_Plus): 0x57,
    int(Qt.Key.Key_Enter): 0x58,
}

_MODIFIER_KEYS = frozenset(
    {
        int(Qt.Key.Key_Control),
        int(Qt.Key.Key_Shift),
        int(Qt.Key.Key_Alt),
        int(Qt.Key.Key_Meta),
        int(Qt.Key.Key_AltGr),
    }
)

# 单独修饰键 → HID Left/Right modifier usage（0xE0-0xE7，kb/0006 §1.2）
_MODIFIER_USAGE: dict[int, int] = {
    int(Qt.Key.Key_Control): 0xE0,
    int(Qt.Key.Key_Shift): 0xE1,
    int(Qt.Key.Key_Alt): 0xE2,
    int(Qt.Key.Key_Meta): 0xE3,
    int(Qt.Key.Key_AltGr): 0xE6,
}

_MODIFIER_OWN_BIT: dict[int, int] = {
    int(Qt.Key.Key_Control): 0x01,
    int(Qt.Key.Key_Shift): 0x02,
    int(Qt.Key.Key_Alt): 0x04,
    int(Qt.Key.Key_Meta): 0x08,
    int(Qt.Key.Key_AltGr): 0x04,
}


def _mod_mask(modifiers: Qt.KeyboardModifier) -> int:
    mask = 0
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        mask |= 0x01
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        mask |= 0x02
    if modifiers & Qt.KeyboardModifier.AltModifier:
        mask |= 0x04
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        mask |= 0x08
    return mask


def binding_from_qt(
    qt_key: int,
    modifiers: Qt.KeyboardModifier,
    *,
    keypad: bool = False,
) -> tuple[int, int, str] | None:
    """Qt 键码 → (button_type, value, 显示名)。无法识别时返回 None。"""
    if qt_key in _MODIFIER_KEYS:
        return None
    usage = _NUMPAD_USAGE.get(qt_key) if keypad else None
    if usage is None:
        usage = _QT_TO_USAGE.get(qt_key)
    if usage is None:
        return None
    mods = _mod_mask(modifiers)
    value = encode_keyboard(mods, usage)
    label = keyboard_label(mods, usage, alt_name="Option", gui_name="Cmd")
    return BUTTON_TYPE_KEYBOARD, value, label


def binding_from_modifier_keys(qt_keys: frozenset[int]) -> tuple[int, int, str] | None:
    """单独修饰键或修饰键和弦 → type=2 绑定。

    单键用 HID usage 0xE0-0xE7、掩码 0（固件把 usage 0 当无键）；
    多键和弦写入修饰掩码、usage 0。见 kb/0006 §1.2。
    """
    usages: list[int] = []
    mask = 0
    for key in qt_keys:
        usage = _MODIFIER_USAGE.get(key)
        if usage is None:
            continue
        usages.append(usage)
        mask |= _MODIFIER_OWN_BIT.get(key, 0)
    if not usages:
        return None
    if len(usages) == 1:
        value = encode_keyboard(0, usages[0])
        mods, usage = 0, usages[0]
    else:
        value = encode_keyboard(mask, 0)
        mods, usage = mask, 0
    label = keyboard_label(mods, usage, alt_name="Option", gui_name="Cmd")
    return BUTTON_TYPE_KEYBOARD, value, label


def _activate_cocoa_app() -> None:
    """菜单栏 accessory 进程默认不抢焦点，录制前必须显式激活。"""
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls = objc.objc_getClass(b"NSApplication")
        nsapp = objc.objc_msgSend(cls, objc.sel_registerName(b"sharedApplication"))
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        objc.objc_msgSend(
            nsapp, objc.sel_registerName(b"activateIgnoringOtherApps:"), 1
        )
    except Exception:  # noqa: BLE001
        pass


class KeyCaptureDialog(QDialog):
    """拦截下一次键盘输入；Esc 或「取消」退出。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加键盘按键")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(360, 180)
        self.captured: tuple[int, int, str] | None = None
        self._mod_down: set[int] = set()
        self._mod_chord: set[int] = set()
        self._hint = QLabel(
            "请按下要添加的键。Shift / Ctrl / Option / Cmd "
            "松开后即保存；也可再按字母组成组合键。\n"
            "不要点鼠标。Esc 或下方按钮取消。"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._hint)
        layout.addWidget(cancel, 0, Qt.AlignmentFlag.AlignCenter)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _activate_cocoa_app()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._arm)

    def _arm(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.grabKeyboard()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def done(self, result: int) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.releaseKeyboard()
        super().done(result)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: ARG002
        if event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        ) and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                self._on_key(event)
            else:
                self._on_key_release(event)
            return True
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._on_key(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._on_key_release(event)

    def _on_key(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat() or self.captured is not None:
            return
        key = int(event.key())
        mods = event.modifiers()
        if key == int(Qt.Key.Key_Escape) and not (
            mods
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            self.reject()
            return
        if key in _MODIFIER_KEYS:
            self._mod_down.add(key)
            self._mod_chord.add(key)
            pending = binding_from_modifier_keys(frozenset(self._mod_chord))
            name = pending[2] if pending is not None else "修饰键"
            self._hint.setText(f"松开即保存 {name}，或再按一个键组成组合键")
            return
        keypad = bool(mods & Qt.KeyboardModifier.KeypadModifier)
        decoded = binding_from_qt(key, mods, keypad=keypad)
        if decoded is None:
            self._hint.setText("无法识别该键，请换一个，或按 Esc 取消")
            return
        self._mod_down.clear()
        self._mod_chord.clear()
        self.captured = decoded
        self.accept()

    def _on_key_release(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat() or self.captured is not None:
            return
        key = int(event.key())
        if key not in _MODIFIER_KEYS:
            return
        self._mod_down.discard(key)
        if self._mod_down or not self._mod_chord:
            return
        decoded = binding_from_modifier_keys(frozenset(self._mod_chord))
        self._mod_chord.clear()
        if decoded is None:
            return
        self.captured = decoded
        self.accept()
