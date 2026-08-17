# MCMouseDriver

迈从（MCHOSE）A7 系列鼠标的非官方 macOS 配置工具。官方 MCHOSE HUB 仅提供 Windows 版；本项目依据公开协议分析，在 macOS 上实现同等核心配置能力。

应用常驻系统菜单栏，无 Dock 图标，不使用 WebView。

## 功能

- DPI 档位、回报率、LOD、直线修正、波纹控制、Motion Sync
- 按键映射与板载宏
- 电量与固件信息
- 命名配置的本地保存、导入与导出

固件升级不在当前范围内。完整需求见 [`docs/requirements.md`](docs/requirements.md)。

## 支持设备

迈从 A7 / A7 Pro / A7 Ultra 及 V2 衍生型号（瑞昱主控，PAW3395 / PAW3950）。

| 连接方式 | 配置 |
|---|---|
| 有线 | 支持 |
| 2.4G 接收器 | 支持 |
| 蓝牙 | 仅识别，不提供配置 |

当前已接入旧协议机型（A7 V2 Pro / Pro+ / Ultra+）。A7 V3 使用新协议，暂未实现。

## 系统要求

- macOS 14 或更高
- Apple Silicon（M 系列）
- 鼠标以有线或 2.4G 接收器连接

## 安装

1. 打开 `MCMouseDriver-x.y.z.dmg`
2. 将 `MCMouseDriver.app` 拖入「应用程序」
3. 首次启动时，若系统提示无法验证开发者，请按住 Control 点按应用并选择「打开」

启动后请到菜单栏查找鼠标图标。点击可查看电量并切换 DPI / 回报率；「设置…」打开完整配置面板。

安装与签名相关的说明见 [`docs/packaging.md`](docs/packaging.md)。

## 从源码运行

```bash
uv sync
uv run mcmouse gui
uv run mcmouse --help
uv run pytest
```

真机测试：`uv run pytest --runlive`。

## 开发

协议结论登记在 [`docs/kb/`](docs/kb/README.md)。技术选型见 [`docs/tech-selection.md`](docs/tech-selection.md)。开发约定见 [`AGENTS.md`](AGENTS.md)。

构建安装包：

```bash
./packaging/build_dmg.sh
```

产物为 `dist/MCMouseDriver.app` 与 `dist/MCMouseDriver-<version>.dmg`。签名与公证步骤见 [`docs/packaging.md`](docs/packaging.md)。

## 仓库结构

```
docs/          需求、选型、逆向知识库
src/mcmouse/   协议库、CLI、菜单栏应用
tests/         单元测试与报文样本
scripts/       逆向分析脚本
packaging/     安装包构建
```

## 路线图

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 官方软件分析、知识库与项目文档 | 完成 |
| M1 | A7 协议库与 CLI，真机读写 | 完成 |
| M2 | macOS 菜单栏应用 | 完成 |
| M3 | `.app` / DMG 分发 | 完成 |

## 免责声明

本项目仅供个人学习与互操作研究，与迈从科技有限公司无任何隶属关系。MCHOSE、迈从为迈从科技有限公司的商标。请勿分发官方安装包、代码或素材。修改设备配置的风险由使用者自行承担。
迈从官网：https://www.maicong.cn
