"""旧协议帧编解码的离线测试（依据 kb/0003，测试向量来自 kb/0002 实机记录）。"""

from __future__ import annotations

from mcmouse.protocol import old

# kb/0002 实机记录 2：get_feature_report(1) 返回的前 11 字节
LIVE_FW_RESPONSE = bytes(
    [0x01, 0xFB, 0xF7, 0xCA, 0xD1, 0xCE, 0xCA, 0xD1, 0xCF, 0xD1, 0xC6]
    + [0xFF] * 53  # 其余字节填充 0xFF
)


def test_encode_decode_roundtrip() -> None:
    raw = bytes([0x04, 0x00, 0xAB, 0xFF])
    assert old.decode(old.encode(raw)) == raw


def test_build_command_layout() -> None:
    # 0x11 0x04 读固件版本：子命令取反 = 0xFB，填充 0x00 取反 = 0xFF，共 20 字节
    payload = old.build_command(old.REPORT_ID_SHORT, old.CMD_READ_FIRMWARE)
    assert len(payload) == 20
    assert payload[0] == 0xFB
    assert payload[1:] == b"\xff" * 19


def test_build_command_reject_overflow() -> None:
    import pytest

    with pytest.raises(ValueError):
        old.build_command(old.REPORT_ID_SHORT, 0x04, b"\x00" * 20)


def test_parse_response_live_capture() -> None:
    report_id, subcmd, payload = old.parse_response(LIVE_FW_RESPONSE)
    assert report_id == 0x01  # reportId 原始值不取反
    assert subcmd == old.CMD_READ_FIRMWARE  # 0xFB 取反 = 0x04
    assert old.parse_firmware_version(payload) == "5.15.0.9"


def test_build_read_firmware() -> None:
    report_id, payload = old.build_read_firmware()
    assert report_id == old.REPORT_ID_SHORT
    assert len(payload) == old.PAYLOAD_SIZES[old.REPORT_ID_SHORT]
