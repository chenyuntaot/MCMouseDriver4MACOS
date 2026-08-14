"""打包入口：.app 双击后直接进菜单栏应用，不经过 CLI 参数解析。

菜单栏应用（LSUIElement）没有终端输出通道，装包后若读不到鼠标很难定位，
因此保留一个自检模式：

    dist/MCMouseDriver.app/Contents/MacOS/MCMouseDriver --selftest

它只做只读操作（枚举接口 + 读固件/电量/配置），不写设备。
"""

from __future__ import annotations

import sys


def selftest() -> int:
    """在打包环境里验证 hidapi 与协议链路（只读）。"""
    from mcmouse.session import OldProtocolSession
    from mcmouse.transport import pick_config_interface

    iface = pick_config_interface()
    if iface is None or iface.variant is None:
        print("未发现迈从设备：请用有线或 2.4G 接收器连接鼠标")
        return 1
    print(f"设备: {iface.variant.model}（{iface.variant.role}）")
    if iface.variant.protocol != "old":
        print("新协议设备（kb/0004）暂不支持配置")
        return 1
    with OldProtocolSession.open(iface) as session:
        firmware = session.read_firmware()
        info = session.read_device_info()
        cfg = session.read_config()
    print(f"固件: {firmware}  电量: {info.battery_level}%")
    if cfg.dpi_count == 0:
        print("读到全零配置：鼠标休眠，晃动后重试（kb/0007 §3）")
        return 1
    print(f"DPI 档位: {', '.join(str(d) for d in cfg.dpis[: cfg.dpi_count])}")
    print("自检通过")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    from mcmouse.gui import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
