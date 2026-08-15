---
id: 6
title: 旧协议按键映射、宏、灯效与电量
category: protocol
status: analyzed
source: web-bundle
firmware: 5.15.0.9（A7 V2 Pro+）
date: 2026-08-08
---

# 旧协议按键映射、宏、灯效与电量

帧格式见 kb/0003，功能命令总览见 kb/0005。行号为
`_reverse/web/pretty/purify.es-B28R1Od0.js`（2026-08-08 快照）。

## 1. 按键映射

### 1.1 物理键索引（`kB`，77600）

`{0: 左键, 1: 中键, 2: 右键, 3: 前进, 4: 后退}`（读配置返回 6 组，索引 5 待查）。

### 1.2 功能类型 buttonType（129613-129654）

| type | 功能 | value 编码（3 字节 BE） |
|---|---|---|
| 0 | 恢复默认 | 0 |
| 1 | 鼠标键 | byte0=按钮位掩码：01 左/02 右/04 中/08 后退/10 前进；滚轮上 `0x000200`、下 `0x00FE00`（byte1=±2 有符号） |
| 2 | 键盘键（含组合键） | `[修饰键掩码, HID Usage ID, 0x00]`，修饰掩码=标准 HID（bit0 LCtrl…bit3 LGUI），如 Ctrl+A=`0x010400`；完整键表 `Voe` 77119-77262。单独修饰键（Shift/Ctrl/Option/Cmd）写入 usage `0xE0-0xE3`（Left Ctrl/Shift/Alt/GUI）、掩码 0，如 Shift=`0x00E100`；多修饰键和弦写掩码、usage 0 |
| 3 | 多媒体 | byte0=Consumer usage 低字节：音量+ E9、音量- EA、静音 E2、播放暂停 CD、上一曲 B6、下一曲 B5、停止 B7 |
| 4 | 宏 | 固定 `0x000000`，宏名/宏数据另存（见 §2） |
| 5 | DPI | 切换 `0x010000`、DPI+ `0x020000`、DPI- `0x030000` |
| 7 | 保留（空表 `WFe`） | — |
| 8 | 屏幕亮度/剪贴板 | 亮度± `0x0C6F00`/`0x0C7000`；复制 `0x070106`、剪切 `0x07011B`、粘贴 `0x070119` |
| 9 | 禁用 | `0xFFFFFF` |
| 10 | 板载配置切换 | 配置 1/2/3 = `0x010000/0x020000/0x030000`，循环 = `0x040000` |

### 1.3 写单键 `0x12 0x52`（parser `fMt` 76836）**【verified】**

逻辑数据：`[buttonIndex, reserved, buttonType, buttonValue(3 字节 BE)]`。
恢复单键默认：type=0, value=0（129739-129745）。
真机验证（2026-08-09）：后退键改 DPI 切换再恢复，读回一致（`mcmouse button set`）。

### 1.4 复位 `0x11 0x0B`（parser `yMt`）

`[0x0B, data u16]`：data=257（0x0101）= 全部按键恢复默认（129794）；
data=43520（0xAA00）= 恢复出厂（138062）。⚠️ u16 字节序未逐字节验证（hypothesis）。

### 1.5 ⚠️ 读写布局不镜像（踩坑预警）

写整档 `0x12 0x57` 的按键字节是 **高4位 buttonIndex | 低4位 buttonType**，
而读 `0x12 0x67` 是 **高4位 buttonType | 低4位 buttonIndex**；rate/dpi 的
nibble 排布读写也相反（kb/0005 §3.4）。实现时必须按方向分别组包。

## 2. 宏（V2）**【verified，需固件 5.42.2.4+】**

存储模型：宏库在 Web 端（localStorage/云端），设备端每个按键槽位存一份宏数据+宏名；
板载宏槽 = 6 个按键槽（buttonIndex 0-5）。
真机验证（2026-08-09，固件 5.42.2.4）：绑定（先 0x52）→ 写数据（0x55，
bundle 取反编码）→ 写名（0x53）→ 物理触发成功；官方 App 可读回本工具写入的宏。
旧固件 5.42.0.9 宏引擎失效、且事件需逻辑原形（kb/0007 §7）。

