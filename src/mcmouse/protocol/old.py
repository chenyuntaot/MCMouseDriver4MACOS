"""旧协议（Feature Report + XOR 0xFF）报文编解码。

适用范围：A7 / A7 V2 全系等旧型号（A7 V3 起为新协议，见 kb/0004）。
帧格式、命令字、编码规则的依据均为 kb/protocol/0003（下称 kb/0003）。
"""

from __future__ import annotations

from dataclasses import dataclass

# --- 帧格式常量，kb/0003 §1 ---
REPORT_ID_SHORT = 0x11  # 短包 reportId，payload 20 字节
REPORT_ID_LONG = 0x12  # 长包 reportId，payload 64 字节
PAYLOAD_SIZES: dict[int, int] = {REPORT_ID_SHORT: 20, REPORT_ID_LONG: 64}

XOR_MASK = 0xFF  # payload 逐字节取反，kb/0003 §2（真机互证）

# --- 读命令子命令字，kb/0003 §3 ---
CMD_READ_BOND = 0x03  # 读绑定信息
CMD_READ_FIRMWARE = 0x04  # 读固件版本
CMD_READ_DEVICE_INFO = 0x06  # 读设备信息（含电量）
CMD_READ_CONFIG = 0x67  # 读整份配置（reportId 0x12）
CMD_READ_LIGHT = 0x1B  # 读灯光

# --- 写命令子命令字，kb/0005 §3 ---
CMD_WRITE_DPI = 0x40  # 写 DPI 整表（reportId 0x12）
CMD_WRITE_RATE = 0x41  # 写回报率
CMD_WRITE_SENSOR = 0x42  # 写性能参数（LOD/波纹/直线/MotionSync/电竞/旋转）
CMD_WRITE_SLEEP = 0x0A  # 写休眠
CMD_WRITE_DEBOUNCE = 0x43  # 写按键防抖
CMD_SWITCH_PROFILE = 0x58  # 切板载配置
CMD_FACTORY_RESET = 0x0B  # 恢复出厂设置


def encode(payload: bytes) -> bytes:
    """payload 逐字节 XOR 0xFF（kb/0003 §2）。"""
    return bytes(b ^ XOR_MASK for b in payload)


def decode(data: bytes) -> bytes:
    """接收侧解码，与 encode 同（XOR 自反）。"""
    return bytes(b ^ XOR_MASK for b in data)


def build_command(report_id: int, subcmd: int, args: bytes = b"") -> bytes:
    """构造命令 payload（不含 reportId 字节，已取反、已按包长填充）。

    布局（kb/0003 §3/§4）：[子命令][参数…][0x00 填充至包长]，整体取反后发送，
    故线上字节填充位为 0xFF。读命令与写命令同构。
    """
    size = PAYLOAD_SIZES[report_id]
    raw = bytes([subcmd]) + args
    if len(raw) > size:
        raise ValueError(f"参数超长：{len(raw)} > {size}")
    return encode(raw.ljust(size, b"\x00"))


def parse_response(buf: bytes) -> tuple[int, int, bytes]:
    """解析 get_feature_report 返回的 buffer。

    布局（kb/0003 §2 与 §7.1，以真机为准）：
    buf[0] = reportId（原始值，不取反）
    buf[1] = 子命令回显（取反后）
    buf[2:] = 数据（取反后）

    返回 (report_id, subcmd, payload)。
    """
    if len(buf) < 2:
        raise ValueError("响应过短")
    report_id = buf[0]
    decoded = decode(bytes(buf[1:]))
    return report_id, decoded[0], decoded[1:]


def build_read_firmware() -> tuple[int, bytes]:
    """读固件版本命令（0x11 0x04，kb/0003 §3）。"""
    return REPORT_ID_SHORT, build_command(REPORT_ID_SHORT, CMD_READ_FIRMWARE)


def parse_firmware_version(payload: bytes) -> str:
    """解析固件版本响应数据（已去掉 reportId 与子命令字节）。

    布局：byte[0] = 版本字符串长度，byte[1..1+len] = ASCII 版本号（含尾部 NUL）。
    真机样本：08 35 2e 31 35 2e 30 2e 39 → "5.15.0.9"（kb/0002 实机记录 2）。
    """
    length = payload[0]
    return payload[1 : 1 + length].rstrip(b"\x00").decode("ascii")


# --- 读设备信息 0x11 0x06（kb/0005 §1） ---


@dataclass(frozen=True)
class DeviceInfo:
    vid: int  # u16 LE
    pid: int  # u16 LE
    fw_version_raw: int  # u32 LE，原始值
    connect_mode: int  # byte8 bit0-2：0=有线 1=2.4G（LSB 读法，真机修正见 kb/0007）
    connect_status: int  # byte8 bit3
    battery_level: int  # 电量百分比
    charge_status: int  # 充电状态


