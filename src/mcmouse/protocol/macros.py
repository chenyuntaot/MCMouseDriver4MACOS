"""旧协议宏下发（kb/0006 §2，RH() 77771-77858 + 双固件真机校准）。

线上字节规则（kb/0007 §7）：
- 包头（12/6 字节）：逻辑值 XOR 0xFF（与 build_command 相同）。
- 事件（4 字节定长）：**编码随固件而异**——官方 bundle 与新固件（5.42.2.4）
  要求"预取反"；旧固件 5.42.0.9 要求逻辑原形（且该固件宏引擎不触发）。
  构造器默认取反，可用 `inverted=False` 生成逻辑原形；
  `OldProtocolSession.write_macro` 会写后读回（0x65）自动探测并重试。
- 每包填充至 64 字节（0xFF）。
"""

from __future__ import annotations

from .old import REPORT_ID_LONG, build_command

CMD_WRITE_MACRO = 0x55  # 写宏数据（reportId 0x12）
CMD_WRITE_MACRO_NAME = 0x53  # 写宏名（reportId 0x12）
CMD_READ_MACRO = 0x65  # 读宏数据（reportId 0x12，官方弃用但固件支持）

# 触发方式（condition u16，kb/0006 §2.1）
TRIGGER_MODES: dict[str, int] = {
    "hold-loop": 0x2001,  # 按住时循环
    "until-same-key": 0x4001,  # 循环至相同键按下
    "once": 0x0001,  # 执行一次
    "until-any-key": 0x6001,  # 循环至任意键按下
}

FIRST_HEADER_LEN = 12  # 首包头长
CONT_HEADER_LEN = 6  # 续包头长
FIRST_EVENT_CAP = 52  # 首包事件容量（字节）
CONT_EVENT_CAP = 58  # 续包事件容量（字节）
PACKET_SIZE = 64

# 鼠标键位掩码（kb/0006 §2.2）
MOUSE_BITS: dict[str, int] = {
    "left": 0x01,
    "right": 0x02,
    "middle": 0x04,
    "back": 0x08,
    "forward": 0x10,
}


def _wire(logical: bytes, inverted: bool) -> bytes:
    """逻辑事件 → 线上形式（inverted=True 时逐字节取反，kb/0007 §7）。"""
    return bytes(b ^ 0xFF for b in logical) if inverted else logical


def ev_key(usage: int, down: bool, inverted: bool = True) -> bytes:
    """键盘事件：[00, 81 按下 / 01 释放, usage, 00]。"""
    return _wire(bytes([0x00, 0x81 if down else 0x01, usage, 0x00]), inverted)


def ev_delay(ms: int, inverted: bool = True) -> bytes:
    """延迟事件：[00, 0F, msLo, msHi]。范围 1-60000。"""
    if not 1 <= ms <= 60000:
        raise ValueError("延迟需在 1-60000ms 之间")
    return _wire(bytes([0x00, 0x0F, *ms.to_bytes(2, "little")]), inverted)


def ev_mouse(bit: int, down: bool, inverted: bool = True) -> bytes:
    """鼠标键事件：[00, 88 按下 / 08 释放, 按钮位, 00]。

    取反时第 4 字节保留官方怪癖发 0x00（RH() 77790-77797 原样）。
    """
    if not inverted:
        return bytes([0x00, 0x88 if down else 0x08, bit, 0x00])
    return bytes([0xFF, (0x88 if down else 0x08) ^ 0xFF, bit ^ 0xFF, 0x00])


def ev_wheel(up: bool, inverted: bool = True) -> bytes:
    """滚轮事件：[00, 05, 01 上 / FF 下, 00]（第 4 字节怪癖同 ev_mouse）。"""
    if not inverted:
        return bytes([0x00, 0x05, 0x01 if up else 0xFF, 0x00])
    return bytes([0xFF, 0x05 ^ 0xFF, (0x01 if up else 0xFF) ^ 0xFF, 0x00])


def _xor(data: bytes) -> bytes:
    return bytes(b ^ 0xFF for b in data)


