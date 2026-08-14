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

## 安装（用打好的 DMG）

打开 `MCMouseDriver-<版本>.dmg`，把 `MCMouseDriver.app` 拖到「应用程序」。
当前包只打了 **Apple Silicon（M 系列）**，Intel Mac 跑不了；系统需 macOS 14+。

### 换到别的 Mac：系统会拦，这是正常的

没有 Apple 开发者证书、也没做公证时，对方双击会看到
「无法验证开发者」或「已损坏」。按下面任一方式放行即可：

1. **右键打开**（推荐，不用终端）：按住 Control 点图标 → 打开 → 再点打开。
2. **系统设置**：隐私与安全性 → 滚到最下面 → 「仍要打开」。
3. **终端**：

```bash
xattr -dr com.apple.quarantine /Applications/MCMouseDriver.app
open /Applications/MCMouseDriver.app
```

DMG 里也有一份 `首次打开（必读）.txt`，可以直接转给对方。

想让别人**双击就能开**，需要加入 [Apple Developer Program](https://developer.apple.com/programs/)
（每年 99 美元），用 Developer ID 签名并公证。有证书后：

```bash
export MCMOUSE_SIGN_IDENTITY="Developer ID Application: 你的名字 (TEAMID)"
./packaging/build_dmg.sh
xcrun notarytool submit dist/MCMouseDriver-*.dmg --keychain-profile notary --wait
xcrun stapler staple dist/MCMouseDriver-*.dmg
```

`notarytool` 的钥匙串配置一次即可：`xcrun notarytool store-credentials notary`。

启动后没有 Dock 图标，鼠标剪影出现在菜单栏；点它看电量/DPI/回报率，
「设置…」打开完整配置面板。若读不到设备：

```bash
/Applications/MCMouseDriver.app/Contents/MacOS/MCMouseDriver --selftest
```

## 从源码运行

```bash
uv sync                 # 安装依赖（首次）
uv run mcmouse gui      # 启动菜单栏应用（A7 图标出现在菜单栏）
uv run mcmouse --help   # CLI：list/info/dpi/rate/sensor/sleep/debounce/button/macro
uv run pytest           # 离线测试（真机测试加 --runlive）
```

## 打包

```bash
./packaging/build_dmg.sh      # 产出 dist/MCMouseDriver.app 与 dist/MCMouseDriver-<版本>.dmg
```

脚本依次做：生成图标 → PyInstaller 构建 .app → 签名 → `hdiutil` 打 DMG。
有 Developer ID 时设 `MCMOUSE_SIGN_IDENTITY="Developer ID Application: …"`
即改为正式签名。打包相关的坑见 `kb/0009`，选型论证见 `docs/tech-selection.md` §2.4。

菜单栏应用：点击 A7 图标弹层（电量/固件/DPI 档位/回报率快捷切换），
「设置面板…」里有 DPI/性能/按键/宏/命名配置的完整界面。
注：macOS 27 上 Qt 原生托盘菜单有崩溃 bug（QTBUG-147449），
弹层为自绘绕行实现（kb/0008）。

## 仓库结构

```
├── AGENTS.md             # 开发规则 + 知识库管理规则（先读这个）
├── docs/
│   ├── requirements.md   # 需求分析
│   ├── tech-selection.md # 技术选型方案
│   └── kb/               # 逆向知识库（协议结论都在这里登记）
├── src/mcmouse/          # 产品代码（协议库 + CLI + 菜单栏 GUI）
├── tests/                # 测试与报文样本
├── scripts/              # 逆向分析脚本
├── packaging/            # 打包：PyInstaller spec、图标生成、DMG 构建脚本
└── _reverse/             # 官方安装包解包工作区（本地专用，不入库）
```

## 路线图

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 解包官方软件、建立知识库、项目文档 | 完成 |
| M1 | 从 Web bundle 逆向 A7 协议，协议库 + CLI 跑通真机读写 | 完成 |
| M2 | macOS 菜单栏应用（PySide6 accessory 模式，无 Dock 图标） | 完成 |
| M3 | 打包分发（.app + DMG）、打磨 | .app/DMG 已通（ad-hoc 签名）；正式签名与公证待 Developer ID |

## 法律与免责声明

本项目仅供个人学习研究使用。所有逆向结论仅用于实现互操作性；
不分发任何官方软件、代码与素材。MCHOSE、迈从为迈从科技有限公司的商标，
本项目与其无任何隶属关系。使用本软件修改鼠标设置的风险由使用者自行承担。
