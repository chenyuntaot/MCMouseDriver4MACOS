---
id: 9
title: 踩坑：打包 .app / DMG 的三个坑（图标 DPI、Qt 裁剪断链、体积）
category: pitfalls
status: verified
source: live-test
firmware: 不适用
date: 2026-08-14
---

# 踩坑：打包 .app / DMG 的三个坑

环境：macOS 27（Apple Silicon）、Python 3.13.12、PySide6 6.11.1、PyInstaller 6.22.0。
构建脚本 `packaging/build_dmg.sh`，配置 `packaging/mcmouse.spec`。

## 坑 1：iconutil 要求 PNG 里的分辨率元数据必须是 72/144 dpi

`iconutil --convert icns` 对 `.iconset` 目录只报一句
`Invalid Iconset.`，不说哪个文件、哪里不对。

实际原因：Qt 保存 PNG 默认写 **96 dpi**，而 iconutil 要求
1x 图为 72 dpi、`@2x` 图为 144 dpi，否则整个 iconset 被判非法
（文件名齐全、像素尺寸正确也照样报错）。

解决：保存前显式设分辨率（`QImage.setDotsPerMeterX/Y`，
72dpi ≈ 2835 dots/m，144dpi ≈ 5669 dots/m），见 `packaging/make_icon.py`
的 `DPI_PER_SCALE` 与 `ICONSET_SIZES`。

排查提示：用 `sips -g dpiWidth <png>` 一眼就能看出来。

## 坑 2：裁剪 Qt 框架会留下断链 symlink，codesign 直接失败

PySide6 装好有 1.2G，必须裁。Python 层 `excludes` 只管模块图，
**管不到 Qt 插件**：插件是二进制依赖，会顺带把整条框架链拖进来——

- `plugins/platforminputcontexts`（虚拟键盘）→ QtVirtualKeyboard + QtQuick + QtQml
- `plugins/imageformats/libqpdf`（PDF 当图片读）→ QtPdf

按产物路径前缀过滤 `a.binaries` / `a.datas` 后，`codesign --verify` 报
`No such file or directory`，且不指出是哪个文件。

实际原因：PyInstaller 还会在 `Contents/Frameworks/` 与 `Contents/Resources/`
下为每个框架建一个**短名 symlink**，其 TOC 条目的 dest 是裸名（如 `QtQuick`），
只有 source 指向框架内部。只按 dest 过滤 → 框架被删、symlink 还在 → 断链。

解决：过滤时 dest 和 source 都要看，见 `mcmouse.spec` 的 `drop_unused_qt()`。

排查提示：`find <app> -type l ! -exec test -e {} \; -print` 列出所有断链。

## 坑 3：体积与内存

裁剪前后（onedir + UDZO 压缩）：

| | .app | DMG |
|---|---|---|
| 裁剪前 | 97M | 40M |
| 裁剪后 | 77M | 32M |

运行时 RSS 约 103M，略超需求文档 §4 的「常驻内存 < 100MB」，
主要来自 PySide6 + Python 运行时，暂不处理，记录备查。

## 验证记录（2026-08-14）

- 真机：A7 V2 Pro+（2.4G 1K 接收器），固件 5.42.2.4。
- `MCMouseDriver.app/Contents/MacOS/MCMouseDriver --selftest`（只读自检）
  读到固件 5.42.2.4、电量 78%、DPI 400/800/1200/1600/6400/26000，通过。
- `codesign --verify --deep --strict` 通过（ad-hoc 签名）。
- `open` 启动后进程常驻，`System Events` 报告为 background only
  → `LSUIElement=1` 生效，无 Dock 图标。
- 首次自检读到电量 0%，第二次 78%：是已知的休眠唤醒问题（kb/0007 §3），
  与打包无关。

## 备注：ad-hoc 签名的分发限制

ad-hoc 签名只保证本机运行。DMG 拷到别的 Mac 上会被 Gatekeeper 隔离，
需 `xattr -dr com.apple.quarantine /Applications/MCMouseDriver.app`
或在「隐私与安全性」里放行。正式签名/公证需 Developer ID，
脚本已留 `MCMOUSE_SIGN_IDENTITY` 入口。

## 修订记录

- 2026-08-14 初版（M3 打包）。
