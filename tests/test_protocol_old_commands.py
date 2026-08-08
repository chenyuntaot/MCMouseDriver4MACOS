"""旧协议功能命令的离线测试（布局依据 kb/0005，向量为人工构造）。"""

from __future__ import annotations

import pytest

from mcmouse.protocol import old


def _make_response(report_id: int, subcmd: int, payload: bytes) -> bytes:
    """构造一条线上响应 buffer：[reportId][取反(子命令+payload)]。"""
    return bytes([report_id]) + old.encode(bytes([subcmd]) + payload)


# 人工构造的 63 字节配置数据（kb/0005 §2 布局）
CONFIG_PAYLOAD = (
    bytes([0x00])  # profileIndex
    + bytes([0x32])  # gDpiIndex=3, gRateIndex=2
    + bytes([0x21])  # usbDpiIndex=2, usbRateIndex=1
    + bytes([0x00])  # reserved
    + b"".join(d.to_bytes(2, "little") for d in (400, 800, 1600, 3200, 6400, 26000))
    + bytes([0x06])  # dpiSum
    + bytes([0x15])  # sensor：lod=1, ripple=1, line=0, motionSync=1, 电竞=0
    + bytes([0x04])  # keyDebounce
    + bytes([0x0A])  # sleep 10 分钟
    + bytes([0x10, 0x01, 0x00, 0x00])  # 键0：type=1 index=0 value=0x010000
    + bytes([0x20, 0x02, 0x00, 0x00])  # 键1
    + bytes([0x00, 0x00, 0x00, 0x00])  # 键2
    + bytes([0x00, 0x00, 0x00, 0x00])  # 键3
    + bytes([0x01, 0x04, 0x00, 0x00])  # 键4：type=0 index=1
    + bytes([0x00, 0x00, 0x00, 0x00])  # 键5
    + bytes(5)  # reserved1-5
    + bytes([0x02])  # rotateVal=2 → 8°
    + bytes([0xFF])  # val
    + b"".join(d.to_bytes(2, "little") for d in (400, 800, 1600, 3200, 6400, 26000))
)


def test_parse_config() -> None:
    _, subcmd, payload = old.parse_response(
        _make_response(old.REPORT_ID_LONG, old.CMD_READ_CONFIG, CONFIG_PAYLOAD)
    )
    assert subcmd == old.CMD_READ_CONFIG
    cfg = old.parse_config(payload)
    assert cfg.profile_index == 0
    assert cfg.g_dpi_index == 3
    assert cfg.g_rate_index == 2
    assert cfg.usb_dpi_index == 2
    assert cfg.usb_rate_index == 1
    assert cfg.dpis == (400, 800, 1600, 3200, 6400, 26000)
    assert cfg.dpi_count == 6
    assert old.sensor_lod(cfg.sensor) == 1
    assert old.sensor_ripple(cfg.sensor) is True
    assert old.sensor_line(cfg.sensor) is False
    assert old.sensor_motion_sync(cfg.sensor) is True
    assert old.sensor_game_mode(cfg.sensor) == 0
    assert cfg.key_debounce == 4
    assert cfg.sleep_minutes == 10
    assert cfg.buttons[0] == old.ButtonBinding(
        button_type=1, button_index=0, value=0x010000
    )
    assert cfg.buttons[1] == old.ButtonBinding(
        button_type=2, button_index=0, value=0x020000
    )
    assert cfg.buttons[4] == old.ButtonBinding(
        button_type=0, button_index=1, value=0x040000
    )
    assert cfg.rotate_degrees == 8
    assert cfg.val == 0xFF
    assert cfg.dpi_vals == cfg.dpis


def test_parse_device_info() -> None:
    payload = (
        (0x3837).to_bytes(2, "little")
        + (0x100A).to_bytes(2, "little")
        + (0x00051509).to_bytes(4, "little")
        + bytes(
            [0b0000_1001]
        )  # connectMode=1(2.4G), connectStatus=1（LSB 读法，kb/0007）
        + bytes([85])  # 电量
        + bytes([1])  # 充电中
    )
    _, subcmd, data = old.parse_response(
        _make_response(old.REPORT_ID_SHORT, old.CMD_READ_DEVICE_INFO, payload)
    )
    assert subcmd == old.CMD_READ_DEVICE_INFO
    info = old.parse_device_info(data)
    assert info.vid == 0x3837
    assert info.pid == 0x100A
    assert info.connect_mode == 1
    assert info.connect_status == 1
    assert info.battery_level == 85
    assert info.charge_status == 1


def _decode(report_id_payload: tuple[int, bytes]) -> bytes:
    """把构造好的线上 payload 还原为逻辑字节（含子命令）。"""
    return old.decode(report_id_payload[1])


def test_build_write_dpi() -> None:
    report_id, payload = old.build_write_dpi(2, (400, 800, 1600, 3200, 6400, 26000), 6)
    assert report_id == old.REPORT_ID_LONG
    raw = _decode((report_id, payload))
    assert raw[0] == old.CMD_WRITE_DPI
    assert raw[1] == 2 and raw[2] == 2  # usb/g 索引同值
    assert int.from_bytes(raw[4:6], "little") == 400
    assert int.from_bytes(raw[14:16], "little") == 26000
    assert raw[16] == 6  # sum
    assert raw[17] == 0xFF  # diff 固定 255
    assert int.from_bytes(raw[18:20], "little") == 400  # Y 轴复制 X


def test_build_write_dpi_reject_bad_length() -> None:
    with pytest.raises(ValueError):
        old.build_write_dpi(0, (800, 1600), 2)


def test_build_write_rate() -> None:
    assert _decode(old.build_write_rate(2, wired=True))[:3] == bytes([0x41, 2, 0])
    assert _decode(old.build_write_rate(1, wired=False))[:3] == bytes([0x41, 0, 1])


def test_build_write_sensor() -> None:
    raw = _decode(
        old.build_write_sensor(
            lod=1,
            ripple=old.SWITCH_ON,
            line=old.SWITCH_OFF,
            motion_sync=old.SWITCH_ON,
            game_mode=2,
        )
    )
    assert raw[:10] == bytes([0x42, 1, 1, 2, 1, 0, 0, 2, 0, 0])


def test_build_misc_writes() -> None:
    assert _decode(old.build_write_sleep(True, 15))[:3] == bytes([0x0A, 1, 15])
    assert _decode(old.build_write_sleep(False, 0))[:3] == bytes([0x0A, 0, 0])
    assert _decode(old.build_write_debounce(8))[:2] == bytes([0x43, 8])
    assert _decode(old.build_switch_profile(1))[:2] == bytes([0x58, 1])
    assert _decode(old.build_factory_reset())[:3] == bytes([0x0B, 0xAA, 0x00])
