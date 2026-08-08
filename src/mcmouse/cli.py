"""mcmouse 命令行入口。

一期定位：协议验证与调试工具；菜单栏 GUI 为二期。
当前提供设备枚举与只读信息读取；写命令待真机验证后逐个接入。
"""

from __future__ import annotations

from dataclasses import replace

import typer

from .devices import MODEL_CAPS, DeviceVariant
from .protocol.old import (
    RATE_TABLES,
    MouseConfig,
    sensor_game_mode,
    sensor_line,
    sensor_lod,
    sensor_motion_sync,
    sensor_ripple,
)
from .session import OldProtocolSession
from .transport import HidInterface, enumerate_interfaces, pick_config_interface

app = typer.Typer(help="迈从 A7 系列鼠标 macOS 配置工具", no_args_is_help=True)


@app.callback()
def _callback() -> None:
    """强制子命令模式，避免单命令时 CLI 形态漂移。"""


@app.command("list")
def list_devices() -> None:
    """枚举当前连接的迈从设备 HID 接口。"""
    interfaces = list(enumerate_interfaces())
    if not interfaces:
        typer.echo("未发现迈从设备。请用有线或 2.4G 接收器连接鼠标后重试。")
        raise typer.Exit(code=1)
    for i in interfaces:
        model = i.variant.model if i.variant else "未登记设备"
        typer.echo(
            f"{model}  vid=0x{i.vid:04x} pid=0x{i.pid:04x} "
            f"usage_page=0x{i.usage_page:04x} usage=0x{i.usage:04x} "
            f"if={i.interface_number}  {i.product}  serial={i.serial}"
        )


def _require_old_device() -> tuple[HidInterface, DeviceVariant]:
    """取配置接口并校验为旧协议设备，否则报错退出。"""
    iface = pick_config_interface()
    if iface is None or iface.variant is None:
        typer.echo("未发现迈从设备。请用有线或 2.4G 接收器连接鼠标后重试。")
        raise typer.Exit(code=1)
    if iface.variant.protocol != "old":
        typer.echo(f"{iface.variant.model} 使用新协议（kb/0004），暂不支持。")
        raise typer.Exit(code=1)
    return iface, iface.variant


@app.command()
def info() -> None:
    """读取设备信息（只读）：固件、电量、DPI、回报率、性能参数。"""
    iface, variant = _require_old_device()

    role_names = {
        "wired": "有线",
        "receiver-1k": "2.4G 接收器（1K）",
        "receiver-8k": "2.4G 接收器（8K）",
    }
    typer.echo(f"型号: {variant.model}（{role_names.get(variant.role, variant.role)}）")
    with OldProtocolSession.open(iface) as session:
        typer.echo(f"固件版本: {session.read_firmware()}")
        dev_info = session.read_device_info()
        typer.echo(
            f"电量: {dev_info.battery_level}%  "
            f"充电状态: {dev_info.charge_status}  "
            f"连接: mode={dev_info.connect_mode} status={dev_info.connect_status}"
        )
        cfg = session.read_config()

    wired = variant.role == "wired"
    dpi_index = cfg.usb_dpi_index if wired else cfg.g_dpi_index
    rate_index = cfg.usb_rate_index if wired else cfg.g_rate_index
    rates = RATE_TABLES[variant.rate_table]
    rate_text = (
        f"{rates[rate_index]}Hz" if rate_index < len(rates) else f"索引{rate_index}"
    )
    dpis = [str(d) for d in cfg.dpis[: cfg.dpi_count]]
    if dpi_index < len(dpis):
        dpis[dpi_index] = f"[{dpis[dpi_index]}]"
    typer.echo(f"DPI: {' / '.join(dpis)}（第 {dpi_index + 1} 档生效）")
    typer.echo(f"回报率: {rate_text}（第 {rate_index + 1} 档）")

    caps = MODEL_CAPS.get(variant.model)
    lod = sensor_lod(cfg.sensor)
    lod_text = caps.lod_labels.get(lod, str(lod)) if caps else str(lod)
    typer.echo(
        f"性能: LOD={lod_text}  波纹={'开' if sensor_ripple(cfg.sensor) else '关'}  "
        f"直线修正={'开' if sensor_line(cfg.sensor) else '关'}  "
        f"MotionSync={'开' if sensor_motion_sync(cfg.sensor) else '关'}  "
        f"电竞模式={sensor_game_mode(cfg.sensor)}"
    )
    typer.echo(f"防抖: {cfg.key_debounce}  休眠: {cfg.sleep_minutes} 分钟（0=从不）")
    typer.echo(f"角度旋转: {cfg.rotate_degrees}°  板载配置: #{cfg.profile_index}")
    typer.echo("按键绑定（type/index/value，语义待 kb 按键条目）：")
    for n, b in enumerate(cfg.buttons):
        typer.echo(
            f"  键{n}: type={b.button_type} index={b.button_index} "
            f"value=0x{b.value:06x}"
        )


dpi_app = typer.Typer(help="DPI 设置（写入后读回校验）", no_args_is_help=True)
app.add_typer(dpi_app, name="dpi")

DPI_MIN = 100  # 下限保守拦截，官方 UI 常见最低档为 100/200


def _read_awake_config(session: OldProtocolSession) -> MouseConfig:
    """读配置并拦截休眠零配置（kb/0007 §3/§5）。"""
    cfg = session.read_config()
    if cfg.dpi_count == 0:
        typer.echo("读到全零配置，鼠标可能在休眠，请晃动鼠标后重试（kb/0007）。")
        raise typer.Exit(code=1)
    return cfg


@dpi_app.command("set")
def dpi_set(stage: int, value: int) -> None:
    """修改第 STAGE 档（1 起）的 DPI 为 VALUE。"""
    iface, variant = _require_old_device()
    caps = MODEL_CAPS.get(variant.model)
    dpi_max = caps.dpi_max if caps else 26000
    with OldProtocolSession.open(iface) as session:
        cfg = _read_awake_config(session)
        if not 1 <= stage <= cfg.dpi_count:
            typer.echo(f"档位需在 1-{cfg.dpi_count} 之间。")
            raise typer.Exit(code=2)
        if not DPI_MIN <= value <= dpi_max:
            typer.echo(f"DPI 需在 {DPI_MIN}-{dpi_max} 之间。")
            raise typer.Exit(code=2)
        dpis = list(cfg.dpis)
        old_value = dpis[stage - 1]
        dpis[stage - 1] = value
        session.write_dpi(replace(cfg, dpis=tuple(dpis)), wired=variant.role == "wired")
        after = _read_awake_config(session)
    if after.dpis[stage - 1] != value:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"第 {stage} 档 DPI: {old_value} → {value}")


@dpi_app.command("current")
def dpi_current(stage: int) -> None:
    """切换当前生效的 DPI 档位（1 起）。"""
    iface, variant = _require_old_device()
    with OldProtocolSession.open(iface) as session:
        cfg = _read_awake_config(session)
        if not 1 <= stage <= cfg.dpi_count:
            typer.echo(f"档位需在 1-{cfg.dpi_count} 之间。")
            raise typer.Exit(code=2)
        new_cfg = replace(cfg, usb_dpi_index=stage - 1, g_dpi_index=stage - 1)
        session.write_dpi(new_cfg, wired=variant.role == "wired")
        after = _read_awake_config(session)
    current = after.usb_dpi_index if variant.role == "wired" else after.g_dpi_index
    if current != stage - 1:
        typer.echo("切换未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"当前 DPI 档位 → 第 {stage} 档（{after.dpis[stage - 1]}）")
