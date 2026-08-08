#!/usr/bin/env python3
"""探测迈从鼠标厂商接口的 Feature Report 可读性（只读实验）。

用途：技术选型方案 §6 待验证实验 2（macOS 上 get_feature_report 通路是否可用）。
对 VID 0x3837 的每个厂商自定义 usage page 接口，依次尝试 report ID 0~7 的
GET_REPORT 请求并打印返回。只发标准 HID 读请求，不发送任何写命令。

用法：uv run scripts/probe_feature_reports.py
"""

from __future__ import annotations

import hid

VENDOR_USAGE_PAGE_MIN = 0xFF00  # 厂商自定义 usage page 区间起点
MCHOSE_VID = 0x3837  # 见 kb/devices/0002
REPORT_LENGTH = 64  # 读 buffer 长度，超出实际报告长度不影响
MAX_REPORT_ID = 7


def main() -> int:
    targets = [
        i
        for i in hid.enumerate()
        if i["vendor_id"] == MCHOSE_VID and i["usage_page"] >= VENDOR_USAGE_PAGE_MIN
    ]
    if not targets:
        print("未发现迈从厂商接口，请先连接鼠标。")
        return 1

    for info in targets:
        print(
            f"== if={info['interface_number']} "
            f"usage_page=0x{info['usage_page']:04x} usage=0x{info['usage']:04x} "
            f"{info['product_string']}"
        )
        dev = hid.device()
        try:
            dev.open_path(info["path"])
        except OSError as exc:
            print(f"   打开失败: {exc}")
            continue
        for report_id in range(MAX_REPORT_ID + 1):
            try:
                data = dev.get_feature_report(report_id, REPORT_LENGTH)
            except OSError as exc:
                print(f"   report {report_id}: 错误 {exc}")
                continue
            nonzero = any(data[1:]) if len(data) > 1 else False
            hex_preview = " ".join(f"{b:02x}" for b in data[:20])
            print(
                f"   report {report_id}: len={len(data)} "
                f"nonzero={nonzero} [{hex_preview}…]"
            )
        dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
