---
id: 5
title: 旧协议功能命令布局（配置/DPI/回报率/传感器/电量）
category: protocol
status: analyzed
source: web-bundle
firmware: 5.15.0.9（A7 V2 Pro+）
date: 2026-08-08
---

# 旧协议功能命令布局

帧格式（XOR 0xFF、reportId 0x11/0x12、包长 20/64）见 kb/0003。
本条目的"偏移"均指 **XOR 解码后、去掉 reportId 与子命令字节** 的逻辑数据偏移。
行号为 `_reverse/web/pretty/purify.es-B28R1Od0.js`（2026-08-08 快照）。

## 1. 读设备信息 `0x11 0x06`（parser `Xwt` 76277-76286，已核对源码）**【verified】**

真机验证（2026-08-08）：电量 59%、connectMode=1（2.4G）、connectStatus=1 均正确；
bit 顺序以 LSB 读法为准（见 kb/0007 §2 的修正过程）。

| 偏移 | 长度 | 字段 | 编码 |
|---|---|---|---|
| 0-1 | 2 | vid | u16 LE |
| 2-3 | 2 | pid | u16 LE |
| 4-7 | 4 | fwVersion | u32 LE |
| 8 | 1 | 连接状态 | **bit0-2=connectMode（0=有线 1=2.4G），bit3=connectStatus**，bit4-7 保留（LSB 读法，真机修正见 kb/0007） |
| 9 | 1 | batteryLevel | 电量百分比 |
| 10 | 1 | chargeStatus | 充电状态 |

## 2. 读整份配置 `0x12 0x67`（parser `Awt` 76288-76366，已核对源码）**【verified】**

真机验证（2026-08-08）：读出用户真实配置（DPI 含自定义值 1193、回报率 1000Hz、
LOD 2mm、防抖 8、休眠 3 分钟），与设备表现一致。休眠时返回全零（kb/0007 §3）。

响应共 63 字节逻辑数据：

| 偏移 | 长度 | 字段 | 编码 |
|---|---|---|---|
| 0 | 1 | profileIndex | 当前板载配置索引 |
| 1 | 1 | 高4位=usbRateIndex，低4位=usbDpiIndex | **有线侧**（真机仲裁，kb/0007 §6；与官方 parser 声明相反） |
| 2 | 1 | 高4位=gRateIndex，低4位=gDpiIndex | **2.4G 侧**（同上当） |
| 3 | 1 | reserved | |
| 4-15 | 12 | dpi0-dpi5 | u16 LE ×6，**真实 DPI 值，无缩放** |
| 16 | 1 | dpiSum | 有效档位数（1-6） |
| 17 | 1 | sensor | 位掩码，见 §4 |
| 18 | 1 | keyDebounce | 按键防抖（UI 0-20，单位 ms 为推测） |
| 19 | 1 | sleep | 休眠分钟数，0=从不 |
| 20-43 | 24 | 按键×6 | 每键 4 字节：byte0 高4位=buttonType、低4位=buttonIndex；byte1-3=buttonValue（BE 拼接，如 0x010000=左键） |
| 44-48 | 5 | reserved1-5 | |
| 49 | 1 | rotateVal | 角度旋转 int8（>30 减 256），**即度数本身（1°/步）**，量程 ±30° |
| 50 | 1 | val | 写时固定 255，含义未知 |
| 51-62 | 12 | dpiVal0-dpiVal5 | u16 LE ×6，独立 Y 轴 DPI（未开启时与 dpi 相同） |

## 3. 写命令

### 3.1 写 DPI `0x12 0x40`（schema `lMt` 76733，调用 131200-131241）**【verified】**

逻辑数据：`usbDpiIndex, gDpiIndex, reserved, dpi0-5 u16 LE, sum(档位数), diff(固定255), dpiVal0-5 u16 LE`。
短版 `0x11 0x40`（rMt 76720）在 bundle 中无调用点，实际都用 0x12 长包。
恢复默认：索引=2，dpi=默认表（dpiMax 26000 → 400/800/1600/3200/6400/26000），sum=6。

真机验证（2026-08-08，A7 V2 Pro+，固件 5.42.0.9）：将读出的 DPI 表原样写回，
读回逐字段一致。样本：`tests/captures/20260808_live_dpi-writeback.hex`。

### 3.2 写回报率 `0x11 0x41`（schema `hMt` 76774，调用 136302-136309）**【verified】**

真机验证（2026-08-09）：`{usbRate:0, freeRate:1}` 后 byte2 高4位 2→1（500Hz），
`{usbRate:1, freeRate:0}` 在无线连接下被忽略（usbRate 仅下线路由生效）。
规律：byte2 = [freeRate(高4) | usbRate(低4)]。

逻辑数据：`usbRate, freeRate`。有线发 `{usbRate: idx, freeRate: 0}`；
2.4G 发 `{usbRate: 0, freeRate: idx}`。idx 为当前 PID 对应 rate 列表的索引。

Hz 映射表（`ta` 88949，**无 250Hz**）：

| 索引 | 1K 列表 | 4K 列表 | 8K 列表 |
|---|---|---|---|
| 0 | 125 | 125 | 125 |
| 1 | 500 | 500 | 500 |
| 2 | 1000 | 1000 | 1000 |
| 3 | — | 2000 | 2000 |
| 4 | — | 4000 | 4000 |
| 5 | — | — | 8000 |

