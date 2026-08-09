"""命名配置持久化（FR-6）：保存/应用/导入/导出整份鼠标配置。

存储位置：`~/Library/Application Support/MCMouseDriver/profiles.json`。
导入时全量校验，非法配置拒绝（AGENTS.md 安全红线）。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .protocol.old import ButtonBinding, MouseConfig

PROFILES_PATH = Path(
    "~/Library/Application Support/MCMouseDriver/profiles.json"
).expanduser()

_DPI_MIN, _DPI_MAX = 100, 52000  # 全机型通用宽限，机型上限在应用时再校


def config_to_dict(cfg: MouseConfig) -> dict:
    """MouseConfig → 可 JSON 序列化的 dict。"""
    return asdict(cfg)


def config_from_dict(data: dict) -> MouseConfig:
    """dict → MouseConfig，带全量校验（非法即 ValueError）。"""
    try:
        dpis = tuple(int(v) for v in data["dpis"])
        dpi_vals = tuple(int(v) for v in data["dpi_vals"])
        buttons = tuple(
            ButtonBinding(
                button_type=int(b["button_type"]),
                button_index=int(b["button_index"]),
                value=int(b["value"]),
            )
            for b in data["buttons"]
        )
        cfg = MouseConfig(
            profile_index=int(data["profile_index"]),
            usb_rate_index=int(data["usb_rate_index"]),
            usb_dpi_index=int(data["usb_dpi_index"]),
            g_rate_index=int(data["g_rate_index"]),
            g_dpi_index=int(data["g_dpi_index"]),
            dpis=dpis,
            dpi_count=int(data["dpi_count"]),
            sensor=int(data["sensor"]),
            key_debounce=int(data["key_debounce"]),
            sleep_minutes=int(data["sleep_minutes"]),
            buttons=buttons,
            rotate_raw=int(data["rotate_raw"]),
            val=int(data["val"]),
            dpi_vals=dpi_vals,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"配置字段缺失或类型错误: {exc}") from exc
    _validate(cfg)
    return cfg


def _validate(cfg: MouseConfig) -> None:
    if len(cfg.dpis) != 6 or len(cfg.dpi_vals) != 6 or len(cfg.buttons) != 6:
        raise ValueError("dpis/dpi_vals/buttons 必须为 6 项")
    if not 1 <= cfg.dpi_count <= 6:
        raise ValueError("dpi_count 需在 1-6 之间")
    for d in cfg.dpis[: cfg.dpi_count]:
        if not _DPI_MIN <= d <= _DPI_MAX:
            raise ValueError(f"DPI 越界: {d}")
    for idx in (
        cfg.usb_rate_index,
        cfg.usb_dpi_index,
        cfg.g_rate_index,
        cfg.g_dpi_index,
    ):
        if not 0 <= idx <= 5:
            raise ValueError(f"档位索引越界: {idx}")
    for field in (cfg.sensor, cfg.key_debounce, cfg.sleep_minutes, cfg.rotate_raw):
        if not 0 <= field <= 255:
            raise ValueError(f"单字节字段越界: {field}")
    for b in cfg.buttons:
        if not 0 <= b.button_type <= 15 or not 0 <= b.button_index <= 15:
            raise ValueError(f"按键 type/index 越界: {b}")
        if not 0 <= b.value <= 0xFFFFFF:
            raise ValueError(f"按键 value 越界: {b}")


def load_profiles() -> dict[str, dict]:
    """读取全部命名配置（文件不存在返回空表）。"""
    if not PROFILES_PATH.exists():
        return {}
    try:
        raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in raw.get("profiles", {}).items()}


def _store(profiles: dict[str, dict]) -> None:
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(
        json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_profile(name: str, cfg: MouseConfig) -> None:
    """保存/覆盖一份命名配置。"""
    if not name.strip():
        raise ValueError("配置名不能为空")
    profiles = load_profiles()
    profiles[name.strip()] = config_to_dict(cfg)
    _store(profiles)


def delete_profile(name: str) -> None:
    profiles = load_profiles()
    if name in profiles:
        del profiles[name]
        _store(profiles)


def export_profile(name: str, path: Path) -> None:
    """导出单份配置为 JSON 文件。"""
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"配置不存在: {name}")
    path.write_text(
        json.dumps(profiles[name], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def import_profile(path: Path) -> MouseConfig:
    """从 JSON 文件导入配置（全量校验）。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取配置文件: {exc}") from exc
    return config_from_dict(data)
