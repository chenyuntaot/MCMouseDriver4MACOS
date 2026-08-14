# 打包与分发

构建入口：`packaging/build_dmg.sh`。选型见 [`tech-selection.md`](tech-selection.md) §2.4，踩坑见 [`kb/0009`](kb/pitfalls/0009-macos-app-packaging-pitfalls.md)。

## 构建

```bash
./packaging/build_dmg.sh
```

依次生成图标、用 PyInstaller 打出 `.app`、签名、再打成 UDZO 格式的 DMG。产物：

- `dist/MCMouseDriver.app`
- `dist/MCMouseDriver-<version>.dmg`

当前安装包为 Apple Silicon（arm64）。Intel Mac 需要另行构建。

## 首次打开

未使用 Developer ID 签名并公证时，经隔空投送或网盘拷贝到其他 Mac，Gatekeeper 会拦截启动。用户可：

1. 按住 Control 点按应用，选择「打开」
2. 系统设置 → 隐私与安全性 → 「仍要打开」
3. 终端执行：

```bash
xattr -dr com.apple.quarantine /Applications/MCMouseDriver.app
open /Applications/MCMouseDriver.app
```

DMG 内附 `首次打开（必读）.txt`，内容与上述步骤一致。

应用为菜单栏形态，无 Dock 图标。无法连接设备时：

```bash
/Applications/MCMouseDriver.app/Contents/MacOS/MCMouseDriver --selftest
```

## 签名与公证

默认 ad-hoc 签名，仅保证构建机可运行。向其他 Mac 分发且希望双击即可打开，需 [Apple Developer Program](https://developer.apple.com/programs/) 的 Developer ID 证书，并完成公证。

```bash
export MCMOUSE_SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"
./packaging/build_dmg.sh
xcrun notarytool store-credentials notary   # 仅需一次
xcrun notarytool submit dist/MCMouseDriver-*.dmg --keychain-profile notary --wait
xcrun stapler staple dist/MCMouseDriver-*.dmg
```

`build_dmg.sh` 在设置了 `MCMOUSE_SIGN_IDENTITY` 时会启用 hardened runtime 与安全时间戳。
