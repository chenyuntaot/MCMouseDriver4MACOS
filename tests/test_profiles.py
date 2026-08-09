"""命名配置持久化的离线测试（FR-6）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcmouse import profiles
from mcmouse.protocol.old import ButtonBinding, MouseConfig

SAMPLE = MouseConfig(
    profile_index=0,
    usb_rate_index=2,
    usb_dpi_index=2,
    g_rate_index=2,
    g_dpi_index=2,
    dpis=(400, 800, 1193, 1600, 6400, 26000),
    dpi_count=6,
    sensor=0x02,
    key_debounce=8,
    sleep_minutes=3,
    buttons=tuple(
        ButtonBinding(button_type=0, button_index=i, value=0) for i in range(6)
    ),
    rotate_raw=0,
    val=255,
    dpi_vals=(400, 800, 1193, 1600, 6400, 26000),
)


@pytest.fixture()
def tmp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr(profiles, "PROFILES_PATH", path)
    return path


def test_roundtrip(tmp_store: Path) -> None:
    profiles.save_profile("办公", SAMPLE)
    loaded = profiles.load_profiles()
    assert "办公" in loaded
    assert profiles.config_from_dict(loaded["办公"]) == SAMPLE


def test_load_missing_file(tmp_store: Path) -> None:
    assert profiles.load_profiles() == {}


def test_delete(tmp_store: Path) -> None:
    profiles.save_profile("a", SAMPLE)
    profiles.delete_profile("a")
    assert profiles.load_profiles() == {}


def test_save_rejects_empty_name(tmp_store: Path) -> None:
    with pytest.raises(ValueError):
        profiles.save_profile("  ", SAMPLE)


def test_export_import(tmp_store: Path, tmp_path: Path) -> None:
    profiles.save_profile("游戏", SAMPLE)
    out = tmp_path / "游戏.json"
    profiles.export_profile("游戏", out)
    assert profiles.import_profile(out) == SAMPLE


def test_validation_rejects_bad_dpi() -> None:
    data = profiles.config_to_dict(SAMPLE)
    data["dpis"] = [10, 800, 1200, 1600, 6400, 26000]  # 10 低于下限
    with pytest.raises(ValueError):
        profiles.config_from_dict(data)


def test_validation_rejects_bad_index() -> None:
    data = profiles.config_to_dict(SAMPLE)
    data["g_dpi_index"] = 9
    with pytest.raises(ValueError):
        profiles.config_from_dict(data)


def test_validation_rejects_missing_field() -> None:
    with pytest.raises(ValueError):
        profiles.config_from_dict({"dpis": [800] * 6})


def test_import_rejects_garbage(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        profiles.import_profile(bad)


def test_store_format_human_readable(tmp_store: Path) -> None:
    profiles.save_profile("办公", SAMPLE)
    raw = json.loads(tmp_store.read_text(encoding="utf-8"))
    assert "profiles" in raw and "办公" in raw["profiles"]
