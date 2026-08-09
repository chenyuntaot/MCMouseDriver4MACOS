# 技术选型方案

版本：v1.0 · 2026-08-08
状态：已确认（核心栈）/ 待验证（标注 ⚠ 的项）

---

## 1. 选型约束

- 目标平台：**macOS（Apple Silicon）**，首期只服务这一台机器，不做 Windows/Linux。
- 目标设备：迈从 A7 系列鼠标（瑞昱主控，PAW3395/PAW3950，有线 + 2.4G 接收器）。
- 软件形态：**macOS 菜单栏应用**（无 Dock 图标的常驻形态，用户 2026-08-08 确认）；
  明确不采用网页/WebView 方案。
- 官方驱动的事实（来自逆向，见 `kb/architecture/0001`）：
  - 配置通道是 **USB HID 厂商自定义接口**，报文为 Feature Report / Input Report；
  - 官方网页版驱动用 **WebHID** 实现同一套协议；
  - 官方桌面端（Electron）用 node-usb，但其主进程逻辑是 V8 字节码，直接参考价值低。
- 个人项目：优先开发效率与可维护性，不追求原生外观。

## 2. 核心决策：Python + hidapi

### 2.1 候选方案对比

| 方案 | HID 访问 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| **Python + hidapi** | IOHIDManager | 与 WebHID 同抽象层，报文可直接对照；逆向脚本同语言；迭代快 | GUI 生态一般 | ✅ 采用 |
| Node + node-hid/node-usb | IOHIDManager / libusb | 与官方桌面端同源 | node-usb 在 macOS 上抢设备会与系统 HID 驱动冲突；异步心智成本高 | 备选 |
| Swift + IOKit HID | IOHIDManager | 最原生、无依赖 | 开发成本高，协议探索期迭代慢 | 二期可选 |
| WebHID 网页 | 浏览器 WebHID | 零安装，官方网页可直接用 | 依赖 Chrome、无法离线、不算"自己的软件" | 应急 fallback |

### 2.2 为什么 hidapi 而不是 pyusb

- pyusb/libusb 在 macOS 上需要 `detach` 内核驱动，而鼠标接口已被系统 HID 栈占用，
  强行独占会导致鼠标失灵；hidapi 走 IOHIDManager，与系统共存，无需 root。
- 官方协议是在 HID 层（WebHID）定义的，hidapi 与之一一对应：
  `send_feature_report` / `get_feature_report` / `read`。
- ⚠ 待验证：macOS 对鼠标类 HID 设备的厂商接口访问不需要特殊权限，
  首个真机实验（M1 里程碑）需确认；如被拦截则退而求其次申请"输入监控"权限或走
  IOKit 原生 binding。

### 2.3 Python 库选型

| 用途 | 选择 | 备选 | 说明 |
|---|---|---|---|
| HID | `hidapi`（trezor/cython-hidapi） | `pyhidapi` | 维护活跃，预编译 wheel 支持 arm64 |
| CLI | `typer` | `click`、`argparse` | 类型标注友好，自动生成帮助 |
| 数据建模 | `dataclasses` + `struct`/`construct` | `construct` | 先用标准库 struct，报文复杂后再引入 construct |
| 测试 | `pytest` | — | 报文回放测试 |
| 代码质量 | `ruff` | — | format + lint 一把抓 |
| 环境管理 | `uv` | `pip + venv` | 快，锁文件可靠 |
| GUI（二期） | `PySide6`（accessory 菜单栏模式） | rumps | 见 §4；不用 pywebview/WebView |
| 打包（三期） | `py2app` 或 `PyInstaller` | — | 产出独立 .app |

## 3. 逆向工程工具链

| 工具 | 用途 | 状态 |
|---|---|---|
| `7zz` | 解 NSIS 安装包、内部 7z | ✅ 已用（`MCHOSE HUB installer.exe` → `app-64.7z`） |
| `@electron/asar` | 解 `resources/app.asar` | ✅ 已用 |
| Chrome DevTools / 格式化后的 JS | 分析官方 Web bundle（**协议第一信息源**） | 待做（M1 主线） |
| `strings` + V8 字节码反汇编（如 `bytenode` 工具） | 从 `.jsc` 挖线索（第二信息源） | 部分已做 |
| Wireshark + USBPcap（Windows 环境/VM） | 抓真机报文，验证静态分析结论 | 待做（M1 验证手段） |
| macOS `tcpdump -i XHC*` | macOS 侧 USB 抓包 | ⚠ Apple Silicon 上可用性待验证 |
| hidapi 探针脚本 | 枚举 VID/PID/usage page，读设备描述符 | 待做（M1 第一步） |