### 2.1 写宏 `0x12 0x55`（`RH()` 77771，64 字节分包）

- 首包头 12 字节（`WMt` 77601）：`[0x55, buttonIndex, moreData, offsetLo, offsetHi,
  length, trigger(固定1), conditionLo, conditionHi, timeLo, timeHi, count]`，
  随后最多 52 字节事件；续包头 6 字节（`QMt`，无 trigger/condition/time/count）
  + 58 字节事件，offset 每次 +58，末包 moreData=0（77834-77852）。
- 头部字段照常 XOR 0xFF；**事件字节在构造时已预先取反，线上原样发**（77830）。
- condition u16 = 触发方式：按住循环 0x2001 / 循环至同键 0x4001 / 执行一次 0x0001 /
  循环至任意键 0x6001（`LMt` 77643）。
- time u16 默认 0，含义未知（hypothesis）。

### 2.2 宏事件编码（4 字节定长，77776-77807）**【verified】**

线上发送为下表逐字节 **XOR 0xFF**（官方 bundle 形态，新固件 5.42.2.4 验证）。
旧固件 5.42.0.9 相反地要求逻辑原形（kb/0007 §7）；`ev_*` 构造器默认取反，
`inverted=False` 得逻辑原形，会话层写后读回自动适配。逻辑布局：

| 事件 | 字节布局 |
|---|---|
| 键盘按下 | `[00, 81, usage, 00]`（标准 HID usage，表 `xoe` 77900） |
| 键盘释放 | `[00, 01, usage, 00]` |
| 延迟 | `[00, 0F, msLo, msHi]`，ms u16 LE，1-60000（84342 钳制） |
| 鼠标键按下/释放 | `[00, 88 / 08, 按钮位, 00]`（位：左1 右2 中4 后退8 前进16） |
| 滚轮 | `[00, 05, 01 上 / FF 下, 00]` |

单宏事件数无硬上限，仅受分包限制。

**写入顺序（kb/0007 §7）**：`0x52` 绑定会清空槽内事件，必须先绑定
（type=4）再写数据（`0x55`）再写名（`0x53`）。

### 2.3 宏名

写 `0x12 0x53`：`[0x53, buttonIndex, nameSize, UTF-8…]`（`GMt` 77644）。
读 `0x12 0x63`：order `12 63 <buttonIndex> 00…`（`vH` 76388），
响应 `{buttonIndex, nameSize, name(UTF-8)}`（`Kwt`）。
读宏数据 `0x12 0x65`/`0x12 0x77` 有 parser 但**全 bundle 无调用点**（死代码，慎用）。

## 3. 灯效：A7 本体无灯

- **A7 系列鼠标本体没有任何 RGB 命令**（代码事实）。"鼠标-灯光设置"页对白名单
  （138910，含 A7 V2 Pro+/Ultra+）渲染的是 **MagDock 座充**灯效组件（135058）。
- `0x11 0x2B` / `0x12 0x2D` 灯效命令仅供 K7 Ultra 键盘（133653 显式设备判断）。
- MagDock 是独立 HID 设备（VID 14391 PID 4114 usagePage 0xFF00，帧首 0xAA）：
  cmd 7 读 / cmd 39 写，模式 0 常亮/1 呼吸/2 闪烁/3 循环/4 流光/5 音乐
  （67402-67482）。帧头/校验未展开（hypothesis，二期再做）。
- **对需求的影响**：FR-4 灯效仅当用户有 MagDock 座充时可做；鼠标本体无灯可控。

## 4. 电量

1. 主动查询 `0x11 0x06`（kb/0005 §1）：batteryLevel = 百分比 0-100；
   **connectMode：0=有线，1=无线 2.4G**（68776、69485 互证）。
2. 设备主动上报 input report 0xE2（XOR 还原后，76642）：
   byte1-2 连接事件（`0001`/`0101`=连接、`0102`=断开）、byte3=chargeStatus、
   byte4=batteryLevel、byte5=dpiIndex、byte8 bit7=设备端切板载。

## 修订记录

- 2026-08-08 初版（Web bundle 静态分析）。
- 2026-08-15 补充单独修饰键编码：type=2 用 HID usage 0xE0-0xE3、掩码 0（固件把 usage 0 当无键）；未真机验证。
