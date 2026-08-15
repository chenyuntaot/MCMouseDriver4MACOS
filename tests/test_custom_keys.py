"""自定义键盘键持久化。"""

from __future__ import annotations

from pathlib import Path

from mcmouse.custom_keys import add_custom_key, load_custom_keys


def test_add_and_load(tmp_path: Path) -> None:
    path = tmp_path / "custom_keys.json"
    added = add_custom_key("Cmd+C", 2, 0x080600, path)
    assert added is not None
    keys = load_custom_keys(path)
    assert len(keys) == 1
    assert keys[0].label == "Cmd+C"
    assert keys[0].value == 0x080600


def test_duplicate_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "custom_keys.json"
    assert add_custom_key("A", 2, 0x000400, path) is not None
    assert add_custom_key("A 重复", 2, 0x000400, path) is None
    assert len(load_custom_keys(path)) == 1


def test_missing_file(tmp_path: Path) -> None:
    assert load_custom_keys(tmp_path / "nope.json") == []
