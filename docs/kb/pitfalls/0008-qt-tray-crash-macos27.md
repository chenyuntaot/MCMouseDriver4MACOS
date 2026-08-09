---
id: 8
title: 踩坑：macOS 27 上 Qt 托盘菜单必崩（QTBUG-147449）与绕行
category: pitfalls
status: verified
source: live-test
firmware: 不适用
date: 2026-08-09
---

# 踩坑：macOS 27 上 Qt 托盘菜单必崩（QTBUG-147449）与绕行

## 现象

菜单栏应用（PySide6 6.11.1）启动正常，托盘图标出现，但**点击图标必现崩溃**：
`NSInternalInconsistencyException: Invalid message sent to event "NSEvent:
type=SysDefined/KitDefined ..."`，栈顶 `-[NSEvent clickCount]` ←
`libqcocoa.dylib` ← `NSMenuTrackingSession sendBeginTrackingNotifications`。

## 定性

已知 Qt bug：[QTBUG-147449](https://qt-project.atlassian.net/browse/QTBUG-147449)，
复现报告见 [ungive/qt-trayicon-crash-macos27](https://github.com/ungive/qt-trayicon-crash-macos27/blob/main/README.md)。
macOS 27 上状态栏菜单弹出时，系统合成的事件不支持 `clickCount`，
libqcocoa 的菜单跟踪观察者无条件调用它导致崩溃。Qt 6.6.3～6.12.0 全部受影响，
截至 2026-08-09 无官方修复。**与我们的代码无关**，任何 `QSystemTrayIcon`
原生菜单在该系统上都会崩。

## 绕行（已实施）

- 不使用 `QSystemTrayIcon.setContextMenu`（NSMenu 弹出一律避开）；
  托盘点击改走 `activated` 信号，弹**自绘 Qt 弹层**（`TrayPopup`，
  纯 QWidget + Qt.Popup，不经 NSMenu），承载状态显示与 DPI/回报率快捷切换。
- 设置面板本来就是普通 Qt 窗口，不受影响。
- 副作用：失去原生菜单外观，换来完全可控的弹层（也算是主流菜单栏应用做法）。

## 备选路线讨论（2026-08-09 用户决策）

曾评估改用 SwiftUI（NSStatusItem + NSPopover 原生范式，无 Qt 依赖，
协议层按 kb/0003-0007 移植 Swift）：**用户决定继续 Qt 路线**，
SwiftUI 重写留作后备。若 Qt 再出平台级问题，重启该评估。

## 修订记录

- 2026-08-09 初版。
