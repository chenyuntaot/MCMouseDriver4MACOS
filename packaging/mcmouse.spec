# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：MCMouseDriver.app。

要点：
- LSUIElement=1：无 Dock 图标、常驻菜单栏（FR-5），与 gui._set_accessory_policy 互为兜底。
- 只用到 QtCore/QtGui/QtWidgets，其余 PySide6 模块全部排除（装好的 PySide6 有 1.2G）。
- hidapi 是自包含扩展（只链系统 IOKit/CoreFoundation），由 Analysis 自动收进来。

请通过 packaging/build_dmg.sh 调用（图标需先生成）。
"""

import re
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH 由 PyInstaller 注入
VERSION = re.search(
    r'__version__ = "([^"]+)"',
    (ROOT / "src" / "mcmouse" / "__init__.py").read_text(encoding="utf-8"),
).group(1)

# 用不到的 PySide6 子模块：不排除的话 QtQuick/WebEngine/3D 会被一并收进 .app
UNUSED_PYSIDE = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
]

# CLI 与测试链路不进 .app（GUI 入口不 import typer）
UNUSED_OTHER = ["typer", "click", "rich", "pytest", "tkinter", "setuptools", "pip"]

# Python 层 excludes 管不到 Qt 插件：插件是二进制依赖，会顺带拖进整条框架链。
# 这里按产物路径前缀再筛一遍（约 19MB）：
# - platforminputcontexts（虚拟键盘）→ QtVirtualKeyboard + QtQuick + QtQml
# - imageformats/libqpdf（PDF 当图片读）→ QtPdf
# 删掉后 Qt 回落到默认输入上下文；托盘与设置面板只用 QtWidgets，不受影响。
UNUSED_QT_PATHS = (
    "PySide6/Qt/lib/QtPdf.framework",
    "PySide6/Qt/lib/QtQml",  # QtQml / QtQmlMeta / QtQmlModels / QtQmlWorkerScript
    "PySide6/Qt/lib/QtQuick.framework",
    "PySide6/Qt/lib/QtVirtualKeyboard",
    "PySide6/Qt/plugins/platforminputcontexts",
    "PySide6/Qt/plugins/imageformats/libqpdf",
    "PySide6/Qt/qml",
)


def drop_unused_qt(entries):
    """剔除用不到的 Qt 框架与插件。

    要同时看目标路径和来源：PyInstaller 会在 Contents/Frameworks、Contents/Resources
    下为每个框架建一个短名 symlink（dest="QtQuick"，源才指向框架内部）。
    只按 dest 过滤会留下断链，codesign --verify 会直接失败。
    """
    kept = []
    for entry in entries:
        dest, source = entry[0], entry[1]
        paths = [dest] + ([source] if isinstance(source, str) else [])
        if any(p.startswith(UNUSED_QT_PATHS) for p in paths):
            continue
        kept.append(entry)
    return kept

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "app_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=UNUSED_PYSIDE + UNUSED_OTHER,
    noarchive=False,
    optimize=0,
)
a.binaries = drop_unused_qt(a.binaries)
a.datas = drop_unused_qt(a.datas)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MCMouseDriver",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # strip 会破坏 ad-hoc 签名
    upx=False,  # UPX 在 macOS 上会让 dyld 拒绝加载
    console=False,
    target_arch=None,  # 跟随当前架构（Apple Silicon）
    codesign_identity=None,  # ad-hoc 签名在 build_dmg.sh 里统一做
    entitlements_file=None,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MCMouseDriver",
)
app = BUNDLE(  # noqa: F821
    coll,
    name="MCMouseDriver.app",
    icon=str(ROOT / "build" / "AppIcon.icns"),
    bundle_identifier="local.mcmousedriver",
    version=VERSION,
    info_plist={
        "CFBundleName": "MCMouseDriver",
        "CFBundleDisplayName": "MCMouseDriver",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,  # 无 Dock 图标，常驻菜单栏（FR-5）
        "LSMinimumSystemVersion": "14.0",  # 需求 §4 非功能要求
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": (
            "个人学习研究项目，与迈从科技有限公司无隶属关系。"
        ),
    },
)
