"""生成 App 图标 AppIcon.icns（自绘，不使用任何官方素材）。

图形与菜单栏图标同源（空心鼠标轮廓），
这里画成 macOS 圆角矩形应用图标：渐变底 + 白色鼠标 + 滚轮。

用法：uv run python packaging/make_icon.py build/AppIcon.icns
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

# iconutil 要求的文件名 → (像素边长, 缩放倍率)
# 倍率决定 PNG 里写的分辨率元数据：1x=72dpi、2x=144dpi。
# 写成别的值（Qt 默认 96dpi）iconutil 会直接报 "Invalid Iconset"。
ICONSET_SIZES: dict[str, tuple[int, int]] = {
    "icon_16x16.png": (16, 1),
    "icon_16x16@2x.png": (32, 2),
    "icon_32x32.png": (32, 1),
    "icon_32x32@2x.png": (64, 2),
    "icon_128x128.png": (128, 1),
    "icon_128x128@2x.png": (256, 2),
    "icon_256x256.png": (256, 1),
    "icon_256x256@2x.png": (512, 2),
    "icon_512x512.png": (512, 1),
    "icon_512x512@2x.png": (1024, 2),
}

DPI_PER_SCALE = 72  # macOS 逻辑分辨率基准
INCH_PER_METER = 1 / 0.0254


def render(size: int) -> QPixmap:
    """按目标边长直接绘制，避免缩放导致的糊边。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 底板：macOS 应用图标留白约 1/16，圆角约边长的 22.5%
    inset = size / 16
    plate = QRectF(inset, inset, size - inset * 2, size - inset * 2)
    radius = plate.width() * 0.225
    gradient = QLinearGradient(plate.topLeft(), plate.bottomRight())
    gradient.setColorAt(0.0, QColor("#4a90e2"))
    gradient.setColorAt(1.0, QColor("#1d4ed8"))
    plate_path = QPainterPath()
    plate_path.addRoundedRect(plate, radius, radius)
    painter.fillPath(plate_path, gradient)

    # 鼠标本体：宽高比 11:15.5，与菜单栏图标一致
    body_w = plate.width() * 0.42
    body_h = body_w * 15.5 / 11
    body = QRectF(
        plate.center().x() - body_w / 2,
        plate.center().y() - body_h / 2,
        body_w,
        body_h,
    )
    body_path = QPainterPath()
    body_path.addRoundedRect(body, body_w / 2, body_w / 2)
    painter.fillPath(body_path, QColor("#ffffff"))

    # 滚轮：上部竖线，细节在 32px 以下会糊，直接省略
    if size >= 32:
        pen_w = max(1.0, body_w * 0.09)
        painter.setPen(
            QPen(
                QColor("#1d4ed8"), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
            )
        )
        wheel_x = body.center().x()
        painter.drawLine(
            QPointF(wheel_x, body.top() + body_h * 0.14),
            QPointF(wheel_x, body.top() + body_h * 0.30),
        )
    painter.end()
    return pix


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: make_icon.py <输出的 .icns 路径>", file=sys.stderr)
        return 2
    out = Path(sys.argv[1]).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # 离屏渲染，不需要窗口服务
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    app = QGuiApplication(["make_icon", "-platform", "offscreen"])

    iconset = out.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    for name, (size, scale) in ICONSET_SIZES.items():
        image = render(size).toImage()
        dots_per_meter = round(DPI_PER_SCALE * scale * INCH_PER_METER)
        image.setDotsPerMeterX(dots_per_meter)
        image.setDotsPerMeterY(dots_per_meter)
        if not image.save(str(iconset / name)):
            print(f"写入失败: {name}", file=sys.stderr)
            return 1

    subprocess.run(
        ["iconutil", "--convert", "icns", str(iconset), "--output", str(out)],
        check=True,
    )
    print(f"图标已生成: {out}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
