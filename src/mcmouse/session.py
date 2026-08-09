"""旧协议会话：命令-应答往返（kb/0003 §5）。

官方流程是"发命令 → 等 input report 通知 → receiveFeatureReport 取数据"，
这里简化为"发命令 → 轮询 get_feature_report 并匹配子命令回显"，
读路径真机已验证（kb/0002 实机记录 2）。
"""

from __future__ import annotations

import time

import hid

from .protocol.buttons import build_write_button
from .protocol.macros import (
    CMD_READ_MACRO,
    CMD_WRITE_MACRO,
    CMD_WRITE_MACRO_NAME,
    CONT_HEADER_LEN,
    build_macro_name,
    build_macro_packets,
    build_read_macro,
)
from .protocol.old import (
    CMD_READ_CONFIG,
    CMD_READ_DEVICE_INFO,
    CMD_READ_FIRMWARE,
    PAYLOAD_SIZES,
    REPORT_ID_LONG,
    DeviceInfo,
    MouseConfig,
    build_read_config,
    build_read_device_info,
    build_read_firmware,
    build_write_debounce,
    build_write_dpi,
    build_write_rate,
    build_write_sensor_from_config,
    build_write_sleep,
    parse_config,
    parse_device_info,
    parse_firmware_version,
    parse_response,
)
from .transport import HidInterface, open_interface

RETRY_COUNT = 5  # 官方读重试上限同为 5（kb/0003 §5）
RETRY_INTERVAL_S = 0.05
WAKE_ROUNDS = 4  # 鼠标休眠时整轮重试次数（kb/0007 §3）
WAKE_INTERVAL_S = 0.5