信息源优先级：**官方 Web bundle > 真机抓包 > asar 内明文 JS（preload 等）> .jsc 字节码**。
所有结论必须登记到知识库（规则见 `AGENTS.md` 第二部分）。

## 4. 架构与演进路线

```
一期（M1）                     二期（M2）                三期（M3）
┌─────────────────┐          ┌─────────────────┐       ┌──────────────┐
│ CLI (typer)     │          │ 菜单栏应用 GUI    │       │ 独立 .app    │
├─────────────────┤          ├─────────────────┤       ├──────────────┤
│ 协议库 mcmouse.protocol │ ─→ │ 同一协议库，不改动  │ ─→    │ py2app 打包   │
├─────────────────┤          ├─────────────────┤       ├──────────────┤
│ hidapi 传输层    │          │ hidapi 传输层    │       │ 同左          │
└─────────────────┘          └─────────────────┘       └──────────────┘
```

设计要点：

1. **协议库与传输层分离**：`mcmouse.protocol` 只做报文编解码（纯函数、可单测），
   `mcmouse.transport` 只做 HID 收发。这样测试用录制报文回放即可，无需真机。
2. **CLI 先行**：每个协议能力先暴露为 CLI 子命令（如 `mcmouse dpi get/set`），
   在真机上验证后再进 GUI。CLI 同时充当永久的调试工具。
3. **GUI 二期为 macOS 菜单栏应用（PySide6 accessory 模式）**：`LSUIElement`
   无 Dock 图标，常驻菜单栏；菜单提供电量/DPI 概览与快捷切换，点击唤出
   设置面板承载完整配置 UI（滑块/色盘/键位捕获）。选 PySide6 而非 rumps，
   因为宏编辑器等面板需要完整控件体系；rumps 仅作 UI 收缩为纯菜单时的
   轻量备选。明确不使用 pywebview/WKWebView 等网页方案（用户要求）。

   ⚠️ 实施修订（2026-08-09，kb/0008）：macOS 27 上 QSystemTrayIcon 原生菜单
   点击必崩（QTBUG-147449，Qt ≤6.12 未修），托盘交互改为**自绘 Qt 弹层**
   （纯 QWidget，不经 NSMenu）。同日评估过 SwiftUI 重写路线，**用户决定
   继续 Qt**，SwiftUI 留作后备。
4. **配置持久化**：本地 JSON 文件（`~/Library/Application Support/MCMouseDriver/`），
   支持导入/导出官方兼容格式（⚠ 官方配置格式待逆向确认）。

## 5. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 协议字段静态分析读不懂（minify/魔法数） | M1 延期 | Windows 环境抓包对照；知识库先记 hypothesis 再逐个验证 |
| macOS HID 权限拦截 | 无法通信 | 首个实验即验证；必要时申请输入监控权限或切 IOKit |
| 2.4G 接收器与有线模式协议不同 | 功能残缺 | 设备档案（kb/devices）分别登记两种通道的能力矩阵 |
| 写错配置变砖 | 设备损坏 | 只写官方已验证的合法取值；先读后写、可恢复默认；一期禁止任何固件烧写 |
| 官方 Web 应用改版导致分析失效 | 知识过期 | 分析用的 bundle 版本号记入知识库条目 front matter |

## 6. 已验证与待验证清单

已验证 ✅：安装包可完整解包；Electron+远程 Web 架构；Web 端走 WebHID；
生产 Web 应用地址与 bundle 可下载；
**hidapi 可枚举到 A7 V2 Pro+ 有线模式的厂商接口（0xff0b/0xff01，见 kb/0002）**；
**两个厂商接口均可 get_feature_report 并返回数据（疑似固件版本 5.15.059，见 kb/0002）**。

待验证 ⚠（M1 剩余实验，按序执行）：
1. ~~hidapi 枚举厂商接口~~（已过）；2.4G 接收器模式的枚举与读写另行验证。
2. ~~get_feature_report 通路~~（已过）。
3. 用静态分析得到的报文格式读取 DPI，返回值与官方 App 显示一致。
