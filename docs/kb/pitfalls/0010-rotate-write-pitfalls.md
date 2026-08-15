---
id: 10
title: 踩坑：角度旋转的单位误读、顺带改写与盘面误触
category: pitfalls
status: verified
source: live-test
firmware: A7 V2 Pro+（2026-08-15 与官方软件互读验证）
date: 2026-08-15
---

# 踩坑：角度旋转的单位误读、顺带改写与盘面误触

角度旋转（`rotateOpen` / `rotateVal`，布局见 kb/0005 §3.3）踩了三个坑，
第一个会让写进设备的角度是错的，后两个会让设备角度被莫名其妙改掉。

## 1. rotateVal 就是度数，不是「度数 / 4」**【verified】**

早期从 Web bundle 读出的结论是「rotateVal = 度数 / 4」，**这是错的**。

取证（2026-08-15）：本程序按 4°/步 写入 12°，实际发出 `rotateVal=3`；
关闭本程序后用官方软件读取，官方显示 **3°**。官方的度数就是 rotateVal 原值，
因此单位是 **1°/步**。

这也解释了读回逻辑里那个一直没想通的阈值：`rotateVal > 30` 视为负值，
说明可用值域就是 `[-30, 30]`，即 **量程 ±30°**——正好是官方界面上的量程。
如果单位真是 4°，量程会是 ±120°，没有哪个鼠标驱动会给出这种量程，
这个不自洽当时就该引起警觉。

**教训**：当推导出的量程明显不像产品会提供的量程时，多半是单位推错了；
拿官方软件互读一次就能证伪（本程序写入 → 官方读取，看两边数字是否一致）。

## 2. 写传感器时不要顺带改写角度

`0x11 0x42` 是一条整包命令，九个字节要一次写全，因此
`build_write_sensor_from_config()` 会以读回的配置为底。
坑在于：如果调用方每次都把界面上的角度一起传进来，那么改 LOD、波纹、直线修正、
Motion Sync、电竞模式中的**任意一项**，都会把界面上那个角度写回设备。
一旦界面显示的角度与设备实际值不同（例如上面的单位错误期间），
用户只是切了个 LOD，设备角度就被静默改掉了。

规则：**只有用户真的动了角度控件，才传 `rotate_degrees`；否则传 `None`，
让协议层沿用 `cfg.rotate_raw` 原样写回。** CLI 的 `_sensor_roundtrip()` 一直是这么做的，
GUI 的性能页曾经不是（已修，见 `PerformancePage._commit_sensor`）。

## 3. 刻度盘的可拖动区域不能是整个控件矩形

自绘刻度盘控件的矩形远大于刻度环本身。若 `mousePressEvent` 里只排除中心读数区、
其余一律当作拖动，那么点一下卡片上看起来空白的地方（控件四角、环与读数之间的空隙），
圆钮就会「闪」到那个方位，并顺带下发一次写命令。

规则：按下时先做命中测试，只有落在**圆钮抓取半径内**或**刻度环附近的环带内**
（且在量程扇区内）才开始拖动，其余位置 `event.ignore()`。
同时用 `setMouseTracking(True)` 只在可拖动区域显示手型光标，
不要给整个控件挂手型——那是在骗用户。

## 相关代码与测试

- `src/mcmouse/protocol/old.py`：`ROTATE_UNIT_DEGREES` / `ROTATE_MAX_STEPS`、
  `encode_rotate()`、`quantize_rotate()`、`MouseConfig.rotate_degrees`
- `src/mcmouse/hub/widgets.py`：`RotateGauge` / `_RotateDial._is_grab()`
- `tests/test_protocol_old_commands.py::test_rotate_roundtrip_and_quantize`
- `tests/test_ui_hub_panel.py::test_rotate_degrees_written_verbatim`
- `tests/test_ui_hub_panel.py::test_click_off_the_ring_does_not_move_knob`

## 修订记录

- 2026-08-15：建立条目，记录量程不自洽与「改其他项顺带改写角度」两个坑。
- 2026-08-15：与官方软件互读后推翻「4°/步」的旧结论，改为 1°/步、量程 ±30°，
  status 升为 verified；补充刻度盘命中测试的坑（§3）。