class OldProtocolSession:
    """一个已打开的旧协议配置接口上的会话。用 close() 或 with 释放。"""

    def __init__(self, dev: hid.device) -> None:
        self._dev = dev

    @classmethod
    def open(cls, iface: HidInterface) -> OldProtocolSession:
        return cls(open_interface(iface))

    def close(self) -> None:
        self._dev.close()

    def __enter__(self) -> OldProtocolSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def query(self, report_id: int, payload: bytes, expect_subcmd: int) -> bytes:
        """发送命令并等待匹配的子命令回显，返回数据段（已解码、去回显）。"""
        self._dev.send_feature_report(bytes([report_id]) + payload)
        for _ in range(RETRY_COUNT):
            time.sleep(RETRY_INTERVAL_S)
            buf = bytes(
                self._dev.get_feature_report(report_id, 1 + PAYLOAD_SIZES[report_id])
            )
            _, subcmd, data = parse_response(buf)
            if subcmd == expect_subcmd:
                return data
        raise TimeoutError(
            f"子命令 0x{expect_subcmd:02x} 重试 {RETRY_COUNT} 次无匹配响应"
        )

    def send_write(self, report_id: int, payload: bytes) -> None:
        """发送写命令（不等待回显；写确认靠后续读回比对，kb/0005 §3）。

        官方流程的写确认走 input report 的 0x1A 通知（kb/0003 §5），
        这里简化为发送后由调用方读回验证。
        """
        self._dev.send_feature_report(bytes([report_id]) + payload)
        time.sleep(RETRY_INTERVAL_S)

    def wait_ack(self, subcmd: int, timeout_s: float = 1.0) -> bool:
        """等待写命令的 0x1A 应答（reportId 0x13，kb/0003 §5）。

        应答格式：[0x13, 0x1A, subcmd^0xFF, ...]。宏等多包写入必须逐包等应答。
        """
        self._dev.set_nonblocking(1)
        try:
            deadline = time.monotonic() + timeout_s
            expect = subcmd ^ 0xFF
            while time.monotonic() < deadline:
                buf = bytes(self._dev.read(64))
                if len(buf) >= 3 and buf[1] == 0x1A and buf[2] == expect:
                    return True
                time.sleep(0.01)
            return False
        finally:
            self._dev.set_nonblocking(0)

    def write_dpi(self, cfg: MouseConfig, wired: bool) -> None:
        """把 cfg 中的 DPI 整表写入设备（0x12 0x40，kb/0005 §3.1）。"""
        if cfg.dpi_count == 0 or not any(cfg.dpis):
            # 防呆：休眠鼠标会读到全零配置（kb/0007 §3），绝不允许写回
            raise ValueError("拒绝写入空 DPI 表（疑似休眠读到的零配置，kb/0007）")
        dpi_index = cfg.usb_dpi_index if wired else cfg.g_dpi_index
        report_id, payload = build_write_dpi(
            dpi_index, cfg.dpis, cfg.dpi_count, cfg.dpi_vals
        )
        self.send_write(report_id, payload)

    def write_rate(self, rate_index: int, wired: bool) -> None:
        """写回报率档位索引（0x11 0x41，kb/0005 §3.2）。"""
        report_id, payload = build_write_rate(rate_index, wired)
        self.send_write(report_id, payload)

    def write_sensor(
        self,
        cfg: MouseConfig,
        *,
        lod: int | None = None,
        ripple: bool | None = None,
        line: bool | None = None,
        motion_sync: bool | None = None,
        game_mode: int | None = None,
    ) -> None:
        """以 cfg 为底覆盖指定项写性能参数（0x11 0x42，kb/0005 §3.3）。"""
        report_id, payload = build_write_sensor_from_config(
            cfg,
            lod=lod,
            ripple=ripple,
            line=line,
            motion_sync=motion_sync,
            game_mode=game_mode,
        )
        self.send_write(report_id, payload)

    def write_sleep(self, minutes: int) -> None:
        """写休眠时间（0x11 0x0A，kb/0005 §3.4）。minutes=0 表示从不休眠。"""
        report_id, payload = build_write_sleep(minutes > 0, minutes)
        self.send_write(report_id, payload)

    def write_debounce(self, value: int) -> None:
        """写按键防抖（0x11 0x43，kb/0005 §3.4）。"""
        report_id, payload = build_write_debounce(value)
        self.send_write(report_id, payload)

    def write_button(self, button_index: int, button_type: int, value: int) -> None:
        """写单键映射（0x12 0x52，kb/0006 §1.3）。"""
        report_id, payload = build_write_button(button_index, button_type, value)
        self.send_write(report_id, payload)

    def write_macro(
        self,
        button_index: int,
        events_logical: list[bytes],
        condition: int,
        name: str,
    ) -> None:
        """下发宏到按键槽（0x12 0x55 分包 + 0x12 0x53 宏名，kb/0006 §2）。

        events_logical 为逻辑形式事件（ev_*(..., inverted=False)）。
        事件线上编码随固件而异（kb/0007 §7）：先按官方/新固件的"预取反"写，
        读回（0x65）无事件则改用逻辑原形重写。逐包等 0x1A 应答。
        注意：调用方必须先写绑定（0x52 会清槽），本函数之后不能再发 0x52。
        """

        def write_data(inverted: bool) -> int:
            wire = [
                bytes(b ^ 0xFF for b in e) if inverted else e for e in events_logical
            ]
            for packet in build_macro_packets(button_index, wire, condition):
                self._dev.send_feature_report(packet)  # packet 已含 reportId
                if not self.wait_ack(CMD_WRITE_MACRO):
                    raise TimeoutError("宏数据包无应答")
            _, payload = build_read_macro(button_index, 0)
            data = self.query(REPORT_ID_LONG, payload, CMD_READ_MACRO)
            return data[4]  # length：>6 表示事件已入槽（kb/0007 §7）

        if write_data(inverted=True) <= CONT_HEADER_LEN:
            if write_data(inverted=False) <= CONT_HEADER_LEN:
                raise RuntimeError("宏事件未存入（两种编码均被设备拒绝）")

        report_id, payload = build_macro_name(button_index, name)
        self._dev.send_feature_report(bytes([report_id]) + payload)
        if not self.wait_ack(CMD_WRITE_MACRO_NAME):
            raise TimeoutError("宏名包无应答")

    def read_firmware(self) -> str:
        report_id, payload = build_read_firmware()
        return parse_firmware_version(self.query(report_id, payload, CMD_READ_FIRMWARE))

    def read_device_info(self) -> DeviceInfo:
        report_id, payload = build_read_device_info()
        for round_ in range(WAKE_ROUNDS):
            info = parse_device_info(
                self.query(report_id, payload, CMD_READ_DEVICE_INFO)
            )
            if info.vid != 0:
                return info
            if round_ < WAKE_ROUNDS - 1:
                time.sleep(WAKE_INTERVAL_S)  # 等鼠标唤醒，kb/0007 §3
        return info

    def read_config(self) -> MouseConfig:
        report_id, payload = build_read_config()
        for round_ in range(WAKE_ROUNDS):
            cfg = parse_config(self.query(report_id, payload, CMD_READ_CONFIG))
            if cfg.dpi_count > 0:
                return cfg
            if round_ < WAKE_ROUNDS - 1:
                time.sleep(WAKE_INTERVAL_S)  # 等鼠标唤醒，kb/0007 §3
        return cfg
