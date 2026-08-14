#!/usr/bin/env bash
# 构建 MCMouseDriver.app 并打成 DMG（M3）。
#
# 用法：./packaging/build_dmg.sh
# 产物：dist/MCMouseDriver.app、dist/MCMouseDriver-<版本>.dmg
#
# 签名说明：默认 ad-hoc 签名（codesign -s -），本机可用。
# 换机分发：对方按 DMG 里「首次打开（必读）.txt」右键打开，或见 README。
# 有 Developer ID 时设 MCMOUSE_SIGN_IDENTITY，脚本会加 hardened runtime + 时间戳；
# 公证需另跑：xcrun notarytool submit … && xcrun stapler staple …
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="MCMouseDriver"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/mcmouse/__init__.py)
SIGN_IDENTITY="${MCMOUSE_SIGN_IDENTITY:--}"
APP="dist/${APP_NAME}.app"
DMG="dist/${APP_NAME}-${VERSION}.dmg"
STAGE="build/dmg"

echo "==> 版本 ${VERSION}，签名身份 ${SIGN_IDENTITY}"

echo "==> 清理旧产物"
rm -rf "$APP" "$DMG" "$STAGE" build/AppIcon.iconset build/AppIcon.icns "build/${APP_NAME}"

echo "==> 生成图标"
uv run python packaging/make_icon.py build/AppIcon.icns

echo "==> PyInstaller 构建 .app"
uv run pyinstaller --noconfirm --clean --log-level WARN packaging/mcmouse.spec

echo "==> 签名"
if [ "$SIGN_IDENTITY" = "-" ]; then
  # ad-hoc：本机可跑；换机要右键打开或去隔离属性（kb/0009）
  codesign --force --deep --sign - "$APP"
else
  # Developer ID：公证要求 hardened runtime + 安全时间戳
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP"
fi
codesign --verify --deep --strict "$APP"

echo "==> 组装 DMG 内容"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/first-open.txt "$STAGE/首次打开（必读）.txt"

echo "==> 生成 DMG"
hdiutil create \
  -volname "${APP_NAME} ${VERSION}" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$DMG" >/dev/null

rm -rf "$STAGE"
echo "==> 完成：${DMG}（$(du -h "$DMG" | cut -f1)）"
