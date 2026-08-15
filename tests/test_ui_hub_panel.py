"""HUB 设置窗口离屏绑定与任务发射。"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from mcmouse.devices import KNOWN_VARIANTS  # noqa: E402
from mcmouse.gui import DeviceSnapshot  # noqa: E402
from mcmouse.panel import Panel  # noqa: E402
from mcmouse.protocol.old import (  # noqa: E402
    ButtonBinding,
    MouseConfig,
    encode_rotate,
)

SAMPLE = MouseConfig(
    profile_index=0,
    usb_rate_index=2,
    usb_dpi_index=2,
    g_rate_index=2,
    g_dpi_index=2,
    dpis=(200, 1200, 2200, 3200, 4200, 26000),
    dpi_count=6,
    sensor=0x02,  # lod=2, 其余关
    key_debounce=8,
    sleep_minutes=3,
    buttons=tuple(
        ButtonBinding(button_type=0, button_index=i, value=0) for i in range(6)
    ),
    rotate_raw=2,  # 2°
    val=255,
    dpi_vals=(200, 1200, 2200, 3200, 4200, 26000),
)


def _press(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos,
        QPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _app() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _variant():
    for item in KNOWN_VARIANTS:
        if item.model == "MCHOSE A7 V2 Pro+" and item.role == "wired":
            return item
    raise AssertionError("测试用机型缺失")


def _snap(**overrides: object) -> DeviceSnapshot:
    data = {
        "variant": _variant(),
        "firmware": "5.42.2.4",
        "battery": 80,
        "charge_status": 0,
        "config": SAMPLE,
    }
    data.update(overrides)
    return DeviceSnapshot(**data)  # type: ignore[arg-type]


def _panel(tmp_path: Path, monkeypatch) -> tuple[Panel, list[tuple]]:  # noqa: ANN001
    _app()
    monkeypatch.setattr("mcmouse.profiles.PROFILES_PATH", tmp_path / "profiles.json")
    tasks: list[tuple] = []
    panel = Panel(lambda *a: tasks.append(a))
    panel.on_snapshot(_snap())
    tasks.clear()
    return panel, tasks


def test_snapshot_binds_dpi_and_perf(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, _tasks = _panel(tmp_path, monkeypatch)
    assert panel._dpi._count.index() == 5  # 6 档
    assert panel._dpi._cards[2].x_value() == 2200
    assert panel._dpi.current_index() == 2
    assert panel.windowTitle() == "A7 V2 Pro+"
    assert panel._perf._mode.index() == 0
    assert panel._perf._debounce.value() == 8
    assert panel._perf._rotate.degrees() == 2
    assert "80%" in panel._sidebar._battery.text()


def test_dpi_stage_emits(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._dpi.select_stage(1)
    assert tasks[-1] == ("dpi_stage", 1)


def test_dpi_table_xy_off_copies_vals(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._dpi._cards[0]._x_spin.setValue(800)
    panel._dpi._commit_table()
    kind, dpis, count, index, vals = tasks[-1]
    assert kind == "dpi_table"
    assert count == 6
    assert index == 2
    assert dpis[0] == 800
    assert vals == dpis


def test_dpi_restore_defaults(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._dpi._on_restore()
    kind, dpis, count, index, vals = tasks[-1]
    assert kind == "dpi_table"
    assert count == 6
    assert index == 2
    assert dpis == (200, 1200, 2200, 3200, 4200, 26000)
    assert vals == dpis


def test_switch_onboard_profile(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._sidebar._on_onboard(1)
    assert tasks[-1] == ("switch_profile", 1)


def test_factory_reset_requires_confirm(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Cancel
    )
    panel._other._on_factory_reset()
    assert tasks == []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes
    )
    panel._other._on_factory_reset()
    assert tasks[-1] == ("factory_reset",)


def test_button_assign(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._buttons.select_button(4)
    panel._buttons.assign(1, 0x080000)
    assert tasks[-1] == ("button", 4, 1, 0x080000)


def test_rate_and_sensor_emit(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._perf._rate.set_index(1, emit=True)
    assert tasks[-1] == ("rate", 1)
    panel._perf._ripple.toggle.set_on(True, emit=True)
    kind, payload = tasks[-1]
    assert kind == "sensor"
    assert payload["ripple"] is True
    # 未动刻度盘时不带角度，交给协议层沿用设备读回值
    assert "rotate_degrees" not in payload


def test_sleep_never(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._perf._never.setChecked(True)
    assert tasks[-1] == ("sleep", 0)


def test_sleeping_blocks_writes(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel.on_snapshot(_snap(config=None))
    tasks.clear()
    panel._dpi.select_stage(1)
    panel._sidebar._on_onboard(1)
    panel._buttons.assign(1, 0x010000)
    assert tasks == []


def test_assign_rows_show_bindings(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """右栏六行依次对应六个物理键，并显示各自当前功能。"""
    panel, _tasks = _panel(tmp_path, monkeypatch)
    rows = panel._buttons._rows
    assert [row._name.text() for row in rows] == [
        "左键",
        "中键",
        "右键",
        "前进键",
        "后退键",
        "DPI 键",
    ]
    assert rows[0]._func.text() == "默认（左键）"
    assert rows[0]._selected is True


def test_assign_row_click_selects_button(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    rows = panel._buttons._rows
    rows[4].clicked.emit(4)
    assert panel._buttons.selected_button() == 4
    assert rows[4]._selected is True
    assert rows[0]._selected is False
    panel._buttons.assign(1, 0x010000)
    assert tasks[-1] == ("button", 4, 1, 0x010000)


def test_rotate_dial_maps_position_to_degrees(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """刻度盘上的落点必须能反解回同一角度，保证拖动与绘制一致。"""
    panel, _tasks = _panel(tmp_path, monkeypatch)
    dial = panel._perf._rotate._dial
    dial.resize(240, 240)
    for degrees in (-30, -12, -1, 0, 7, 30):
        dial.set_degrees(degrees)
        knob = dial._point_at(degrees, dial._radius())
        assert dial._value_at(knob) == degrees


def test_rotate_degrees_written_verbatim(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """界面上的度数必须原样写进设备：rotateVal 就是度数（kb/0005 §3.3）。"""
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._perf._rotate.set_degrees(12)
    panel._perf._rotate._plus.click()
    assert tasks[-1][1]["rotate_degrees"] == 13
    open_flag, raw = encode_rotate(13)
    assert (open_flag, raw) == (1, 13)


def test_rotate_buttons_step_and_clamp(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    rotate = panel._perf._rotate
    rotate.set_degrees(29)
    rotate._plus.click()
    assert rotate.degrees() == 30
    assert tasks[-1][0] == "sensor"
    rotate._plus.click()  # 已到上限，不再重复下发
    assert rotate.degrees() == 30
    rotate._minus.click()
    assert rotate.degrees() == 29
    assert tasks[-1][-1]["rotate_degrees"] == 29


def test_rotation_kept_when_other_sensor_changes(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """改别的性能项时不带角度，交给协议层沿用设备读回值。"""
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel.on_snapshot(_snap(config=replace(SAMPLE, rotate_raw=12)))
    tasks.clear()
    assert panel._perf._rotate.degrees() == 12
    panel._perf._line.toggle.set_on(True, emit=True)
    assert "rotate_degrees" not in tasks[-1][1]


def test_click_off_the_ring_does_not_move_knob(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """点在刻度环以外的空白处，圆钮不能跳角度，也不能下发写命令。"""
    panel, tasks = _panel(tmp_path, monkeypatch)
    dial = panel._perf._rotate._dial
    dial.resize(240, 240)
    dial.set_degrees(10)
    tasks.clear()
    c, radius = dial._center(), dial._radius()
    spots = (
        QPointF(4.0, 4.0),  # 控件左上角
        QPointF(c.x() + radius * 0.5, c.y() - radius * 0.5),  # 环与读数之间
        QPointF(c.x(), c.y() + radius + 60),  # 环外侧
    )
    for spot in spots:
        event = _press(spot)
        dial.mousePressEvent(event)
        dial.mouseReleaseEvent(event)
    assert dial.degrees() == 10
    assert tasks == []

    # 按在圆钮上仍然可以拖动
    dial.mousePressEvent(_press(dial._point_at(10, radius + 2)))
    assert dial._dragging is True


def test_rotate_drag_without_change_writes_nothing(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    dial = panel._perf._rotate._dial
    dial.resize(240, 240)
    dial._dragging = True
    dial._drag_from = dial.degrees()
    dial.mouseReleaseEvent(None)
    assert tasks == []


def test_game_mode_labels(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, _tasks = _panel(tmp_path, monkeypatch)
    assert [b.text() for b in panel._perf._mode._buttons] == [
        "性能模式",
        "电竞模式",
        "超竞模式",
    ]


def test_xy_independent_packs_vals(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    panel, tasks = _panel(tmp_path, monkeypatch)
    panel._dpi._xy.blockSignals(True)
    panel._dpi._xy.setChecked(True)
    panel._dpi._xy.blockSignals(False)
    for card in panel._dpi._cards:
        card.set_xy(True)
    panel._dpi._cards[0]._y_spin.setValue(1600)
    panel._dpi._commit_table()
    _kind, dpis, _count, _index, vals = tasks[-1]
    assert dpis[0] == 200
    assert vals[0] == 1600
    assert vals[1] == dpis[1]
