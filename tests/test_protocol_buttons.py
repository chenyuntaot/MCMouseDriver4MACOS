"""按键语义映射的离线测试（依据 kb/0006 §1）。"""

from __future__ import annotations

import pytest

from mcmouse.protocol import buttons, old


def _binding(t: int, i: int, v: int) -> old.ButtonBinding:
    return old.ButtonBinding(button_type=t, button_index=i, value=v)


def test_describe_mouse_buttons() -> None:
    assert buttons.describe_button(_binding(0, 0, 0)) == "默认"
    assert buttons.describe_button(_binding(1, 0, 0x010000)) == "左键"
    assert buttons.describe_button(_binding(1, 0, 0x100000)) == "前进"
    assert buttons.describe_button(_binding(1, 0, 0x000200)) == "滚轮上滚"
    assert buttons.describe_button(_binding(1, 0, 0x00FE00)) == "滚轮下滚"


def test_describe_keyboard() -> None:
    assert buttons.describe_button(_binding(2, 0, 0x000400)) == "A"  # usage 0x04
    assert buttons.describe_button(_binding(2, 0, 0x010400)) == "Ctrl+A"
    assert buttons.describe_button(_binding(2, 0, 0x022800)) == "Shift+Enter"
    assert buttons.describe_button(_binding(2, 0, 0x052800)) == "Ctrl+Alt+Enter"
    assert buttons.describe_button(_binding(2, 0, 0x00E100)) == "Shift"
    assert buttons.describe_button(_binding(2, 0, 0x00E300)) == "Cmd"


def test_describe_others() -> None:
    assert buttons.describe_button(_binding(3, 0, 0xE90000)) == "音量+"
    assert buttons.describe_button(_binding(4, 0, 0)) == "宏"
    assert buttons.describe_button(_binding(5, 0, 0x010000)) == "DPI 切换"
    assert buttons.describe_button(_binding(8, 0, 0x070106)) == "复制"
    assert buttons.describe_button(_binding(9, 0, 0xFFFFFF)) == "禁用"
    assert buttons.describe_button(_binding(10, 0, 0x020000)) == "板载配置 2"
    assert buttons.describe_button(_binding(6, 0, 0x123456)) == "未知类型 6（0x123456）"


def test_build_write_button_layout() -> None:
    report_id, payload = buttons.build_write_button(3, 5, 0x010000)
    assert report_id == old.REPORT_ID_LONG
    raw = old.decode(payload)
    # [0x52, buttonIndex, reserved, buttonType, value(3B BE)]（kb/0006 §1.3）
    assert raw[:7] == bytes([0x52, 0x03, 0x00, 0x05, 0x01, 0x00, 0x00])
    assert raw[7:] == b"\x00" * (64 - 7)  # 其余填充


def test_build_write_button_validation() -> None:
    with pytest.raises(ValueError):
        buttons.build_write_button(6, 0, 0)
    with pytest.raises(ValueError):
        buttons.build_write_button(0, 0, 0x1000000)


def test_presets_consistent_with_describe() -> None:
    # 每个预设写进去后，describe 应给出非"未知"的解读
    for name, (t, v) in buttons.BUTTON_PRESETS.items():
        text = buttons.describe_button(_binding(t, 0, v))
        assert "未知" not in text, name
