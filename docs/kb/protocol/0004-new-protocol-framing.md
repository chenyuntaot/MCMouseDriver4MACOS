---
id: 4
title: 新协议报文框架（A7 V3 等新型号，Output Report 0x4D + XOR 校验）
category: protocol
status: analyzed
source: web-bundle
firmware: 不适用（未接触真机）
date: 2026-08-08
---

# 新协议报文框架（"Nordic"，Output Report）

适用设备（analyzed，名单 `_H`，purify.js:127278-127293）：A7 V3 全系、A5 V3、
K7 V2 Pro+/Ultra+、K5、R7、V7、G3 V3 等新型号。分流函数 `Fj(productName)`
（purify.js:127294）。**本项目目标设备 A7 V2 Pro+ 不用本协议（用 kb/0003）**，
此条目为后续兼容 V3 预留。

## 帧构造（`HYe`，purify.js:125385-125411）

固定 64 字节帧，原始字节（不取反）：

| 偏移 | 含义 |
|---|---|
| 0 | 77（0x4D 'M'），作为 sendReport 的 reportId |
| 1 | 1（推测协议版本） |
| 2 | flags（默认 1 = 带校验） |
| 3 | data 长度 |
| 4-5 | commandId 小端（低字节在前） |
| 6 | bizCode（默认 0） |
| 7 | sequence（默认 0） |
| 8..8+len | data |
| 8+len | XOR 校验（flags==1 时对 byte[2..7+len] 逐字节异或，`aYt` 125380-125384） |

## 收发

- 读 `Ih`（125571-125584）/写 `db`（125774-125787）：`sendReport` 后经
  `inputreport` 事件等响应，回显命令字 = 响应 byte[3]/byte[4]（小端），
  数据 = byte[7:]；默认超时 3000ms；首字节 0xFF 的响应重试至多 5 次间隔 40ms（`XB` 125413）。
- 请求经 `_S` Promise 链串行化（125567-125583）。
- 主动通知：commandId 0x0600 的 input report（`Lq` 125810+），bit 标志位指示
  DPI 上报/电量上报/配置切换/充电状态。

## 命令字（125865-126030 及 parser 表）

| commandId | 方向 | 含义 |
|---|---|---|
| 0x0001 | 读 | 按键配置（data=[profileIndex, 0, 5]） |
| 0x0002 | 读 | 全局信息（profileIndex/rate/sleep/sensor/rotate/去抖） |
| 0x0003 | 读 | DPI（含 X/Y 两个 direction） |
| 0x0009 | 读 | LOD |
| 0x0900 | 读 | 设备信息（vid/pid/电量/充电/连接） |
| 0x0901 | 读 | 固件版本 |
| 0x0905 / 0x090c | 读 | 板载配置名 / 宏名（分页） |
| 0x0101 | 写 | 按键 |
| 0x0102 | 写 | 全局信息 |
| 0x0103 / 0x0104 | 写 | DPI 整表 / 单档 DPI |
| 0x0105 | 写 | 恢复默认 |
| 0x0109 | 写 | LOD |
| 0x0906 | 写 | 切板载配置 |
| 0x0910 | 写 | 板载配置名 |

## V3 能力表（`JS` 127144-127277）

A7 V3：pids [16432, 4116, 4120]，dpiMax 26000；A7 V3 Pro：16433，42000；
A7 V3 Pro+：16434，42000；A7 V3 Ultra+：16435，50000。
新设备有 `dpiMagicNum`（原始 DPI 值→显示值映射表 `r0` 127116-127142）与 `dpiSlider`。

## 修订记录

- 2026-08-08 初版（Web bundle 静态分析，未真机验证）。
