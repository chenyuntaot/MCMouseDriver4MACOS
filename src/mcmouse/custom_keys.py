"""用户录制的自定义键盘键，持久化到 Application Support。

与命名配置分开存：只是下拉列表里的可选项，不绑定到某一份鼠标配置。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CUSTOM_KEYS_PATH = Path(
    "~/Library/Application Support/MCMouseDriver/custom_keys.json"
).expanduser()


@dataclass(frozen=True)
class CustomKey:
    """一条用户保存的键盘映射（kb/0006 type=2）。"""

    label: str
    button_type: int
    value: int


def load_custom_keys(path: Path = CUSTOM_KEYS_PATH) -> list[CustomKey]:
    """读取已保存的自定义键；文件缺失或损坏时返回空列表。"""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = raw.get("keys", raw if isinstance(raw, list) else [])
    result: list[CustomKey] = []
    seen: set[tuple[int, int]] = set()
    for item in items:
        try:
            key = CustomKey(
                label=str(item["label"]).strip() or "未命名",
                button_type=int(item["button_type"]),
                value=int(item["value"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        pair = (key.button_type, key.value)
        if pair in seen:
            continue
        if not 0 <= key.button_type <= 15 or not 0 <= key.value <= 0xFFFFFF:
            continue
        seen.add(pair)
        result.append(key)
    return result


def save_custom_keys(keys: list[CustomKey], path: Path = CUSTOM_KEYS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "keys": [
            {"label": k.label, "button_type": k.button_type, "value": k.value}
            for k in keys
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_custom_key(
    label: str,
    button_type: int,
    value: int,
    path: Path = CUSTOM_KEYS_PATH,
) -> CustomKey | None:
    """追加一条；已存在相同 (type, value) 时返回 None。"""
    keys = load_custom_keys(path)
    pair = (button_type, value)
    if any((k.button_type, k.value) == pair for k in keys):
        return None
    key = CustomKey(
        label=label.strip() or "未命名", button_type=button_type, value=value
    )
    keys.append(key)
    save_custom_keys(keys, path)
    return key
