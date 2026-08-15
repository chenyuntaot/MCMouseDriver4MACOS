"""左栏：设备状态、板载三配置、本机自定义配置。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .. import profiles
from .theme import ROLE_NAMES, apply_hub_font, palette
from .widgets import GhostButton, HubCard, PrimaryButton, SecondaryButton, muted_label

Submit = Callable[..., None]

ONBOARD_LABELS = ("默认板载", "默认板载 2", "默认板载 3")


class _ProfileRow(HubCard):
    def __init__(self, title: str, *, clickable: bool = True) -> None:
        super().__init__(clickable=clickable)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        self._title = QLabel(title)
        apply_hub_font(self._title, 13, QFont.Weight.Medium)
        layout.addWidget(self._title, 1)
        self._mark = QLabel("✓")
        apply_hub_font(self._mark, 13, QFont.Weight.DemiBold)
        self._mark.hide()
        layout.addWidget(self._mark)
        self._refresh_colors()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._refresh_colors()
        )

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_selected(self, selected: bool) -> None:
        self.set_active(selected)
        self._mark.setVisible(selected)
        self._refresh_colors()

    def _refresh_colors(self) -> None:
        p = palette()
        color = p.accent if self._active else p.text
        self._title.setStyleSheet(f"color: {color}; background: transparent;")
        self._mark.setStyleSheet(f"color: {p.accent}; background: transparent;")


class Sidebar(QWidget):
    def __init__(self, submit: Submit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HubSidebar")
        self.setFixedWidth(248)
        self._submit = submit
        self._updating = False
        self._snapshot = None
        self._custom_names: list[str] = []
        self._selected_custom: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 18, 16, 16)
        root.setSpacing(10)

        self._model = QLabel("正在读取设备…")
        apply_hub_font(self._model, 18, QFont.Weight.DemiBold)
        self._model.setWordWrap(True)
        root.addWidget(self._model)

        status = QHBoxLayout()
        status.setSpacing(10)
        self._battery = muted_label("电量 —")
        self._role = muted_label("未连接")
        status.addWidget(self._battery)
        status.addWidget(self._role)
        status.addStretch()
        root.addLayout(status)

        self._create = PrimaryButton("+  创建配置")
        self._create.clicked.connect(self._on_create)
        root.addWidget(self._create)
        self._import = SecondaryButton("导入")
        self._import.clicked.connect(self._on_import)
        root.addWidget(self._import)

        root.addWidget(muted_label("板载配置"))
        self._onboard: list[_ProfileRow] = []
        for i, label in enumerate(ONBOARD_LABELS):
            row = _ProfileRow(label)
            row.setObjectName(f"Onboard{i}")
            row.clicked.connect(lambda i=i: self._on_onboard(i))
            self._onboard.append(row)
            root.addWidget(row)

        custom_head = QHBoxLayout()
        custom_head.addWidget(muted_label("自定义配置"))
        custom_head.addStretch()
        self._count_lab = muted_label("0")
        custom_head.addWidget(self._count_lab)
        self._delete = GhostButton("删除")
        self._delete.clicked.connect(self._on_delete)
        custom_head.addWidget(self._delete)
        root.addLayout(custom_head)

        self._hint = muted_label("点击下方配置即可写入鼠标。")
        root.addWidget(self._hint)

        self._custom_box = QVBoxLayout()
        self._custom_box.setSpacing(6)
        root.addLayout(self._custom_box)
        root.addStretch()

        self.reload_custom()
        self._apply_chrome()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self._apply_chrome()
        )

    def _apply_chrome(self) -> None:
        p = palette()
        self.setStyleSheet(f"QWidget#HubSidebar {{ background: {p.sidebar}; }}")

    def set_updating(self, updating: bool) -> None:
        self._updating = updating

    def on_snapshot(self, snap) -> None:  # noqa: ANN001
        self._snapshot = snap
        sleeping = snap.config is None
        self._model.setText(snap.variant.model.replace("MCHOSE ", ""))
        extra = " · 充电中" if snap.charge_status else ""
        self._battery.setText(f"电量 {snap.battery}%{extra}")
        role = ROLE_NAMES.get(snap.variant.role, snap.variant.role)
        if sleeping:
            self._role.setText(f"{role} · 休眠")
        else:
            self._role.setText(role)
        index = 0 if sleeping else int(snap.config.profile_index)
        for i, row in enumerate(self._onboard):
            row.set_selected(i == index and not sleeping)
        self.reload_custom()

    def show_error(self, message: str) -> None:
        self._model.setText("未连接")
        self._battery.setText("电量 —")
        self._role.setText(message)
        for row in self._onboard:
            row.set_selected(False)

    def reload_custom(self) -> None:
        names = sorted(profiles.load_profiles())
        self._custom_names = names
        self._count_lab.setText(str(len(names)))
        while self._custom_box.count():
            item = self._custom_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not names:
            empty = muted_label("还没有本机配置")
            self._custom_box.addWidget(empty)
            return
        for name in names:
            row = _ProfileRow(name)
            row.set_selected(name == self._selected_custom)
            row.clicked.connect(lambda n=name: self._on_custom(n))
            self._custom_box.addWidget(row)

    def _on_onboard(self, index: int) -> None:
        if self._updating:
            return
        self._submit("switch_profile", index)

    def _on_custom(self, name: str) -> None:
        if self._updating:
            return
        self._selected_custom = name
        self.reload_custom()
        try:
            cfg = profiles.config_from_dict(profiles.load_profiles()[name])
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "配置无效", str(exc))
            return
        self._submit("apply_config", cfg)

    def _on_create(self) -> None:
        name, ok = QInputDialog.getText(self, "创建配置", "配置名")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入配置名")
            return
        self._submit("save_profile", name)
        self._selected_custom = name
        self.reload_custom()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            cfg = profiles.import_profile(Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._submit("apply_config", cfg)

    def _on_delete(self) -> None:
        name = self._selected_custom
        if not name:
            return
        profiles.delete_profile(name)
        self._selected_custom = None
        self.reload_custom()
