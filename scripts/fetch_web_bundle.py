#!/usr/bin/env python3
"""抓取 MCHOSE 官方 Web 驱动的全部 JS/CSS 资源到 _reverse/web/。

用途：逆向分析协议的第一信息源（见 docs/kb/architecture/0001）。
只下载，不修改；下载内容属于官方素材，仅留在 _reverse/ 本地分析，禁止分发。

用法：uv run scripts/fetch_web_bundle.py [--base https://www.mchose.com.cn]
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

# 资源引用模式：Vite 构建产物中的相对/绝对资源路径
ASSET_RE = re.compile(r'["\']((?:\./|/)[\w./-]+\.(?:js|css|json))(?:\?[^"\']*)?["\']')
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://www.mchose.com.cn")
    parser.add_argument("--out", default="_reverse/web")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    queue = ["/"]
    seen: set[str] = set()
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        url = (
            path
            if path.startswith("http")
            else args.base + ("" if path.startswith("/") else "/") + path
        )
        try:
            data = fetch(url)
        except Exception as exc:  # noqa: BLE001 - 抓取失败只跳过，不中断
            print(f"[skip] {url}: {exc}", file=sys.stderr)
            continue

        rel = "index.html" if path == "/" else path.lstrip("/")
        if rel.startswith("./"):
            rel = rel[2:]
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"[ok] {url} -> {dest} ({len(data)} bytes)")

        # 只在文本资源里继续找引用
        if dest.suffix in {".html", ".js", ".css", ".json"}:
            try:
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                continue
            for m in ASSET_RE.finditer(text):
                ref = m.group(1)
                if ref.startswith("./"):
                    # 相对路径：相对于当前资源所在目录
                    ref = str(Path(rel).parent / ref[2:])
                if ref not in seen:
                    queue.append(ref)

    print(f"\n共抓取 {len(seen)} 个资源到 {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
