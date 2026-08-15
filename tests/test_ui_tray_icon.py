"""菜单栏空心鼠标电量图标（离屏绘制）。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from mcmouse.ui import (  # noqa: E402
    make_tray_icon,
    render_tray_mouse,
    tray_icon_tooltip,
)


def _app() -> QGuiApplication:
    existing = QGuiApplication.instance()
    if existing is not None:
        assert isinstance(existing, QGuiApplication)
        return existing
    return QGuiApplication([])


def _opaque(battery: int | None, *, charging: bool = False) -> int:
    _app()
    img = render_tray_mouse(44, battery, charging=charging).toImage()
    count = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 20:
                count += 1
    return count


def test_tray_tooltip() -> None:
    assert tray_icon_tooltip(None) == "未连接"
    assert tray_icon_tooltip(80) == "电量 80%"
    assert tray_icon_tooltip(40, charging=True) == "电量 40% · 充电中"


def test_fill_grows_with_battery() -> None:
    empty = _opaque(None)
    low = _opaque(15)
    high = _opaque(90)
    assert low > empty
    assert high > low


def test_charging_differs_from_idle() -> None:
    assert _opaque(70, charging=True) != _opaque(70, charging=False)


def test_low_battery_drops_template_mask() -> None:
    _app()
    assert make_tray_icon(80).isMask()
    assert not make_tray_icon(10).isMask()
    assert make_tray_icon(10, charging=True).isMask()
    assert make_tray_icon(None).isMask()
