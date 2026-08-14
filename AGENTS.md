# AGENTS.md — MCMouseDriver 项目工作规范

本文件是所有开发者（人类与 AI 代理）在本仓库工作时必须遵守的规则。
它包含两部分：**开发规则** 与 **知识库管理规则**。

---

## 第一部分：开发规则

### 1. 项目一句话定位

在 macOS 上为迈从（MCHOSE）A7 系列鼠标开发开源配置软件；通信协议通过对官方
Windows 驱动（MCHOSE HUB，Electron 应用）及其 Web 版驱动（www.mchose.com.cn）
的逆向分析获得。

### 2. 技术栈（已定）

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.13 | 与逆向脚本同一语言，降低上下文切换 |
| 包管理/环境 | `uv` + `.venv` | 所有第三方包只装进 `.venv`，禁止污染系统 Python |
| HID 通信 | `hidapi`（Python binding） | 与官方 WebHID 同一抽象层，报文可直接对照迁移 |
| 协议验证 | `pytest` + 录制的报文回放 | 协议层测试不依赖真机 |
| 一期交互 | CLI（`typer`） | 先把协议跑通；GUI 为 macOS 菜单栏应用（PySide6 accessory 模式），放二期 |
| 逆向工具 | `7zz`、`@electron/asar`、Chrome DevTools、Wireshark/USBPcap | 详见 `docs/tech-selection.md` |

技术选型的完整论证见 `docs/tech-selection.md`，改动选型必须先改该文档。

### 3. 目录结构约定

```
MCMouseDriver/
├── AGENTS.md            # 本文件
├── README.md            # 项目介绍
├── docs/
│   ├── requirements.md  # 需求分析
│   ├── tech-selection.md# 技术选型方案
│   ├── packaging.md     # 安装包构建、签名与公证
│   └── kb/              # 知识库（规则见第二部分）
├── src/mcmouse/         # 产品代码（协议库 + CLI + GUI）
├── tests/               # pytest 测试与录制的报文样本
├── scripts/             # 逆向/分析用一次性脚本
├── packaging/           # 打包分发：PyInstaller spec、图标生成、DMG 构建脚本
├── _reverse/            # 逆向工作区：解包出的官方文件（不入库、不分发）
├── build/               # 打包中间产物（不入库）
├── dist/                # 打包产物 .app / .dmg（不入库）
└── .venv/               # 虚拟环境（不入库）
```

规则：
- `_reverse/`、`.venv/`、构建产物一律通过 `.gitignore` 排除，**禁止提交**。
- `scripts/` 里的逆向脚本可以入库，但脚本引用的官方文件路径必须指向 `_reverse/`，
  且脚本不得把官方代码/素材复制到仓库其他位置。
- 新增顶层目录前，先在本文件更新此结构图。

### 4. 代码规范

- 标识符（模块、类、函数、变量）一律英文；注释、文档、提交信息使用中文。
- 所有协议层代码必须带类型标注；报文构造/解析处必须用注释写明字节布局
  （偏移、长度、含义、取值来源），例如 `# byte[3]: DPI 档位索引, 0-4, 来源 kb/0007`。
- 协议常量集中放在 `src/mcmouse/protocol/` 下，禁止在业务代码里散落魔法数字；
  每个常量注明知识库来源条目编号。
- 格式化与静态检查：`ruff format` + `ruff check`，提交前必须通过。
- 依赖只允许加入确实需要的包；加包前检查是否已有等价依赖。

### 5. 测试规则

- 协议编解码必须有单元测试：构造 → 字节流、字节流 → 解析，双向都要测。
- 测试用报文样本放在 `tests/captures/`，文件命名 `YYYYMMDD_来源_描述.hex`，
  并在对应知识库条目中登记样本出处。
- 涉及真机的测试（`tests/live/`）必须默认跳过（`pytest.mark.live`），
  仅在显式指定时运行，且只允许只读取证类操作，写操作测试需二次确认。
- 任何"已在真机验证"的结论，必须在知识库中记录验证时的固件版本、连接方式
  （有线/2.4G 接收器）与原始报文。

### 6. Git 规范

- 提交信息使用 Conventional Commits 中文格式：`feat: …`、`fix: …`、`docs: …`、
  `reverse: …`（逆向发现入库专用）、`chore: …`。
- 未经用户明确同意，不执行 `git commit/push/reset/rebase` 等变更操作。

### 7. 安全与合规红线

- 本项目仅供个人学习研究，**禁止分发**官方安装包、解包出的官方代码、图片、
  字体等任何官方素材；`_reverse/` 仅作本地分析用。
- 逆向结论（字节级协议描述、字段含义）属于可入库的知识；官方原始代码不属于。
- 不访问/不写入工作目录以外的文件（系统 HID 设备访问除外）。
- 对设备的一切写命令（改配置、切档位）先读现状、可回滚；固件 OTA 属于二期，
  一期代码里禁止出现任何固件烧写路径。

---

## 第二部分：知识库管理规则

### 1. 定位

`docs/kb/` 是项目的逆向知识库：所有从官方软件、抓包、实机实验中得到的
**事实性结论**都必须在这里登记，代码只能引用知识库结论，不允许"我记得是这样"。

### 2. 目录与命名

```
docs/kb/
├── README.md            # 知识库索引（表格：编号 | 标题 | 分类 | 状态 | 日期）
├── architecture/        # 官方软件架构、逆向方法
├── protocol/            # HID 报文协议：命令字、字段布局、校验
├── devices/             # 具体设备档案：VID/PID、接口、固件、能力矩阵
└── pitfalls/            # 踩坑记录：失败实验、错误假设、注意事项
```

- 文件名：`NNNN-标题英文-kebab-case.md`，`NNNN` 为全库连续递增编号（如
  `protocol/0003-set-dpi-report.md`），编号永不复用。
- 每条目开头必须有 YAML front matter：

```yaml
---
id: 3                  # 数字编号，与文件名一致
title: 设置 DPI 的 Feature Report 布局
category: protocol     # architecture | protocol | devices | pitfalls
status: verified       # hypothesis | analyzed | verified
source: web-bundle     # web-bundle | asar | jsc | capture | live-test | spec
firmware: 待填          # 涉及具体固件时填写
date: 2026-08-08
---
```

### 3. 状态机（status）

- `hypothesis`：推测，未验证。
- `analyzed`：已从官方代码静态分析得出，但未在真机验证。
- `verified`：已通过抓包或真机实验验证，条目中必须附原始报文与验证环境。

代码中只允许依赖 `analyzed` 或 `verified` 状态的结论；引用 `hypothesis`
必须在代码注释中显式标注风险。状态升级时必须补充证据（报文样本路径等）。

### 4. 写入与更新时机

以下事件发生后**必须**同步更新知识库，再写/改代码：
1. 逆向得到新的协议字段、命令字、设备参数 → 新建或更新条目。
2. 实机实验推翻或证实某条结论 → 更新 status 并附证据。
3. 发现之前理解有误 → 更新条目，在文末"修订记录"追加一行（日期+改了什么），
   禁止无痕覆盖旧结论。
4. 每完成一个里程碑 → 更新 `docs/kb/README.md` 索引。

### 5. 交叉引用

- 代码注释引用知识库：`见 kb/0003`。
- 知识库条目引用代码：`src/mcmouse/protocol/dpi.py`。
- 知识库条目引用报文样本：`tests/captures/20260808_live_dpi-800.hex`。
- 引用官方文件时只写相对 `_reverse/` 的路径与分析位置，不复制内容。
