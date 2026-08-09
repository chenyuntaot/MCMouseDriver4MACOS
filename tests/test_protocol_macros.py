"""宏下发的离线测试（依据 kb/0006 §2 + kb/0007 §7 真机校准）。"""

from __future__ import annotations

import pytest

from mcmouse.protocol import macros


def test_event_wire_forms() -> None:
    # 默认取反（官方/新固件形态）
    assert macros.ev_key(0x04, down=True) == bytes([0xFF, 0x7E, 0xFB, 0xFF])
    assert macros.ev_key(0x04, down=False) == bytes([0xFF, 0xFE, 0xFB, 0xFF])
    assert macros.ev_delay(50) == bytes([0xFF, 0xF0, 0xCD, 0xFF])
    assert macros.ev_mouse(0x01, down=True) == bytes([0xFF, 0x77, 0xFE, 0x00])
    assert macros.ev_mouse(0x01, down=False) == bytes([0xFF, 0xF7, 0xFE, 0x00])
    assert macros.ev_wheel(up=True) == bytes([0xFF, 0xFA, 0xFE, 0x00])
    assert macros.ev_wheel(up=False) == bytes([0xFF, 0xFA, 0x00, 0x00])
    # 逻辑原形（旧固件形态）
    assert macros.ev_key(0x04, down=True, inverted=False) == bytes(
        [0x00, 0x81, 0x04, 0x00]
    )
    assert macros.ev_delay(50, inverted=False) == bytes([0x00, 0x0F, 0x32, 0x00])
    assert macros.ev_mouse(0x01, down=True, inverted=False) == bytes(
        [0x00, 0x88, 0x01, 0x00]
    )
    assert macros.ev_wheel(up=True, inverted=False) == bytes([0x00, 0x05, 0x01, 0x00])


def test_ev_delay_range() -> None:
    with pytest.raises(ValueError):
        macros.ev_delay(0)
    with pytest.raises(ValueError):
        macros.ev_delay(60001)


def test_single_packet_layout() -> None:
    packets = macros.build_macro_packets(
        4, [macros.ev_key(0x04, True)], macros.TRIGGER_MODES["once"]
    )
    assert len(packets) == 1
    pkt = packets[0]
    assert len(pkt) == 65  # reportId + 64
    assert pkt[0] == 0x12
    # 12 字节头取反：[55,04,00,00,00,3A,01,01,00,00,00,01]^FF
    assert pkt[1:13] == bytes(
        [0xAA, 0xFB, 0xFF, 0xFF, 0xFF, 0xC5, 0xFE, 0xFE, 0xFF, 0xFF, 0xFF, 0xFE]
    )
    # 事件默认取反（官方/新固件形态）
    assert pkt[13:17] == bytes([0xFF, 0x7E, 0xFB, 0xFF])
    assert pkt[17:] == b"\xff" * 48  # 填充


def test_multi_packet_chunking() -> None:
    # 14 个事件 = 56 字节 > 52 → 两包
    events = [macros.ev_key(0x04, True)] * 14
    packets = macros.build_macro_packets(1, events, macros.TRIGGER_MODES["once"])
    assert len(packets) == 2
    first, last = packets
    assert first[1] == 0x55 ^ 0xFF
    assert first[2] == 0x01 ^ 0xFF  # buttonIndex=1
    assert first[3] == 0x01 ^ 0xFF  # moreData=1
    # 续包 6 字节头取反：[55,01,00(more),3A,00(offset=58),0A(length=4+6)]^FF
    assert last[1] == 0x55 ^ 0xFF
    assert last[2] == 0x01 ^ 0xFF
    assert last[3] == 0x00 ^ 0xFF  # moreData=0
    assert last[4:6] == bytes([58 ^ 0xFF, 0x00 ^ 0xFF])  # offset=58
    assert last[6] == 0x0A ^ 0xFF  # length=10
    # 续包事件 = 第 14 个事件（默认取反形态）
    assert last[7:11] == macros.ev_key(0x04, True)


def test_macro_name() -> None:
    report_id, payload = macros.build_macro_name(2, "测试宏")
    assert report_id == 0x12
    from mcmouse.protocol.old import decode

    raw = decode(payload)
    assert raw[0] == 0x53
    assert raw[1] == 2  # buttonIndex
    assert raw[2] == 9  # "测试宏" UTF-8 9 字节
    assert raw[3:12].decode("utf-8") == "测试宏"


def test_macro_name_too_long() -> None:
    with pytest.raises(ValueError):
        macros.build_macro_name(0, "x" * 60)


def test_build_read_macro() -> None:
    report_id, payload = macros.build_read_macro(4, 0)
    assert report_id == 0x12
    from mcmouse.protocol.old import decode

    raw = decode(payload)
    assert raw[:3] == bytes([0x65, 0x04, 0x00])
