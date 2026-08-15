"""键盘键编码（旧协议 type=2，kb/0006 §1.2）。

value 三字节 BE：`[修饰键掩码, HID Usage ID, 0x00]`。
修饰掩码为标准 HID：bit0 LCtrl、bit1 LShift、bit2 LAlt、bit3 LGUI。
"""

from __future__ import annotations

from .buttons import HID_USAGE_NAMES, MOD_BITS

BUTTON_TYPE_KEYBOARD = 2  # kb/0006 §1.2 type=2


def encode_keyboard(mod_mask: int, usage: int) -> int:
    """组装 type=2 的 buttonValue。Ctrl+A → 0x010400。"""
    if not 0 <= mod_mask <= 0xFF:
        raise ValueError("mod_mask 为 1 字节")
    if not 0 <= usage <= 0xFF:
        raise ValueError("usage 为 1 字节")
    return (mod_mask << 16) | (usage << 8)


def decode_keyboard(value: int) -> tuple[int, int]:
    """buttonValue → (mod_mask, usage)。"""
    return (value >> 16) & 0xFF, (value >> 8) & 0xFF


def keyboard_label(
    mod_mask: int,
    usage: int,
    *,
    alt_name: str = "Alt",
    gui_name: str = "Win",
) -> str:
    """给人看的键名，如 Ctrl+Shift+A。"""
    names = []
    for bit, name in MOD_BITS:
        label = name
        if bit == 0x04:
            label = alt_name
        elif bit == 0x08:
            label = gui_name
        if mod_mask & bit:
            names.append(label)
    if usage == 0:
        return "+".join(names) if names else "未命名"
    names.append(HID_USAGE_NAMES.get(usage, f"0x{usage:02x}"))
    return "+".join(names)
