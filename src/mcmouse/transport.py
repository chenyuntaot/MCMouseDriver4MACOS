"""hidapi 传输层：枚举与打开迈从设备接口。

只负责 HID 收发，不含任何协议知识；协议编解码在 mcmouse.protocol。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import hid

from .devices import KNOWN_VARIANTS, MCHOSE_VIDS, DeviceVariant

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class HidInterface:
    """一枚枚举到的 HID 接口（一个 USB 设备可暴露多个接口）。"""

    path: bytes  # hidapi 设备路径，open 时使用
    vid: int
    pid: int
    usage_page: int
    usage: int
    interface_number: int
    product: str
    serial: str
    variant: DeviceVariant | None  # 命中注册表则为对应型号，否则 None


def enumerate_interfaces() -> Iterator[HidInterface]:
    """枚举系统上所有属于迈从 VID 的 HID 接口。"""
    for info in hid.enumerate():
        if info["vendor_id"] not in MCHOSE_VIDS:
            continue
        variant = next(
            (
                v
                for v in KNOWN_VARIANTS
                if v.vid == info["vendor_id"] and v.pid == info["product_id"]
            ),
            None,
        )
        yield HidInterface(
            path=info["path"],
            vid=info["vendor_id"],
            pid=info["product_id"],
            usage_page=info["usage_page"],
            usage=info["usage"],
            interface_number=info["interface_number"],
            product=info["product_string"] or "",
            serial=info["serial_number"] or "",
            variant=variant,
        )


def open_interface(iface: HidInterface) -> hid.device:
    """打开指定接口；调用方负责 close。"""
    dev = hid.device()
    dev.open_path(iface.path)
    return dev


CONFIG_USAGE_PAGES = (0xFF01, 0xFF0B)  # 配置接口 usage page，kb/0003 §1


def pick_config_interface() -> HidInterface | None:
    """选择配置接口：优先已登记型号 + usage page 0xFF01，其次 0xFF0B。"""
    interfaces = [i for i in enumerate_interfaces() if i.variant is not None]
    for page in CONFIG_USAGE_PAGES:
        for i in interfaces:
            if i.usage_page == page:
                return i
    return None
