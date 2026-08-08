"""真机写测试（--runlive 才运行，鼠标需处于唤醒状态）。

写通路验证策略：把当前 DPI 表原样写回（值不变、无风险），再读回比对。
依据：kb/0005 §3.1（写 DPI 布局）、kb/0007（休眠与缓冲区坑）。
"""

from __future__ import annotations

import pytest

from mcmouse.session import OldProtocolSession
from mcmouse.transport import pick_config_interface

pytestmark = pytest.mark.live


def test_dpi_write_back_same_values() -> None:
    iface = pick_config_interface()
    assert iface is not None and iface.variant is not None, "未发现迈从设备"
    assert iface.variant.protocol == "old", "新协议设备不适用本测试"

    with OldProtocolSession.open(iface) as session:
        before = session.read_config()
        assert before.dpi_count > 0, "读到全零配置，请先晃动鼠标唤醒（kb/0007 §3）"

        session.write_dpi(before, wired=iface.variant.role == "wired")

        after = session.read_config()

    assert after.dpis == before.dpis
    assert after.dpi_vals == before.dpi_vals
    assert after.dpi_count == before.dpi_count
    if iface.variant.role == "wired":
        assert after.usb_dpi_index == before.usb_dpi_index
    else:
        assert after.g_dpi_index == before.g_dpi_index
