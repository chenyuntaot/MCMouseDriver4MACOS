"""pytest 全局配置：live 标记默认跳过。"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--runlive", action="store_true", help="运行需要真机的测试")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--runlive"):
        return
    skip = pytest.mark.skip(reason="需要真机，用 --runlive 显式运行")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