def build_read_device_info() -> tuple[int, bytes]:
    """读设备信息命令（0x11 0x06，kb/0005 §1）。"""
    return REPORT_ID_SHORT, build_command(REPORT_ID_SHORT, CMD_READ_DEVICE_INFO)


def parse_device_info(payload: bytes) -> DeviceInfo:
    """解析设备信息响应（布局见 kb/0005 §1，共 11 字节）。"""
    return DeviceInfo(
        vid=int.from_bytes(payload[0:2], "little"),
        pid=int.from_bytes(payload[2:4], "little"),
        fw_version_raw=int.from_bytes(payload[4:8], "little"),
        connect_mode=payload[8] & 0x07,  # 0=有线 1=2.4G（kb/0007，真机修正为 LSB 读法）
        connect_status=(payload[8]) >> 3 & 1,
        battery_level=payload[9],
        charge_status=payload[10],
    )


# --- 读整份配置 0x12 0x67（kb/0005 §2） ---


@dataclass(frozen=True)
class ButtonBinding:
    """单个按键绑定（kb/0005 §2 按键区，语义映射待 kb 按键条目补充）。"""

    button_type: int  # 高 4 位
    button_index: int  # 低 4 位
    value: int  # 3 字节 BE，如 0x010000=左键


@dataclass(frozen=True)
class MouseConfig:
    """整份配置（kb/0005 §2，63 字节逻辑数据）。"""

    profile_index: int
    g_dpi_index: int  # 2.4G 侧当前 DPI 档
    g_rate_index: int  # 2.4G 侧当前回报率档
    usb_dpi_index: int  # 有线侧当前 DPI 档
    usb_rate_index: int  # 有线侧当前回报率档
    dpis: tuple[int, ...]  # 6 档 DPI，真实值无缩放
    dpi_count: int  # 有效档位数
    sensor: int  # 位掩码，用下方 sensor_* 助手解读
    key_debounce: int
    sleep_minutes: int  # 0=从不休眠
    buttons: tuple[ButtonBinding, ...]  # 6 个按键
    rotate_raw: int  # 原始值，角度 = rotate_degrees
    val: int  # 含义未知（写时固定 255）
    dpi_vals: tuple[int, ...]  # 6 档独立 Y 轴 DPI

    @property
    def rotate_degrees(self) -> int:
        """角度旋转（度）。原始值 >30 按负值处理（kb/0005 §2），单位 4°。"""
        v = self.rotate_raw - 256 if self.rotate_raw > 30 else self.rotate_raw
        return v * 4


def build_read_config() -> tuple[int, bytes]:
    """读整份配置命令（0x12 0x67，kb/0005 §2）。"""
    return REPORT_ID_LONG, build_command(REPORT_ID_LONG, CMD_READ_CONFIG)


def parse_config(payload: bytes) -> MouseConfig:
    """解析整份配置响应（布局见 kb/0005 §2，63 字节，u16 均小端）。"""
    dpis = tuple(
        int.from_bytes(payload[4 + i * 2 : 6 + i * 2], "little") for i in range(6)
    )
    buttons = tuple(
        ButtonBinding(
            button_type=payload[20 + i * 4] >> 4,
            button_index=payload[20 + i * 4] & 0x0F,
            value=int.from_bytes(payload[21 + i * 4 : 24 + i * 4], "big"),
        )
        for i in range(6)
    )
    dpi_vals = tuple(
        int.from_bytes(payload[51 + i * 2 : 53 + i * 2], "little") for i in range(6)
    )
    return MouseConfig(
        profile_index=payload[0],
        g_dpi_index=payload[1] >> 4,
        g_rate_index=payload[1] & 0x0F,
        usb_dpi_index=payload[2] >> 4,
        usb_rate_index=payload[2] & 0x0F,
        dpis=dpis,
        dpi_count=payload[16],
        sensor=payload[17],
        key_debounce=payload[18],
        sleep_minutes=payload[19],
        buttons=buttons,
        rotate_raw=payload[49],
        val=payload[50],
        dpi_vals=dpi_vals,
    )


# --- sensor 位掩码助手（kb/0005 §4，bit 编号从 LSB 起） ---


def sensor_lod(sensor: int) -> int:
    """LOD 档位值（bit0-1）。显示文本映射见 devices.MODEL_CAPS。"""
    return sensor & 0b11


def sensor_ripple(sensor: int) -> bool:
    return bool(sensor & 0b100)


def sensor_line(sensor: int) -> bool:
    return bool(sensor & 0b1000)


