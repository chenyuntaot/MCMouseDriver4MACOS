"""迈从鼠标设备注册表与能力矩阵。

数据来源：kb/devices/0002（VID/PID 与角色）、kb/0003 §6 与 kb/0004（能力表）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceVariant:
    """一个型号的一个 VID/PID 组合（角色划分见 kb/0002）。"""

    model: str  # 型号名，如 "MCHOSE A7 V2 Pro+"
    vid: int
    pid: int
    role: str  # wired | receiver-1k | receiver-8k（kb/0002 PID 角色表）
    protocol: str  # old（kb/0003）| new（kb/0004）
    rate_table: str  # protocol.old.RATE_TABLES 的键（kb/0005 §3.2）


# 见 kb/devices/0002 的 A7 系列全量表与 PID 角色表
KNOWN_VARIANTS: tuple[DeviceVariant, ...] = (
    # A7 V2 Pro+（旧协议；pids = [有线, 1K 接收器, 8K 接收器, 8K(VID 21075)]）
    DeviceVariant("MCHOSE A7 V2 Pro+", 14391, 16419, "wired", "old", "8k"),
    DeviceVariant("MCHOSE A7 V2 Pro+", 14391, 4106, "receiver-1k", "old", "1k"),
    DeviceVariant("MCHOSE A7 V2 Pro+", 14391, 4107, "receiver-8k", "old", "8k"),
    DeviceVariant("MCHOSE A7 V2 Pro+", 21075, 4128, "receiver-8k", "old", "8k"),
    # A7 V2 Ultra+（旧协议）
    DeviceVariant("MCHOSE A7 V2 Ultra+", 14391, 16417, "wired", "old", "8k"),
    DeviceVariant("MCHOSE A7 V2 Ultra+", 14391, 4106, "receiver-1k", "old", "1k"),
    DeviceVariant("MCHOSE A7 V2 Ultra+", 14391, 4107, "receiver-8k", "old", "8k"),
    DeviceVariant("MCHOSE A7 V2 Ultra+", 21075, 4128, "receiver-8k", "old", "8k"),
    # A7 V3 Pro+（新协议）
    DeviceVariant("MCHOSE A7 V3 Pro+", 14391, 16434, "wired", "new", "8k"),
    DeviceVariant("MCHOSE A7 V3 Pro+", 14391, 4116, "receiver-8k", "new", "8k"),
    DeviceVariant("MCHOSE A7 V3 Pro+", 14391, 4120, "receiver-8k", "new", "8k"),
    # A7 V3 Ultra+（新协议）
    DeviceVariant("MCHOSE A7 V3 Ultra+", 14391, 16435, "wired", "new", "8k"),
    DeviceVariant("MCHOSE A7 V3 Ultra+", 14391, 4116, "receiver-8k", "new", "8k"),
    DeviceVariant("MCHOSE A7 V3 Ultra+", 14391, 4120, "receiver-8k", "new", "8k"),
)

# 迈从相关 VID（十进制），用于枚举时宽匹配，见 kb/0002
MCHOSE_VIDS: frozenset[int] = frozenset({14391, 21075})


@dataclass(frozen=True)
class ModelCaps:
    """型号能力矩阵。"""

    dpi_max: int
    default_dpis: tuple[int, ...]  # 出厂 6 档 DPI
    lod_labels: dict[int, str]  # sensor 字节 LOD 值 → 显示文本（kb/0005 §4）


MODEL_CAPS: dict[str, ModelCaps] = {
    # kb/0003 §6（Xf 表）
    "MCHOSE A7 V2 Pro+": ModelCaps(
        26000, (200, 1200, 2200, 3200, 4200, 26000), {1: "1mm", 2: "2mm"}
    ),
    "MCHOSE A7 V2 Ultra+": ModelCaps(
        42000,
        (200, 1200, 2200, 3200, 4200, 42000),  # 末档=dpiMax 为按 Kr 表模式推断，待验证
        {0: "0.7mm", 1: "1mm", 2: "2mm"},
    ),
    # kb/0004 V3 能力表（默认 DPI 表 CYt：400/800/1600/3200/6400/max）
    "MCHOSE A7 V3 Pro+": ModelCaps(
        42000, (400, 800, 1600, 3200, 6400, 42000), {0: "0.7mm", 1: "1mm", 2: "2mm"}
    ),
    "MCHOSE A7 V3 Ultra+": ModelCaps(
        50000,
        (400, 800, 1600, 3200, 6400, 50000),
        {},  # 5 档 LOD 走独立命令，kb/0004
    ),
}
