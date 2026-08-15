"""设备注册表的静态自洽性测试（数据来自 kb/devices/0002）。"""

from __future__ import annotations

from mcmouse.devices import DPI_MIN, KNOWN_VARIANTS, MCHOSE_VIDS, clamp_dpi


def test_all_variants_use_known_vids() -> None:
    for v in KNOWN_VARIANTS:
        assert v.vid in MCHOSE_VIDS, v


def test_a7_models_present() -> None:
    models = {v.model for v in KNOWN_VARIANTS}
    assert "MCHOSE A7 V2 Pro+" in models
    assert "MCHOSE A7 V3 Ultra+" in models


def test_no_duplicate_vid_pid() -> None:
    pairs = [(v.vid, v.pid) for v in KNOWN_VARIANTS]
    # 同一 VID/PID 可被多个型号共用（见 kb/0002），但不应出现完全相同的重复条目
    assert len(set((v.model, v.vid, v.pid) for v in KNOWN_VARIANTS)) == len(
        KNOWN_VARIANTS
    )
    assert all(0 < pid < 65536 for _, pid in pairs)


def test_clamp_dpi() -> None:
    assert clamp_dpi(50, 26000) == DPI_MIN
    assert clamp_dpi(1193, 26000) == 1193
    assert clamp_dpi(30000, 26000) == 26000
