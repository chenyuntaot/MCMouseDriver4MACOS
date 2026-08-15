"""旧协议按键映射：语义解读与写单键命令（kb/0006 §1）。

buttonType/buttonValue 编码见 kb/0006 §1.2；写单键 0x12 0x52 布局见 §1.3。
读配置（0x12 0x67）按键字节 nibble 顺序：高4位=index、低4位=type
（真机仲裁结论，kb/0007 §4，与官方 parser 声明相反）。
"""

from __future__ import annotations

from .old import REPORT_ID_LONG, ButtonBinding, build_command

CMD_WRITE_BUTTON = 0x52  # 写单键（reportId 0x12，kb/0006 §1.3）

# 物理键索引 → 名称（kb/0006 §1.1；索引 5 待查）
BUTTON_NAMES: dict[int, str] = {
    0: "左键",
    1: "中键",
    2: "右键",
    3: "前进键",
    4: "后退键",
    5: "键5",
}

# 功能类型（kb/0006 §1.2）
TYPE_NAMES: dict[int, str] = {
    0: "默认",
    1: "鼠标键",
    2: "键盘键",
    3: "多媒体",
    4: "宏",
    5: "DPI",
    7: "保留",
    8: "系统功能",
    9: "禁用",
    10: "板载切换",
}

# type=1 鼠标键：value byte0 位掩码（kb/0006 §1.2）
MOUSE_BUTTON_BITS: dict[int, str] = {
    0x01: "左键",
    0x02: "右键",
    0x04: "中键",
    0x08: "后退",
    0x10: "前进",
}

# type=3 多媒体：value byte0 = Consumer usage 低字节（kb/0006 §1.2）
MEDIA_KEYS: dict[int, str] = {
    0xE9: "音量+",
    0xEA: "音量-",
    0xE2: "静音",
    0xCD: "播放/暂停",
    0xB6: "上一曲",
    0xB5: "下一曲",
    0xB7: "停止",
}

# type=5 DPI 动作（kb/0006 §1.2）
DPI_ACTIONS: dict[int, str] = {
    0x010000: "DPI 切换",
    0x020000: "DPI+",
    0x030000: "DPI-",
}

# type=8 系统功能（kb/0006 §1.2）
SYSTEM_ACTIONS: dict[int, str] = {
    0x0C6F00: "亮度+",
    0x0C7000: "亮度-",
    0x070106: "复制",
    0x07011B: "剪切",
    0x070119: "粘贴",
}

# type=10 板载切换（kb/0006 §1.2）
PROFILE_ACTIONS: dict[int, str] = {
    0x010000: "板载配置 1",
    0x020000: "板载配置 2",
    0x030000: "板载配置 3",
    0x040000: "板载循环切换",
}

# type=2 键盘键修饰掩码（标准 HID modifier，kb/0006 §1.2）
MOD_BITS: tuple[tuple[int, str], ...] = (
    (0x01, "Ctrl"),
    (0x02, "Shift"),
    (0x04, "Alt"),
    (0x08, "Win"),
)

# 标准 HID Usage ID 常用键名子集（kb/0006 §1.2；完整表在官方 Voe 77119-77262）
HID_USAGE_NAMES: dict[int, str] = {
    **{0x04 + i: chr(ord("A") + i) for i in range(26)},  # 0x04-0x1D: A-Z
    **{0x1E + i: str((i + 1) % 10) for i in range(10)},  # 0x1E-0x27: 1-0
    0x28: "Enter",
    0x29: "Esc",
    0x2A: "Backspace",
    0x2B: "Tab",
    0x2C: "Space",
    0x39: "CapsLock",
    **{0x3A + i: f"F{i + 1}" for i in range(12)},  # 0x3A-0x45: F1-F12
    0x46: "PrintScreen",
    0x49: "Insert",
    0x4A: "Home",
    0x4B: "PageUp",
    0x4C: "Delete",
    0x4D: "End",
    0x4E: "PageDown",
    0x4F: "→",
    0x50: "←",
    0x51: "↓",
    0x52: "↑",
    0x2D: "-",
    0x2E: "=",
    0x2F: "[",
    0x30: "]",
    0x31: "\\",
    0x33: ";",
    0x34: "'",
    0x35: "`",
    0x36: ",",
    0x37: ".",
    0x38: "/",
    0x54: "Num/",
    0x55: "Num*",
    0x56: "Num-",
    0x57: "Num+",
    0x58: "NumEnter",
    **{0x59 + i: f"Num{i + 1}" for i in range(9)},  # 0x59-0x61: Num1-Num9
    0x62: "Num0",
    0x63: "Num.",
    # 单独修饰键走 HID usage 0xE0-0xE7，而不是只填修饰掩码、usage=0
    # （kb/0006 §1.2；固件把 usage 0 当「无键」）
    0xE0: "Ctrl",
    0xE1: "Shift",
    0xE2: "Option",
    0xE3: "Cmd",
    0xE4: "RCtrl",
    0xE5: "RShift",
    0xE6: "ROption",
    0xE7: "RCmd",
}

