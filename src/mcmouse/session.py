"""旧协议会话：命令-应答往返（kb/0003 §5）。

官方流程是"发命令 → 等 input report 通知 → receiveFeatureReport 取数据"，
这里简化为"发命令 → 轮询 get_feature_report 并匹配子命令回显"，
读路径真机已验证（kb/0002 实机记录 2）。
"""

from __future__ import annotations

import time

import hid

from .protocol.old import (
    CMD_READ_CONFIG,
    CMD_READ_DEVICE_INFO,
    CMD_READ_FIRMWARE,
    PAYLOAD_SIZES,
    DeviceInfo,
    MouseConfig,
    build_read_config,
    build_read_device_info,
    build_read_firmware,
    build_write_dpi,
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
