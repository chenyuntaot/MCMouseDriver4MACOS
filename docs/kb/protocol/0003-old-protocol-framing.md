---
id: 3
title: 旧协议报文框架（A7 V2 及更早型号，Feature Report + XOR 0xFF）
category: protocol
status: analyzed
source: web-bundle
firmware: 5.15.0.9（A7 V2 Pro+，部分结论已真机互证）
date: 2026-08-08
---

# 旧协议报文框架（Feature Report + XOR 0xFF）

适用设备（analyzed，来源官方分流函数 `Fj`，purify.js:127294 + 名单 `_H` 127278）：
A7 / A7 V2 全系、M7/L7/K7 V1、AX5 等旧型号走本协议；
**A7 V3 全系走新协议（kb/0004，output report 0x4D）**。

行号均为 `_reverse/web/pretty/purify.es-B28R1Od0.js`（2026-08-08 快照）。

## 1. 接口选择

- 配置接口：usage_page **0xFF01** 或 **0xFF0B**（官方过滤器 65281/65291，
  purify.js:137387-137487；真机枚举见 kb/0002，两个接口都存在）。
- WebHID 不显式选 collection，按 reportId 路由；hidapi 侧打开 0xFF01 接口即可
  （0xFF0B 备选，两者实测行为一致）。
- reportId：**0x11 = 短包（数据 20 字节）**，**0x12 = 长包（数据 64 字节）**。

## 2. 编码规则（verified，真机互证）

- 发送：payload **逐字节 XOR 0xFF（取反）** 后 `sendFeatureReport`；
  不足长度部分填 0xFF（即原始 0x00 取反）。
  组包代码：读 `Oc`（76533-76558）、写 `yl`（76981-77004）。
- 接收：`receiveFeatureReport` 返回 DataView，首字节为 reportId（原始值，不取反），
  其后字节**取反**后解析；byte[1] 取反 = 子命令回显，与请求比对，不等则重试
  （76598-76604，官方日志"指令混发了"）。
- 真机互证：kb/0002 实机记录 2 —— 原始 `fb f7 ca d1 ce ca d1 cf d1 c6` 取反 =
  `04 08 "5.15.0.9"`，即子命令 0x04（读固件版本）+ 长度 + ASCII 版本号。

## 3. 读命令表（order 表 `UH`，purify.js:76418-76430）

order 字符串含 reportId 字节（如 `"0x11 0x04"` = reportId 0x11、子命令 0x04）：

| 命令 | 含义 | parser |
|---|---|---|
| `0x11 0x03` | 读绑定信息（bond/vid/pid/connect/game） | Dwt (76260) |
| `0x11 0x04` | 读固件版本（versionLength + ASCII） | _wt (76268) |
| `0x11 0x06` | 读设备信息（vid/pid/fwVersion u32/connectMode bit3/connectStatus bit1/**batteryLevel/chargeStatus**） | Xwt (76277) |
| `0x12 0x67` | 读整份配置（profileIndex、DPI×6、回报率索引、sensor、按键×6） | Awt (76288-76366) |
| `0x12 0x65` | 读宏 | Pwt (76369) |
| `0x12 0x63` | 读板载配置名 | Kwt (76392) |
| `0x11 0x1b` | 读灯光 | qwt (76398) |
| `0x12 0x68 00/01/02` | 读板载名（分 3 页） | (76415-76417) |
| `0x12 0x77` | （待查） | Hwt (76380) |

读接收器固件版本：order 改为 `11 04 AA 00…`（`NW(2)`，76431-76437）。

## 4. 写命令表（schema `UMt` 76919-76934 + 序列化器 `MO` 76949，定义 76715-76918）

| 命令 | 含义 | schema |
|---|---|---|
| `0x11 0x40` | 设 DPI 6 档（usbDpiIndex/gDpiIndex/dpi0..5 u16 LE/sum） | rMt (76720) |
| `0x12 0x40` | 设 DPI（含 X/Y 拆分） | lMt (76733) |
| `0x11 0x41` | 设回报率（usbRate/freeRate） | hMt (76774) |
| `0x11 0x42` | 性能设置（lod/ripple/line/motionSync/gameMode/rotate） | uMt (76762) |
| `0x11 0x43` | 休眠时间 | dMt (76758) |
| `0x11 0x0A` | 休眠开关 | cMt (76753) |
| `0x12 0x52` | 设按键（buttonIndex/buttonType/buttonValue u24） | fMt (76836) |
| `0x12 0x55` | 写宏头 | pMt (76829) |
| `0x12 0x57` | 写整份配置 | mMt (76779-76828) |
| `0x11 0x58` | 切板载配置（profileIndex） | vMt (76915) |
| `0x11 0x2B` / `0x12 0x2D` | 灯光 | gMt (76847) / bMt (76865) |
| `0x12 0x59` | 写板载名（直接字节数组） | (127616) |

## 5. 通知（input report，`QCe` 76640-76713）

- 首字节 raw 0x1A = 命令完成通知（取反后显示 "e5"），第二字节 = 命令回显；
  任务队列按命令字匹配（76700-76707）。`EJ` 路径（76442-76520）等到通知后再
  `receiveFeatureReport` 取数据。
- 首字节 raw 0x1D = 设备主动状态上报（"e2"）：连接状态、DPI 档位、电量、
  充电状态、板载切换（76652-76696）。
- reportId 44/45 被跳过（76645）；通知到达时的 reportId 代码未校验（未知，需抓包）。
- 超时/重试：写任务超时 200ms、看门狗 150（78426-78427）；读重试至多 5 次（76501）；
  `EJ` 收响应超时 600ms（76498）。

## 6. A7 V2 Pro+ 能力表（`Xf` 89074-89080）

- `pids`: ["16419"（有线）, "4106"（1K 接收器）, "4107"（8K 接收器）, "4128"（8K 接收器 VID 21075）]
- `rate`: [8K, 1K, 8K, 8K]（与 pids 按下标对应）
- `lod`: 1mm / 2mm
- 默认 DPI 6 档：200/1200/2200/3200/4200/26000；dpiMax 26000
- 固件版本表：鼠标 "5.48.1.4"（j5t 89204-89217）、接收器 "5.48.2.4"（yRe 89218-89227）
  ——这是官方最新版参照，本机实测 5.15.0.9（kb/0002）。

## 7. 未决问题（hypothesis，需抓包/实验）

1. 旧协议 feature 响应 byte[0] 是否为主命令回显（真机数据显示为子命令 0x04，
   即响应布局为 [reportId][子命令][数据]，与代码注释的 byte[1] 说法差一个偏移——
   差异来自 WebHID DataView 是否含 reportId 字节，实现时以真机为准）。
2. e2/e5 通知到达的 reportId。
3. `0x12 0x77` 命令含义。

## 8. 调试技巧（事实）

官方页面控制台可直接调 `navigator.testCommand`（= `Oc` 读）、
`navigator.testSetCommand`（= `yl` 写）（76639、77035），用于真机对照实验。

## 修订记录

- 2026-08-08 初版（Web bundle 静态分析 + kb/0002 真机数据互证 XOR 编码）。
