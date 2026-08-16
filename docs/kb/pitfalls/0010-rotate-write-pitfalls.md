---
id: 10
title: 踩坑：角度旋转的单位误读、顺带改写、0° 编码与盘面误触
category: pitfalls
status: verified
source: live-test
firmware: A7 V2 Pro+（2026-08-15 与官方软件互读验证）
date: 2026-08-15
---

# 踩坑：角度旋转的单位误读、顺带改写、0° 编码与盘面误触

角度旋转（`rotateOpen` / `rotateVal`，布局见 kb/0005 §3.3）踩了五个坑，
第一个会让写进设备的角度是错的，中间两个会让设备角度被莫名其妙改掉，
后两个会让界面上的角度自己跳。

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

## 4. 设 0° 不能发 rotateOpen=0 **【analyzed，症状真机复现】**

官方刻度盘组件对**任何角度（含 0°）都发 `rotateOpen: 1`**：
`we()` 组包时 `rotateOpen: 1` 写死、`rotateVal = 度数 >= 0 ? 度数 : 度数+256`，
清零入口 `Ge` 也走 `we(0)` → 发 (1, 0)（bundle 135497-135502、152497-152510）。

本程序早期 `encode_rotate(0)` 返回 (0, 0)——试图用 open=0 表达「关闭旋转」。
真机症状（2026-08-16 用户报告）：UI 设 0° 后刻度盘会自己跳回 -1° 或旧值；
-1° 按读回解码即 rotateVal=255（0xFF），推测设备收到 open=0 后 byte49
进入未定义状态、读回 0xFF（或保留旧值）。该 byte 级推断尚无抓包样本，
待下次真机取证补录；但「对齐官方恒发 open=1」本身即可消除该状态。

连带坑：`build_write_sensor_from_config()` 在**不传角度**时曾算
`rotate_open = 1 if cfg.rotate_raw else 0`——设备正处 0° 时改任何其他
性能项（LOD/波纹/模式…）都会顺带把 open=0 发下去，把设备推进同一脏状态。

规则：**rotateOpen 恒写 1**；0° 就是 (1, 0)。

## 5. 1° 步进下，刻度盘的绝对映射与隐形命中带都会「自己跳」

单位是 1° 后（§1），盘面 1° 只有约 6px（半径 ~86px、量程弧 250°），
官方组件的交互习惯在这里会翻车：

- **抓取瞬移**：按下即把值设为指针落点角度（官方也是绝对映射，但其 4°/步
  一步有 ~25px，误差被步进吃掉）。1°/步下按在圆钮边缘偏 4~6px，值就跳 ±1~3°，
  松手还顺带下发一次写。修复：按在圆钮上时记录指针-圆钮角差，
  拖动按差值跟随；点刻度环仍绝对跳到落点。
- **落不进 0**：瞄准顶部想设 0°，偏 6px 就是 ±1°。修复：指针落点在 ±1° 内
  一律算 0（磁吸）；代价是盘面拖不出 ±1°，用两侧 +/− 按钮可达。
- **隐形命中带太宽**：圆钮可见半径 11px 而抓取半径曾给 20px、刻度环带曾给
  ±22px，点「看起来空白」的地方落在带内，圆钮就闪到那个角度并写设备，
  表现为「点空白处有时跳有时不跳」。修复：命中带收紧到贴近可见元素
  （圆钮 14px、环带 ±10px）。
- **轮询回填抢拖动**：60s 轮询快照回填 `set_degrees()` 若不避让拖动，
  会把用户手里的圆钮拽走。修复：拖动中忽略回填（与 `HubSlider.set_value`
  同一策略）。

## 相关代码与测试

- `src/mcmouse/protocol/old.py`：`ROTATE_UNIT_DEGREES` / `ROTATE_MAX_STEPS`、
  `encode_rotate()`、`quantize_rotate()`、`MouseConfig.rotate_degrees`
- `src/mcmouse/hub/widgets.py`：`RotateGauge` / `_RotateDial._is_grab()`
- `tests/test_protocol_old_commands.py::test_rotate_roundtrip_and_quantize`
- `tests/test_ui_hub_panel.py::test_rotate_degrees_written_verbatim`
- `tests/test_ui_hub_panel.py::test_click_off_the_ring_does_not_move_knob`
- `tests/test_ui_hub_panel.py::test_rotate_dial_zero_detent`
- `tests/test_ui_hub_panel.py::test_click_knob_without_move_keeps_angle`
- `tests/test_ui_hub_panel.py::test_snapshot_ignored_while_dragging_dial`

## 修订记录

- 2026-08-15：建立条目，记录量程不自洽与「改其他项顺带改写角度」两个坑。
- 2026-08-15：与官方软件互读后推翻「4°/步」的旧结论，改为 1°/步、量程 ±30°，
  status 升为 verified；补充刻度盘命中测试的坑（§3）。
- 2026-08-16：新增 §4（0° 发 rotateOpen=0 导致设备读回 0xFF→-1°，症状真机
  复现、byte 级推断待抓包；encode/build_write_sensor_from_config 已改恒 open=1）
  与 §5（1° 步进下的绝对映射、0° 磁吸、命中带宽与轮询回填四个交互坑）。