def sensor_motion_sync(sensor: int) -> bool:
    return bool(sensor & 0b10000)


def sensor_game_mode(sensor: int) -> int:
    """电竞模式：bit7=0→0；bit7=1&bit6=0→1；bit7=1&bit6=1→2（kb/0005 §4）。"""
    if not sensor & 0x80:
        return 0
    return 2 if sensor & 0x40 else 1


# --- 回报率档位表（kb/0005 §3.2，无 250Hz） ---

RATE_TABLES: dict[str, tuple[int, ...]] = {
    "1k": (125, 500, 1000),
    "4k": (125, 500, 1000, 2000, 4000),
    "8k": (125, 500, 1000, 2000, 4000, 8000),
}

# --- 写命令（kb/0005 §3）。注意：写命令真机验证前只允许离线测试 ---

# 性能开关的写入编码（kb/0005 §3.3，与读回位掩码不同）
SWITCH_ON = 1
SWITCH_OFF = 2


def build_write_dpi(
    dpi_index: int,
    dpis: tuple[int, ...],
    dpi_count: int,
    dpi_vals: tuple[int, ...] | None = None,
) -> tuple[int, bytes]:
    """写 DPI 整表（0x12 0x40，kb/0005 §3.1）。

    dpis 为 6 档真实 DPI 值；dpi_vals 为独立 Y 轴（None 时复制 dpis，即不启用）。
    usb/g 两侧索引写同一值（官方行为，kb/0005 §3.1）。
    """
    if len(dpis) != 6:
        raise ValueError("dpis 必须为 6 档")
    vals = dpis if dpi_vals is None else dpi_vals
    if len(vals) != 6:
        raise ValueError("dpi_vals 必须为 6 档")
    args = (
        bytes([dpi_index, dpi_index, 0])  # usbDpiIndex, gDpiIndex, reserved
        + b"".join(d.to_bytes(2, "little") for d in dpis)
        + bytes([dpi_count, 0xFF])  # sum, diff（固定 255）
        + b"".join(d.to_bytes(2, "little") for d in vals)
    )
    return REPORT_ID_LONG, build_command(REPORT_ID_LONG, CMD_WRITE_DPI, args)


def build_write_rate(rate_index: int, wired: bool) -> tuple[int, bytes]:
    """写回报率（0x11 0x41，kb/0005 §3.2）。有线写 usbRate，2.4G 写 freeRate。"""
    args = bytes([rate_index, 0]) if wired else bytes([0, rate_index])
    return REPORT_ID_SHORT, build_command(REPORT_ID_SHORT, CMD_WRITE_RATE, args)


def build_write_sensor(
    lod: int,
    ripple: int,
    line: int,
    motion_sync: int,
    game_mode: int,
    rotate_open: int = 0,
    rotate_val: int = 0,
) -> tuple[int, bytes]:
    """写性能参数（0x11 0x42，kb/0005 §3.3）。

    ripple/line/motion_sync 用 SWITCH_ON/SWITCH_OFF；game_mode 1/2/3；
    rotate_val = 度数/4，负值 +256。
    """
    args = bytes(
        [lod, ripple, line, motion_sync, 0, 0, game_mode, rotate_open, rotate_val]
    )
    return REPORT_ID_SHORT, build_command(REPORT_ID_SHORT, CMD_WRITE_SENSOR, args)


def build_write_sleep(enabled: bool, minutes: int) -> tuple[int, bytes]:
    """写休眠（0x11 0x0A，kb/0005 §3.4）。enabled=False 表示从不休眠。"""
    return REPORT_ID_SHORT, build_command(
        REPORT_ID_SHORT, CMD_WRITE_SLEEP, bytes([1 if enabled else 0, minutes])
    )


def build_write_debounce(value: int) -> tuple[int, bytes]:
    """写按键防抖（0x11 0x43，kb/0005 §3.4，UI 范围 0-20）。"""
    return REPORT_ID_SHORT, build_command(
        REPORT_ID_SHORT, CMD_WRITE_DEBOUNCE, bytes([value])
    )


def build_switch_profile(profile_index: int) -> tuple[int, bytes]:
    """切换板载配置（0x11 0x58，kb/0005 §3.4）。"""
    return REPORT_ID_SHORT, build_command(
        REPORT_ID_SHORT, CMD_SWITCH_PROFILE, bytes([profile_index])
    )


def build_factory_reset() -> tuple[int, bytes]:
    """恢复出厂设置（0x11 0x0B，魔数 AA 00，kb/0005 §3.4）。"""
    return REPORT_ID_SHORT, build_command(
        REPORT_ID_SHORT, CMD_FACTORY_RESET, bytes([0xAA, 0x00])
    )
