---
id: 2
title: 鼠标设备注册表（VID/PID 清单）
category: devices
status: analyzed
source: web-bundle
firmware: 不适用
date: 2026-08-08
---

# 鼠标设备注册表（VID/PID 清单）

来源：官方 Web 驱动 bundle（2026-08-08 快照，`main-zuTdzYUB.js` + `purify.es-B28R1Od0.js`
+ `index-6qA02BRF.js`）。

## 设备键格式

注册表中设备以字符串键标识：`设备名$$$VID$$$PID`（VID/PID 为**十进制**）。
示例：`"MCHOSE A7 V2 Pro+$$$14391$$$16419"`。

## 常见 VID

| VID 十进制 | VID 十六进制 | 用途（推测） |
|---|---|---|
| 14391 | 0x3837 | 主力 VID：鼠标/键盘本体与接收器 |
| 21075 | 0x5253 | 部分鼠标的额外条目（疑似 8K 接收器，hypothesis） |
| 10525 | 0x291D | 耳机（G9/S9/V9 等） |
| 16868 | 0x41E4 | 耳机（另一主控） |
| 3690 | 0x0E6A | G20 系列 |

## A7 系列条目（全量）

| 型号 | VID | PID（十进制/十六进制） |
|---|---|---|
| A7 V2 Pro+ | 14391 | 16419 / 0x4033 |
| A7 V2 Pro+ | 14391 | 4106 / 0x100A |
| A7 V2 Pro+ | 14391 | 4107 / 0x100B |
| A7 V2 Pro+ | 21075 | 4128 / 0x1020 |
| A7 V2 Ultra+ | 14391 | 16417 / 0x4021 |
| A7 V2 Ultra+ | 14391 | 4106 / 0x100A |
| A7 V2 Ultra+ | 14391 | 4107 / 0x100B |
| A7 V2 Ultra+ | 21075 | 4128 / 0x1020 |
| A7 V3 Pro+ | 14391 | 16434 / 0x4032 |
| A7 V3 Pro+ | 14391 | 4116 / 0x1014 |
| A7 V3 Pro+ | 14391 | 4120 / 0x1018 |
| A7 V3 Ultra+ | 14391 | 16435 / 0x4033 |
| A7 V3 Ultra+ | 14391 | 4116 / 0x1014 |
| A7 V3 Ultra+ | 14391 | 4120 / 0x1018 |

## PID 角色（来源：官方能力表 `Xf`/`JS`，purify.js:88982+，status: analyzed）

能力表中每个型号的 `pids` 数组按下标对应 `rate` 数组（该 PID 支持的回报率）：

- **pids[0]（164xx 段）= 有线模式**（rate 8K）。
- **pids[1]（41xx 段）= 1K 接收器**（rate 1K）——如 A7 V2 Pro+ 的 4106。
- **pids[2]（41xx 段）= 8K 接收器**（rate 8K）——如 A7 V2 Pro+ 的 4107。
- **pids[3]（21075/4128）= 另一方案 8K 接收器**（V2 系列独有条目）。

注意：早期版本本条目的角色推测（164xx=接收器、41xx=本体）**方向相反，是错的**，
以本节为准（见修订记录）。

## 实机验证记录

### 2026-08-08 · macOS（Apple Silicon）· hidapi（IOHIDManager）· USB 连接

设备：**MCHOSE A7 V2 Pro+**（product string "MCHOSE A7 V2 Pro"，serial 0123456789）。
连接方式：PID 为 4106，按上方角色表为 **2.4G 接收器（1K）模式**（待用户确认物理接法）。

1. **verified**：PID=0x100A（4106）与注册表吻合，macOS 可直接枚举，共 6 个接口：
   - if=0：usage_page 0x0001/usage 0x0002（鼠标）、0x0001/0x0001
   - if=1：usage 0x0006（键盘）、0x000c（consumer control）
   - if=2：**usage_page 0xff0b/usage 0x0104** 与 **usage_page 0xff01/usage 0x0001**
     （两个厂商自定义接口，与官方过滤器 65281/65291=0xFF01/0xFF0B 完全吻合）
2. **verified**：两个厂商接口均可 `get_feature_report`（report ID 0 报错，1~7 返回 64 字节）。
   原始返回（report 1，前 20 字节，首字节为 report ID 回显）：
   `01 fb f7 ca d1 ce ca d1 cf d1 c6 ff ff ff ff ff ff ff ff ff ff`
   - **verified（与 kb/0003 互证）**：设备数据 `fb f7 ca …` 逐字节取反 =
     `04 08 35 2e 31 35 2e 30 2e 39` = 子命令 0x04（读固件版本）+ 长度 8 +
     ASCII "5.15.0.9"。本机固件版本即 **5.15.0.9**。
3. 有线模式（PID 16419）尚未实测。

### 2026-08-08 · 读路径全量验证（2.4G 接收器 1K 模式）

通过 `mcmouse info` 读到真实配置（鼠标唤醒后，睡眠时接收器回全零，见 kb/0007）：

- 鼠标固件 **5.42.0.9**（`0x11 0x04`）；接收器固件 **5.15.0.9**（`0x11 0x04` + 第3字节 0xAA）
- 电量 59%，未充电；connectMode=1（2.4G），connectStatus=1（已连接）
- DPI 6 档：400/800/1193/1600/6400/26000，当前第 3 档（用户自定义值 1193 原样读出）
- 回报率 1000Hz（1K 列表索引 2）；LOD=2mm；防抖 8；休眠 3 分钟；角度旋转 0°
- 设备信息响应（XOR 解码后）前缀：`37 38 18 40 2a 05 00 09 09 3b 00 3b`
  → vid=0x3837 pid=0x4018（A7 V2 Pro 本体 PID）fw=0x0900052A 连接=0x09 电量=0x3B

工具：`scripts/probe_hid.py`、`scripts/probe_feature_reports.py`。

### 2026-08-09 · 有线模式与固件升级

1. **verified**：有线模式 PID=0x4018（16408，A7 V2 Pro 本体标识），product/serial
   "MCHOSE A7 V2 Pro / 0123456789A"。已登记进 `mcmouse.devices`。
   注：本机市场名为 A7 V2 Pro+，MCU 自报为 A7 V2 Pro（+ 或仅表示捆绑 8K 接收器）。
2. **固件升级 5.42.0.9 → 5.42.2.4**（用户经官方 App 升级）：读协议与配置布局不变
   （DPI 表、回报率等读回一致）；**宏引擎在新固件恢复工作，事件编码回归官方
   bundle 的"预取反"形态**（kb/0007 §7 结案）。
3. 电量读数随充电状态变化正常（77%，充电中 chargeStatus=1）。

## 注意

- **A7 V1（A7 / A7 Pro，非 V2/V3）未出现在当前 Web 驱动注册表中**。
  当前 Web 驱动支持的鼠标系列（theme 文案）：K7 Ultra、A7 系列、M7 系列、L7 系列、
  G7 系列、G3 A、G3 Ultra、A5 V2/V3 等。V1 用户需实机确认能否被识别及所用协议。
- 键盘（K20/K9/Ace 75/God 60/G87）与耳机条目不在本项目范围。

## 修订记录

- 2026-08-08 初版（Web bundle 静态分析）。
- 2026-08-08 PID 角色推测方向写反（164xx/41xx 互换），按官方能力表 `pids`/`rate`
  对应关系修正；补充实机验证记录（A7 V2 Pro+，固件 5.15.0.9）。
- 2026-08-08 修正固件版本号笔误：5.15.09 → 5.15.0.9（重数取反字节证实）。
