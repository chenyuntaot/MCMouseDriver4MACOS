#!/usr/bin/env python3
"""枚举系统 HID 设备中的迈从接口，打印 usage page / interface 等细节。

用途：技术选型方案 §6 待验证实验 1（macOS 能否枚举到 A7 的厂商接口）。
只读操作，不发送任何写命令。

用法：uv run scripts/probe_hid.py [--all]
  --all  列出系统全部 HID 设备（不止迈从），排查时可用
"""

from __future__ import annotations

import argparse

import hid

from mcmouse.devices import MCHOSE_VIDS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="列出全部 HID 设备")
    args = parser.parse_args()

    found = 0
    for info in hid.enumerate():
        if not args.all and info["vendor_id"] not in MCHOSE_VIDS:
            continue
        found += 1
        print(
            f"vid=0x{info['vendor_id']:04x} pid=0x{info['product_id']:04x} "
            f"if={info['interface_number']} "
            f"usage_page=0x{info['usage_page']:04x} usage=0x{info['usage']:04x}"
        )
        print(f"  product: {info['product_string']}")
        mfr = info["manufacturer_string"]
        print(f"  manufacturer: {mfr}  serial: {info['serial_number']}")
        print(f"  path: {info['path']!r}")
    if not found:
        print("未发现目标设备。请用有线或 2.4G 接收器连接鼠标后重试。")
        return 1
    print(f"\n共 {found} 个接口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
