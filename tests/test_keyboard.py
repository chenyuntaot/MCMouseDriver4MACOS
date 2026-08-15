"""键盘键编码与 Qt 键码映射（kb/0006 §1.2 type=2）。"""

from __future__ import annotations

from PySide6.QtCore import Qt

from mcmouse.keycapture import binding_from_modifier_keys, binding_from_qt
from mcmouse.protocol.buttons import describe_button
from mcmouse.protocol.keyboard import (
    BUTTON_TYPE_KEYBOARD,
    decode_keyboard,
    encode_keyboard,
    keyboard_label,
)
from mcmouse.protocol.old import ButtonBinding


def test_encode_ctrl_a() -> None:
    value = encode_keyboard(0x01, 0x04)
    assert value == 0x010400
    assert decode_keyboard(value) == (0x01, 0x04)
    assert keyboard_label(0x01, 0x04) == "Ctrl+A"


def test_keyboard_label_mac_names() -> None:
    assert (
        keyboard_label(0x0C, 0x06, alt_name="Option", gui_name="Cmd") == "Option+Cmd+C"
    )


def test_keyboard_label_usage_zero() -> None:
    assert keyboard_label(0x02, 0, alt_name="Option", gui_name="Cmd") == "Shift"
    assert keyboard_label(0x0A, 0, alt_name="Option", gui_name="Cmd") == "Shift+Cmd"


def test_binding_from_qt_letter() -> None:
    got = binding_from_qt(int(Qt.Key.Key_A), Qt.KeyboardModifier.NoModifier)
    assert got == (BUTTON_TYPE_KEYBOARD, 0x000400, "A")


def test_binding_from_qt_cmd_c() -> None:
    got = binding_from_qt(int(Qt.Key.Key_C), Qt.KeyboardModifier.MetaModifier)
    assert got is not None
    assert got[0] == BUTTON_TYPE_KEYBOARD
    assert got[1] == 0x080600  # LGUI + usage C
    assert got[2] == "Cmd+C"


def test_binding_from_qt_modifier_only() -> None:
    assert (
        binding_from_qt(int(Qt.Key.Key_Shift), Qt.KeyboardModifier.ShiftModifier)
        is None
    )


def test_binding_from_modifier_keys_shift() -> None:
    got = binding_from_modifier_keys(frozenset({int(Qt.Key.Key_Shift)}))
    assert got == (BUTTON_TYPE_KEYBOARD, 0x00E100, "Shift")


def test_binding_from_modifier_keys_cmd() -> None:
    got = binding_from_modifier_keys(frozenset({int(Qt.Key.Key_Meta)}))
    assert got == (BUTTON_TYPE_KEYBOARD, 0x00E300, "Cmd")


def test_binding_from_modifier_keys_option() -> None:
    got = binding_from_modifier_keys(frozenset({int(Qt.Key.Key_Alt)}))
    assert got == (BUTTON_TYPE_KEYBOARD, 0x00E200, "Option")


def test_binding_from_modifier_keys_control() -> None:
    got = binding_from_modifier_keys(frozenset({int(Qt.Key.Key_Control)}))
    assert got == (BUTTON_TYPE_KEYBOARD, 0x00E000, "Ctrl")


def test_binding_from_modifier_keys_chord() -> None:
    got = binding_from_modifier_keys(
        frozenset({int(Qt.Key.Key_Shift), int(Qt.Key.Key_Meta)})
    )
    assert got == (BUTTON_TYPE_KEYBOARD, 0x0A0000, "Shift+Cmd")


def test_describe_standalone_modifiers() -> None:
    assert describe_button(ButtonBinding(2, 0, 0x00E100)) == "Shift"
    assert describe_button(ButtonBinding(2, 0, 0x020000)) == "Shift"


def test_binding_from_qt_unknown() -> None:
    assert binding_from_qt(0x0, Qt.KeyboardModifier.NoModifier) is None