def build_macro_packets(
    button_index: int, events: list[bytes], condition: int
) -> list[bytes]:
    """构造宏数据分包（每条含 reportId 0x12，64 字节，可直接发送）。

    首包 12 字节头（kb/0006 §2.1，取反发送）：[0x55, buttonIndex, moreData,
    offset u16LE, length, trigger=1, condition u16LE, time u16LE=0, count=事件数]；
    续包 6 字节头，offset 每次 +58，末包 moreData=0、length=剩余事件字节数+6；
    单包 moreData=0、length=58。事件按逻辑原形直接拼接（kb/0007 §7）。
    """
    for e in events:
        if len(e) != 4:
            raise ValueError("事件必须为 4 字节")
    blob = b"".join(events)
    count = len(events)
    packets: list[bytes] = []

    def header12(more: int) -> bytes:
        return _xor(
            bytes(
                [
                    CMD_WRITE_MACRO,
                    button_index,
                    more,
                    0,
                    0,  # offset u16 LE，首包=0
                    58,  # length，官方常量
                    1,  # trigger 固定 1
                    *condition.to_bytes(2, "little"),
                    0,
                    0,  # time u16 LE=0
                    count,
                ]
            )
        )

    if len(blob) <= FIRST_EVENT_CAP:
        packets.append(header12(0) + blob)
    else:
        packets.append(header12(1) + blob[:FIRST_EVENT_CAP])
        pos = FIRST_EVENT_CAP
        offset = 0
        while pos < len(blob):
            chunk = blob[pos : pos + CONT_EVENT_CAP]
            offset += CONT_EVENT_CAP
            more = 1 if pos + CONT_EVENT_CAP < len(blob) else 0
            length = CONT_EVENT_CAP if more else len(chunk) + CONT_HEADER_LEN
            cont = bytes(
                [
                    CMD_WRITE_MACRO,
                    button_index,
                    more,
                    *offset.to_bytes(2, "little"),
                    length,
                ]
            )
            packets.append(_xor(cont) + chunk)
            pos += CONT_EVENT_CAP

    return [bytes([REPORT_ID_LONG]) + p.ljust(PACKET_SIZE, b"\xff") for p in packets]


def build_macro_name(button_index: int, name: str) -> tuple[int, bytes]:
    """写宏名命令（0x12 0x53）：[0x53, buttonIndex, nameSize, UTF-8…]。"""
    encoded = name.encode("utf-8")
    if len(encoded) > 50:
        raise ValueError("宏名过长")
    return REPORT_ID_LONG, build_command(
        REPORT_ID_LONG,
        CMD_WRITE_MACRO_NAME,
        bytes([button_index, len(encoded)]) + encoded,
    )


def build_read_macro(button_index: int, part: int = 0) -> tuple[int, bytes]:
    """读宏数据命令（0x12 0x65 <buttonIndex> <part>）。

    官方 bundle 中无调用点（死代码），但本机固件支持（kb/0007 §7）。
    响应布局（parser Pwt 76369）：[buttonIndex, moreData, offset u16, length,
    trigger, condition u16, time u16, count, 事件×52（逻辑原形）]。
    """
    return REPORT_ID_LONG, build_command(
        REPORT_ID_LONG, CMD_READ_MACRO, bytes([button_index, part])
    )


def parse_events_dsl(dsl: str, key_tokens: dict[str, int]) -> list[bytes]:
    """解析宏事件 DSL，返回逻辑形式事件列表（供 write_macro 使用）。

    语法（逗号分隔）：`a` 点按、`+a`/`-a` 按下/释放、`delay:50` 延迟 ms、
    `mouse:left` 点按鼠标键、`+mouse:left`/`-mouse:left` 按下/释放、
    `wheel:up`/`wheel:down` 滚轮。key_tokens 为键名 → HID usage 表。
    """
    events: list[bytes] = []
    for token in dsl.split(","):
        token = token.strip().lower()
        if not token:
            continue
        down_up = None
        if token[0] in "+-":
            down_up = token[0] == "+"
            token = token[1:]
        if token.startswith("delay:") and down_up is None:
            events.append(ev_delay(int(token[6:]), inverted=False))
        elif token.startswith("mouse:") and token[6:] in MOUSE_BITS:
            bit = MOUSE_BITS[token[6:]]
            if down_up is None:
                events += [ev_mouse(bit, True, False), ev_mouse(bit, False, False)]
            else:
                events.append(ev_mouse(bit, down_up, False))
        elif (
            token.startswith("wheel:")
            and down_up is None
            and token[6:] in ("up", "down")
        ):
            events.append(ev_wheel(token[6:] == "up", inverted=False))
        elif token in key_tokens:
            usage = key_tokens[token]
            if down_up is None:
                events += [ev_key(usage, True, False), ev_key(usage, False, False)]
            else:
                events.append(ev_key(usage, down_up, False))
        else:
            raise ValueError(f"无法解析的事件: {token}")
    if not events:
        raise ValueError("宏至少需要一个事件")
    return events
