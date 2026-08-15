# 知识库索引

管理规则见根目录 `AGENTS.md` 第二部分。编号全库连续递增，永不复用。

| 编号 | 标题 | 分类 | 状态 | 日期 |
|---|---|---|---|---|
| 0001 | [官方软件架构与逆向信息源](architecture/0001-official-software-architecture.md) | architecture | analyzed | 2026-08-08 |
| 0002 | [鼠标设备注册表（VID/PID 清单）](devices/0002-mouse-device-registry.md) | devices | analyzed | 2026-08-08 |
| 0003 | [旧协议报文框架（Feature Report + XOR 0xFF）](protocol/0003-old-protocol-framing.md) | protocol | analyzed | 2026-08-08 |
| 0004 | [新协议报文框架（Output Report 0x4D）](protocol/0004-new-protocol-framing.md) | protocol | analyzed | 2026-08-08 |
| 0005 | [旧协议功能命令布局（配置/DPI/回报率/传感器/电量）](protocol/0005-old-protocol-commands.md) | protocol | analyzed | 2026-08-08 |
| 0006 | [旧协议按键映射、宏、灯效与电量](protocol/0006-old-protocol-buttons-macros-light-battery.md) | protocol | analyzed | 2026-08-15 |
| 0007 | [踩坑：旧协议读路径的三个真机坑](pitfalls/0007-old-protocol-read-pitfalls.md) | pitfalls | verified | 2026-08-08 |
| 0008 | [踩坑：macOS 27 上 Qt 托盘菜单必崩与绕行](pitfalls/0008-qt-tray-crash-macos27.md) | pitfalls | verified | 2026-08-09 |
| 0009 | [踩坑：打包 .app / DMG 的三个坑](pitfalls/0009-macos-app-packaging-pitfalls.md) | pitfalls | verified | 2026-08-14 |

## 分类目录

- `architecture/` — 官方软件架构、逆向方法与工具链
- `protocol/` — HID 报文协议：命令字、字段布局、校验
- `devices/` — 设备档案：VID/PID、接口、固件、能力矩阵
- `pitfalls/` — 踩坑记录：失败实验、错误假设、注意事项
