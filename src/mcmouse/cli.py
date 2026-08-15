"""mcmouse 命令行入口。

一期定位：协议验证与调试工具；菜单栏 GUI 为二期。
当前提供设备枚举与只读信息读取；写命令待真机验证后逐个接入。
"""

from __future__ import annotations

from dataclasses import replace

import typer

from .devices import DPI_MIN, MODEL_CAPS, DeviceVariant
from .protocol.buttons import (
    BUTTON_NAMES,
    BUTTON_PRESETS,
    KEY_TOKENS,
    describe_button,
)
from .protocol.macros import TRIGGER_MODES, parse_events_dsl
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
    typer.echo("按键绑定：")
    for n, b in enumerate(cfg.buttons):
        name = BUTTON_NAMES.get(n, f"键{n}")
        typer.echo(f"  {name}: {describe_button(b)}")


dpi_app = typer.Typer(help="DPI 设置（写入后读回校验）", no_args_is_help=True)
app.add_typer(dpi_app, name="dpi")


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


rate_app = typer.Typer(help="回报率设置", no_args_is_help=True)
app.add_typer(rate_app, name="rate")

sensor_app = typer.Typer(help="传感器性能设置", no_args_is_help=True)
app.add_typer(sensor_app, name="sensor")


def _parse_switch(text: str) -> bool:
    """解析开关参数：on/off/开/关。"""
    t = text.strip().lower()
    if t in ("on", "开", "1", "true"):
        return True
    if t in ("off", "关", "0", "false"):
        return False
    typer.echo("开关取值：on/off")
    raise typer.Exit(code=2)


def _sensor_roundtrip(
    iface: HidInterface, **changes: object
) -> tuple[MouseConfig, MouseConfig]:
    """读配置 → 覆盖指定项写性能参数 → 读回（kb/0005 §3.3）。"""
    with OldProtocolSession.open(iface) as session:
        cfg = _read_awake_config(session)
        session.write_sensor(cfg, **changes)
        return cfg, _read_awake_config(session)


@rate_app.command("set")
def rate_set(hz: int) -> None:
    """设置回报率（Hz），可选值取决于当前连接方式。"""
    iface, variant = _require_old_device()
    rates = RATE_TABLES[variant.rate_table]
    if hz not in rates:
        typer.echo(f"当前连接仅支持: {'/'.join(str(r) for r in rates)}Hz")
        raise typer.Exit(code=2)
    index = rates.index(hz)
    wired = variant.role == "wired"
    with OldProtocolSession.open(iface) as session:
        session.write_rate(index, wired)
        after = _read_awake_config(session)
    current = after.usb_rate_index if wired else after.g_rate_index
    if current != index:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"回报率 → {rates[current]}Hz")


@sensor_app.command("lod")
def sensor_lod_set(value: str) -> None:
    """设置 LOD 高度（可选档位见机型能力表，如 1mm/2mm）。"""
    iface, variant = _require_old_device()
    caps = MODEL_CAPS.get(variant.model)
    if caps is None or not caps.lod_labels:
        typer.echo("该机型的 LOD 档位未登记（见 kb/devices）。")
        raise typer.Exit(code=1)
    # 反查显示文本 → 档位值（kb/0005 §4）
    normalized = value.strip().lower().removesuffix("mm")
    options = {label.removesuffix("mm"): key for key, label in caps.lod_labels.items()}
    if normalized not in options:
        typer.echo(f"可选: {' / '.join(caps.lod_labels.values())}")
        raise typer.Exit(code=2)
    lod = options[normalized]
    _, after = _sensor_roundtrip(iface, lod=lod)
    if sensor_lod(after.sensor) != lod:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"LOD → {caps.lod_labels[lod]}")


@sensor_app.command("ripple")
def sensor_ripple_set(state: str) -> None:
    """波纹控制开关（on/off）。"""
    target = _parse_switch(state)
    iface, _ = _require_old_device()
    _, after = _sensor_roundtrip(iface, ripple=target)
    if sensor_ripple(after.sensor) != target:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"波纹控制 → {'开' if target else '关'}")


@sensor_app.command("line")
def sensor_line_set(state: str) -> None:
    """直线修正开关（on/off）。"""
    target = _parse_switch(state)
    iface, _ = _require_old_device()
    _, after = _sensor_roundtrip(iface, line=target)
    if sensor_line(after.sensor) != target:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"直线修正 → {'开' if target else '关'}")


@sensor_app.command("motion-sync")
def sensor_motion_sync_set(state: str) -> None:
    """Motion Sync 开关（on/off）。"""
    target = _parse_switch(state)
    iface, _ = _require_old_device()
    _, after = _sensor_roundtrip(iface, motion_sync=target)
    if sensor_motion_sync(after.sensor) != target:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"Motion Sync → {'开' if target else '关'}")


@sensor_app.command("game-mode")
def sensor_game_mode_set(mode: int) -> None:
    """电竞模式（0/1/2）。"""
    if not 0 <= mode <= 2:
        typer.echo("模式取值：0/1/2")
        raise typer.Exit(code=2)
    iface, _ = _require_old_device()
    _, after = _sensor_roundtrip(iface, game_mode=mode)
    if sensor_game_mode(after.sensor) != mode:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"电竞模式 → {mode}")