设备用哪个列表：`Xf[型号].rate[pids.indexOf(当前PID)]`（136011-136032）。
A7 V2 Pro+：有线(16419)=8K 列表，接收器 4106=1K 列表，4107/4128=8K 列表。

### 3.3 写性能参数 `0x11 0x42`（schema `uMt` 76762，调用 136251+）**【verified】**

真机验证（2026-08-09）：以读回全量为底、仅改 ripple=1 写入，byte17 0x02→0x06
（bit2 置位），其余字节不变；恢复后一致。全量回写方式安全。

逻辑数据 9 字节：`lod, ripple, line, motionSync, reserved, reserved2, gameMode, rotateOpen, rotateVal`。
**写入编码与读回位掩码不同**：
- ripple/line/motionSync：**1=开，2=关**（136255）
- lod：0/1/2；2 档设备 UI 选项 0→发 1、选项 1→发 2（136232-136243）
- gameMode：1/2/3（136344）
- rotateOpen=1 时 **rotateVal 就是度数本身**，负值 +256，量程 ±30°
  （135483, 135497-135502；「/4」为早期误读，2026-08-15 真机推翻，见下方修订记录与 kb/0010）
- **rotateOpen 恒为 1，设 0° 也发 (1, 0)**：官方刻度盘组件从不发 0
  （`we()` 里 `rotateOpen: 1` 与角度值无关；清零路径 `Ge` 同样走 `we(0)`，
  135497-135502 / 152497-152510）。本程序曾对 0° 发 (0, 0)，设备 byte49
  读回 0xFF、按「>30 减 256」解码成 -1°，表现为「设 0° 跳 -1°」（kb/0010 §4）
- 未提供字段的行为是推测（hypothesis：UI 调用只传部分字段，需真机验证，风险中等）

### 3.4 其他

| 命令 | 用途 | 逻辑数据 | 出处 |
|---|---|---|---|
| `0x11 0x0A` | 休眠 **【verified】** | `sleepStatus(1=启用/0=从不), sleep(分钟)`；真机：byte19 3→5→3 | 76753, 136173 |
| `0x11 0x43` | 按键防抖 **【verified】** | `time`（uint8，0-20）；真机：byte18 8→12→8 | 76758, 136214 |
| `0x11 0x58` | 切板载配置 | `profileIndex` | 79096 |
| `0x11 0x0B` | **恢复出厂** | `AA 00`（u16 BE=43520） | 76843, 138062 |
| `0x12 0x57` | 全量配置写 | 与 0x67 响应同构 62 字节，**nibble 顺序与读相反**（byte1 高4=usbRateIndex 低4=usbDpiIndex；byte2 高4=gRateIndex 低4=gDpiIndex），val=255 | mMt 76779, 78240 |
| `0x11 0x02` | 未知（读配置后例行发送） | `00` | 78231, 136116 |

## 4. sensor 位掩码（读 @136048-136092）

| bit | 含义 |
|---|---|
| 0-1 | LOD：值=bit0+2×bit1；3 档设备 0=0.7/1=1/2=2mm；2 档设备 1=1mm/2=2mm |
| 2 | 波纹控制 ripple |
| 3 | 直线修正 line |
| 4 | Motion Sync |
| 6-7 | 电竞模式：bit7=0→模式0；bit7=1&bit6=0→模式1；bit7=1&bit6=1→模式2 |
| 5 | 保留 |

## 5. 设备主动上报（input report，XOR 解码后，76650-76712）

- `e2` 开头：通知。byte1-2：`0001`/`0101`=DPI 切换（首字节 00=有线/01=无线）、
  `0102`=断连；byte3=chargeStatus；byte4=batteryLevel；byte5=dpiIndex；
  byte8 bit7=设备端切换了板载配置。
- `e5` 开头：命令应答，byte1=命令字回显，用于任务队列推进。

## 修订记录

- 2026-08-08 初版（Web bundle 静态分析；§1/§2 布局已对照 parser 源码逐字段核对）。
- 2026-08-08 §1/§2/§3.1 真机验证通过（A7 V2 Pro+，固件 5.42.0.9）；
  §3.2/§3.3/§3.4 当日仅做幂等验证，次日发现校验读错字节位置（见下条）。
- 2026-08-08 §2 按键区 nibble 顺序修正：高4位=buttonIndex、低4位=buttonType
  （真机仲裁，见 kb/0007 §4）。
- 2026-08-09 §2 byte1/2 布局修正（真机仲裁，见 kb/0007 §6）：
  byte1=[usbRate|usbDpi]、byte2=[gRate|gDpi]，与官方 parser 声明完全相反；
  §3.2/§3.3/§3.4 随之真机验证通过（0x11 短包写实际一直有效，此前是读回
  校验读错了字节位置）。
- 2026-08-15 §2 byte49 / §3.3 角度旋转单位修正：**rotateVal 即度数，不是度数/4**。
  取证方式：本程序按「4°/步」写入 12°（实际发出 rotateVal=3），关闭后用官方软件读取，
  官方显示 3°，说明官方的度数就是 rotateVal 原值。这也与「>30 视为负值」的阈值自洽
  ——量程正是 ±30°，而非按 4° 折算出的 ±120°。详见 kb/0010。
- 2026-08-16 §3.3 补充：rotateOpen 恒为 1（含 0°），官方组件从不发 0；
  本程序发 (0, 0) 后设备 byte49 读回 0xFF → 解码 -1°。详见 kb/0010 §4。
