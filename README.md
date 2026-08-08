# MCMouseDriver

迈从（MCHOSE）A7 系列鼠标的 **macOS 菜单栏配置软件**（非官方，个人学习项目）。
无 Dock 图标、常驻系统菜单栏，纯原生实现，不使用网页/WebView。

官方配置工具 MCHOSE HUB 只有 Windows 版。本项目通过逆向官方驱动弄清鼠标配置协议，
用 Python + hidapi 实现一个 macOS 上可用的替代品。

## 背景：官方软件是怎么工作的

对官方安装包（`MCHOSE HUB installer.exe`，NSIS 自解压包）解包分析后确认：

- **MCHOSE HUB 是一个 Electron 壳 + 远程 Web 应用**：真正的配置界面和协议逻辑都在
  Web 应用里（生产环境地址 `https://www.mchose.com.cn/`，SPA + WebHID），
  Electron 主进程只负责窗口、USB 访问（node-usb）、升级、音频 SDK 等本地能力。
- 鼠标配置走的是 **USB HID**（厂商自定义 usage page），浏览器端用 WebHID 收发
  Feature/Input Report。这意味着同一套报文协议可以在 macOS 上用 hidapi 直接复现。
- 官方 Web 应用的 JS bundle 可公开下载、可读性尚可（minify 但未虚拟化保护），
  是协议逆向的第一信息源；Electron 主进程核心逻辑被编译成 V8 字节码（`.jsc`），
  作为第二信息源。

详细结论见知识库 `docs/kb/architecture/0001-official-software-architecture.md`。

## 目标设备

迈从 A7 系列（A7 / A7 Pro / A7 Ultra 及 V2 衍生版）：瑞昱主控，
PAW3395/PAW3950 传感器，三模（有线 / 2.4G 接收器 / 蓝牙），最高双 8K 回报率。
首期聚焦**有线与 2.4G 接收器**两种连接方式（蓝牙模式不在首期范围）。

## 功能规划（一期）

- DPI 档位、回报率、LOD、直线修正/波纹控制等传感器参数读写
- 按键映射与宏下发
- RGB 灯效控制、电量显示
- 配置的本地持久化与导入导出

固件 OTA 升级为二期内容（一期不做）。完整需求见 `docs/requirements.md`。

## 仓库结构

```
├── AGENTS.md             # 开发规则 + 知识库管理规则（先读这个）
├── docs/
│   ├── requirements.md   # 需求分析
│   ├── tech-selection.md # 技术选型方案
│   └── kb/               # 逆向知识库（协议结论都在这里登记）
├── src/mcmouse/          # 产品代码（待建）
├── tests/                # 测试与报文样本（待建）
├── scripts/              # 逆向分析脚本（待建）
└── _reverse/             # 官方安装包解包工作区（本地专用，不入库）
```

## 路线图

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 解包官方软件、建立知识库、项目文档 | 完成 |
| M1 | 从 Web bundle 逆向 A7 协议，协议库 + CLI 跑通真机读写 | 进行中（读/写 DPI 已验证） |
| M2 | macOS 菜单栏应用（PySide6 accessory 模式，无 Dock 图标） | 未开始 |
| M3 | 打包分发（.app）、打磨 | 未开始 |

## 法律与免责声明

本项目仅供个人学习研究使用。所有逆向结论仅用于实现互操作性；
不分发任何官方软件、代码与素材。MCHOSE、迈从为迈从科技有限公司的商标，
本项目与其无任何隶属关系。使用本软件修改鼠标设置的风险由使用者自行承担。