@app.command()
def sleep(minutes: int) -> None:
    """设置休眠时间（分钟，0=从不休眠）。"""
    if not 0 <= minutes <= 255:
        typer.echo("分钟数需在 0-255 之间。")
        raise typer.Exit(code=2)
    iface, _ = _require_old_device()
    with OldProtocolSession.open(iface) as session:
        session.write_sleep(minutes)
        after = _read_awake_config(session)
    if after.sleep_minutes != minutes:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"休眠 → {'从不' if minutes == 0 else f'{minutes} 分钟'}")


@app.command()
def debounce(value: int) -> None:
    """设置按键防抖（0-20）。"""
    if not 0 <= value <= 20:
        typer.echo("防抖值需在 0-20 之间（kb/0005 §3.4）。")
        raise typer.Exit(code=2)
    iface, _ = _require_old_device()
    with OldProtocolSession.open(iface) as session:
        session.write_debounce(value)
        after = _read_awake_config(session)
    if after.key_debounce != value:
        typer.echo("写入未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(f"按键防抖 → {value}")


button_app = typer.Typer(help="按键映射", no_args_is_help=True)
app.add_typer(button_app, name="button")

# 键名 → 物理索引（kb/0006 §1.1）
KEY_ALIASES = {
    "left": 0,
    "mid": 1,
    "middle": 1,
    "right": 2,
    "forward": 3,
    "back": 4,
}


@button_app.command("set")
def button_set(key: str, preset: str) -> None:
    """把 KEY（0-5 或 left/mid/right/forward/back）设为预设功能。

    预设见 BUTTON_PRESETS：default/disable/dpi-switch/dpi-plus/dpi-minus/
    left/right/middle/back/forward/wheel-up/wheel-down/volume-up/…
    """
    index = _parse_key(key)
    if preset not in BUTTON_PRESETS:
        typer.echo(f"未知预设 {preset}，可用: {'/'.join(BUTTON_PRESETS)}")
        raise typer.Exit(code=2)
    button_type, value = BUTTON_PRESETS[preset]
    iface, _ = _require_old_device()
    with OldProtocolSession.open(iface) as session:
        _read_awake_config(session)  # 先确认鼠标在线
        session.write_button(index, button_type, value)
        after = _read_awake_config(session)
    binding = after.buttons[index]
    typer.echo(f"{BUTTON_NAMES.get(index, f'键{index}')} → {describe_button(binding)}")


macro_app = typer.Typer(help="宏", no_args_is_help=True)
app.add_typer(macro_app, name="macro")


def _parse_key(key: str) -> int:
    """解析按键参数：0-5 或 left/mid/right/forward/back。"""
    index = KEY_ALIASES.get(key.lower())
    if index is not None:
        return index
    if key.isdigit() and 0 <= int(key) <= 5:
        return int(key)
    typer.echo(f"未知按键 {key}，可用: 0-5 或 {'/'.join(KEY_ALIASES)}")
    raise typer.Exit(code=2)


def _parse_events(dsl: str) -> list[bytes]:
    """解析宏事件 DSL（语法见 protocol.macros.parse_events_dsl）。"""
    try:
        return parse_events_dsl(dsl, KEY_TOKENS)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc


@macro_app.command("set")
def macro_set(
    key: str,
    events: str,
    mode: str = "once",
    name: str = "macro",
) -> None:
    """把宏写入 KEY 槽位，并把该键绑定为宏（type=4）。

    EVENTS 为逗号分隔 DSL，如 `a,delay:50,a`；--mode 触发方式
    （once/hold-loop/until-same-key/until-any-key）；--name 宏名。
    """
    if mode not in TRIGGER_MODES:
        typer.echo(f"触发方式: {'/'.join(TRIGGER_MODES)}")
        raise typer.Exit(code=2)
    index = _parse_key(key)
    event_bytes = _parse_events(events)
    iface, _ = _require_old_device()
    with OldProtocolSession.open(iface) as session:
        _read_awake_config(session)  # 确认在线
        # 顺序敏感（kb/0007 §7）：0x52 绑定会清空槽内事件，必须先绑再写数据
        session.write_button(index, 4, 0)  # 绑定为宏（kb/0006 §1.2 type=4）
        session.write_macro(index, event_bytes, TRIGGER_MODES[mode], name)
        after = _read_awake_config(session)
    if after.buttons[index].button_type != 4:
        typer.echo("绑定未生效，请重试。")
        raise typer.Exit(code=1)
    typer.echo(
        f"{BUTTON_NAMES.get(index, f'键{index}')} → 宏 {name!r}"
        f"（{len(event_bytes)} 个事件，{mode}）"
    )


@app.command()
def gui() -> None:
    """启动 macOS 菜单栏应用（无 Dock 图标，常驻菜单栏）。"""
    from .gui import run

    raise SystemExit(run())
