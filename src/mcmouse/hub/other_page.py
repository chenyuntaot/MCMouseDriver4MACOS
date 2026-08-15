"""其他设置：固件信息、宏兜底、恢复出厂。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from .theme import ROLE_NAMES
from .widgets import GhostButton, labeled_block, muted_label

Submit = Callable[..., None]


class OtherPage(QWidget):
    def __init__(self, submit: Submit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._submit = submit
        self._updating = False
        self.setObjectName("OtherPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(14)

        self._info = muted_label("正在读取设备…")
        root.addWidget(labeled_block("设备信息", self._info))

        hint = muted_label(
            "板载宏请到「按键配置」选中按键后点「写入宏」。"
            "恢复出厂会清空鼠标上的 DPI、按键与性能设置，本机已保存的配置不受影响。"
        )
        reset = GhostButton("恢复出厂设置…")
        reset.setObjectName("FactoryReset")
        reset.clicked.connect(self._on_factory_reset)
        root.addWidget(labeled_block("维护", hint, reset))
        root.addStretch()

    def set_updating(self, updating: bool) -> None:
        self._updating = updating

    def on_snapshot(self, snap) -> None:  # noqa: ANN001
        role = ROLE_NAMES.get(snap.variant.role, snap.variant.role)
        sleeping = snap.config is None
        extra = "休眠中" if sleeping else f"板载配置 #{snap.config.profile_index + 1}"
        charge = "充电中 · " if snap.charge_status else ""
        self._info.setText(
            f"{snap.variant.model}\n"
            f"{role} · 固件 {snap.firmware}\n"
            f"{charge}电量 {snap.battery}% · {extra}"
        )

    def show_error(self, message: str) -> None:
        self._info.setText(message)

    def _on_factory_reset(self) -> None:
        if self._updating:
            return
        box = QMessageBox(self)
        box.setWindowTitle("恢复出厂设置")
        box.setText("确定把鼠标恢复为出厂配置？")
        box.setInformativeText("此操作会改写板载设置，无法从软件自动撤销。")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        yes = box.button(QMessageBox.StandardButton.Yes)
        if yes is not None:
            yes.setText("恢复出厂")
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self._submit("factory_reset")
