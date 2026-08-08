---
id: 1
title: 官方软件架构与逆向信息源
category: architecture
status: analyzed
source: asar
firmware: 不适用
date: 2026-08-08
---

# 官方软件架构与逆向信息源

## 解包链（2026-08-08 完成）

```
MCHOSE HUB installer.exe            # NSIS 自解压包, 173MB, PE32 GUI
└── 7zz x  →  $PLUGINSDIR/app-64.7z # 真正的应用本体
    └── 7zz x  →  Electron 应用目录   # _reverse/app/
        └── resources/app.asar
            └── npx @electron/asar extract  →  _reverse/asar_src/
```

## 架构结论

**MCHOSE HUB = Electron 壳 + 远程 Web 应用。**

- Electron 主进程：`out/main/index.js` → 仅是 `bytecode-loader.cjs` 的加载器，
  真实逻辑编译为 V8 字节码 `*.jsc`（bytenode 保护）。直接反编译成本高。
- preload：`out/preload/index.js` **明文未保护**，暴露约 200 个 IPC 方法
  （`window.electronAPI.*`），是理解桌面端能力的完整清单。
- 渲染层 = 远程 Web SPA：
  - 生产：`https://www.mchose.com.cn/`（路由 `#/connectDevice`、`/tray.html`）
  - 测试：`https://drivertest.maicong.cn`
  - CDN：`https://cdn.mchose.com.cn/configCenter`、`configCenter-test`、
    `customPage/{pre,prod,...}/index.html`
- package.json 关键依赖：`usb`（node-usb 2.x，桌面端 USB 通信）、`koffi`
  （FFI 调 DLL）、`@grpc/grpc-js`、`jszip`（固件包解压？）、`win-audio`。
- `_reverse/app/libs/<设备型号>/` 是按设备型号组织的 Windows 驱动包
  （多为耳机音频 APO / Bolutek CM2025 驱动），鼠标配置不在这里。

## 协议载体

配置走 **USB HID**（厂商自定义 usage page），Web 端用 WebHID。证据与线索：

- preload 中 USB 相关 IPC：`getUsbDeviceDescriptor`、`getFWVersionFromUsbDescriptor`、
  `getUsbStringDescriptor`、`getUsbVersion`。
- 事件通道：`battery_info`（电量上报）、`g20_light`（灯效）、`onOtaMessage`。
- OTA 相关 IPC（二期线索）：`otaDevice`、`getFirmwareBinData`。
- `sdk-worker-*.jsc` 是 CMedia 音频 SDK（耳机），与鼠标无关，不要混淆。

## 逆向信息源优先级

1. **官方 Web bundle**（第一信息源）：`https://www.mchose.com.cn/` 首页引用的
   `/assets/main-*.js`（2026-08-08 快照为 `main-zuTdzYUB.js`，Vite 构建）。
   minify 但可读，HID 报文定义应在其中。注意记录分析时的 bundle hash。
2. **真机抓包**（验证手段）：Windows + Wireshark/USBPcap；macOS `tcpdump -i XHC*` 待验证。
3. asar 明文 JS（preload、Lang/main.js 等）：已读完 preload。
4. `.jsc` 字节码：strings 可挖 URL/符号名（已用），完整反编译留作最后手段。

## 修订记录

- 2026-08-08 初版（解包分析完成，Web bundle 协议字段提取待做）。