# 宏 DSL 键名 → HID usage（含方向键别名），供 parse_events_dsl 使用
KEY_TOKENS: dict[str, int] = {v.lower(): k for k, v in HID_USAGE_NAMES.items()}
KEY_TOKENS.update({"up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4F})


def describe_button(binding: ButtonBinding) -> str:
    """把按键绑定翻译成人话（kb/0006 §1.2 各表）。"""
    t, v = binding.button_type, binding.value
    if t == 0:
        return "默认"
    if t == 1:
        if v in (0x000200, 0x00FE00):
            return "滚轮上滚" if v == 0x000200 else "滚轮下滚"
        names = [name for bit, name in MOUSE_BUTTON_BITS.items() if v >> 16 & bit]
        return "+".join(names) if names else f"鼠标键 0x{v:06x}"
    if t == 2:
        mods = "+".join(name for bit, name in MOD_BITS if v >> 16 & bit)
        usage = (v >> 8) & 0xFF
        if usage == 0:
            return mods if mods else "未命名"
        key = HID_USAGE_NAMES.get(usage, f"Usage 0x{usage:02x}")
        return f"{mods}+{key}" if mods else key
    if t == 3:
        return MEDIA_KEYS.get(v >> 16, f"多媒体 0x{v:06x}")
    if t == 4:
        return "宏"
    if t == 5:
        return DPI_ACTIONS.get(v, f"DPI 0x{v:06x}")
    if t == 8:
        return SYSTEM_ACTIONS.get(v, f"系统功能 0x{v:06x}")
    if t == 9:
        return "禁用"
    if t == 10:
        return PROFILE_ACTIONS.get(v, f"板载切换 0x{v:06x}")
    return f"未知类型 {t}（0x{v:06x}）"


def build_write_button(
    button_index: int, button_type: int, value: int
) -> tuple[int, bytes]:
    """写单键命令（0x12 0x52，kb/0006 §1.3）。

    逻辑数据：[buttonIndex, reserved(0), buttonType, buttonValue(3 字节 BE)]。
    """
    if not 0 <= button_index <= 5:
        raise ValueError("button_index 需在 0-5 之间")
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError("value 为 3 字节")
    args = bytes([button_index, 0, button_type]) + value.to_bytes(3, "big")
    return REPORT_ID_LONG, build_command(REPORT_ID_LONG, CMD_WRITE_BUTTON, args)


# 常用预设（供 CLI 与 GUI 使用）：名称 → (type, value)
BUTTON_PRESETS: dict[str, tuple[int, int]] = {
    "default": (0, 0),  # 恢复默认
    "disable": (9, 0xFFFFFF),  # 禁用
    "dpi-switch": (5, 0x010000),
    "dpi-plus": (5, 0x020000),
    "dpi-minus": (5, 0x030000),
    "left": (1, 0x010000),
    "right": (1, 0x020000),
    "middle": (1, 0x040000),
    "back": (1, 0x080000),
    "forward": (1, 0x100000),
    "wheel-up": (1, 0x000200),
    "wheel-down": (1, 0x00FE00),
    "volume-up": (3, 0xE90000),
    "volume-down": (3, 0xEA0000),
    "mute": (3, 0xE20000),
    "play-pause": (3, 0xCD0000),
    "ctrl": (2, 0x00E000),  # HID Left Control 0xE0，kb/0006 §1.2
    "shift": (2, 0x00E100),  # Left Shift 0xE1
    "option": (2, 0x00E200),  # Left Alt 0xE2
    "cmd": (2, 0x00E300),  # Left GUI 0xE3
}
