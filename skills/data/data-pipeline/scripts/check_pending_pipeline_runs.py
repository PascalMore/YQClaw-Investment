#!/usr/bin/env python3
"""
扫描某归档目录下"已归档 vs 已跑过 pipeline"的差异。

用法：
    python check_pending_pipeline_runs.py [--date YYYY-MM-DD]

输出：
    - image_cache 唯一 hash 数（飞书推送的全部）
    - 归档目录 portfolio_*.jpg 唯一 hash 数（agent 第一步归档的）
    - 归档目录 xlsx 痕迹数（pipeline 已跑过留产物）
    - 待跑的图路径列表（按归档顺序）

实战背景（2026-06-27 用户多批推送）：
    用户分多批（9:46 + 10:02 + 10:10）推同一批持仓截图，image_cache unique
    数看着不变，但 pipeline 实际只跑了第一轮的子集。仅凭"归档目录里有"
    不能说"全部入库了"——必须看 xlsx 痕迹。

决策矩阵（hash 匹配）：

    ┌────────────────┬──────────────────────┬──────────────────────┐
    │ image_cache     │ 归档目录             │ pipeline 跑过?        │
    │ unique hash     │ (portfolio_*.jpg)    │ (同名 xlsx/vision_raw)│
    ├────────────────┼──────────────────────┼──────────────────────┤
    │ ✅ 有           │ ✅ 有                 │ ❌ 没有               │ → 需要跑
    │ ✅ 有           │ ✅ 有                 │ ✅ 有                  │ → 重复 upsert (无副作用)
    │ ❌ 没           │ ✅ 有                 │ ?                     │ → agent 推过但 cache 清了
    │ ✅ 有           │ ❌ 没                 │ ❌                    │ → 飞书新推未归档
    └────────────────┴──────────────────────┴──────────────────────┘
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

DEFAULT_REPO = Path("/home/pascal/workspace/yquant-investment")
DEFAULT_IMAGE_CACHE = Path("/home/pascal/.hermes/profiles/yquant/image_cache")
SM_ROOT = DEFAULT_REPO / "skills/data/source/smart-money"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def scan_dir(d: Path) -> dict[str, Path]:
    """返回 {md5: path} 字典（按 md5 去重，保留首个）。"""
    out: dict[str, Path] = {}
    for p in sorted(d.glob("*.jpg")):
        h = md5(p)
        out.setdefault(h, p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="归档日期 YYYY-MM-DD（默认今天）", default=None)
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    args = ap.parse_args()

    repo = Path(args.repo)
    sm = repo / "skills/data/source/smart-money"
    date = args.date or dt.date.today().isoformat()

    image_cache = DEFAULT_IMAGE_CACHE
    archive_dir = sm / date / "image"

    if not archive_dir.exists():
        print(f"❌ 归档目录不存在: {archive_dir}")
        return 1

    # 1) image_cache 里所有 unique hash（飞书推送的全部）
    cache_hashes: dict[str, Path] = {}
    if image_cache.exists():
        cache_hashes = scan_dir(image_cache)
    print(f"📦 image_cache unique hash: {len(cache_hashes)}")

    # 2) 归档目录 portfolio_*.jpg unique hash
    archive_hashes = scan_dir(archive_dir)
    print(f"📁 归档目录 portfolio_*.jpg unique hash: {len(archive_hashes)}")

    # 3) pipeline 跑过 = 归档目录里有对应 xlsx 或 vision_raw
    # xlsx 命名约定：portfolio_20260627_100526.xlsx / trade_20260627_100516.xlsx
    # 不与 jpg 同时间戳，所以无法用文件名 1:1 匹配。改为用 MongoDB source_image 查。
    # 本脚本只统计归档目录里 xlsx 总数，作为参考
    xlsx_count = len(list(archive_dir.glob("*.xlsx")))
    vision_raw_count = len(list(archive_dir.glob("*vision_raw*.json")))
    vision_error_count = len(list(archive_dir.glob("*vision_error*.json")))
    print(f"📊 归档目录 xlsx 痕迹（pipeline 跑过产物）: {xlsx_count}")
    print(f"📊 vision_raw json: {vision_raw_count} | vision_error json: {vision_error_count}")

    # 4) 差集分析
    print()
    print("=== 决策矩阵 ===")
    print()

    # A) cache 有、archive 有、但 xlsx 没有 → 待跑
    in_cache_and_archive = cache_hashes.keys() & archive_hashes.keys()
    archive_only = archive_hashes.keys() - cache_hashes.keys()
    cache_only = cache_hashes.keys() - archive_hashes.keys()

    # 简化：xlsx 数 ≈ 跑过的不同图数（同一图多次跑只算一次）
    # 实际更准：把 MongoDB source_image 拉出来
    print(f"🔁 cache ∩ archive（两边都有）: {len(in_cache_and_archive)} 张")
    print(f"📂 archive \\ cache（归档有但 cache 没了，可能是 cache 清了）: {len(archive_only)} 张")
    print(f"🆕 cache \\ archive（飞书新推未归档）: {len(cache_only)} 张")
    print()

    # B) 待跑：归档有，但还没在 xlsx 痕迹里（粗略估计）
    # 由于 xlsx 时间戳 ≠ jpg 时间戳，无法用文件名匹配
    # 推荐做法：用户根据 xlsx 数和归档数对比判断
    # 启发式：如果 xlsx_count 接近 archive unique 数，说明大部分跑过
    if xlsx_count >= len(archive_hashes) * 0.8:
        print("✅ 多数归档图已跑过 pipeline（xlsx 数 ≥ 80%）")
    else:
        print(f"⚠️  至少 {len(archive_hashes) - xlsx_count} 张图可能没跑过")
        print("    （粗略估计；精确判断需查 MongoDB portfolio_position.source_image）")

    print()
    print("=== 完整待跑列表（按归档文件名排序）===")
    for h, p in sorted(archive_hashes.items(), key=lambda kv: kv[1].name):
        in_cache = "✓" if h in cache_hashes else "·"
        print(f"  {in_cache} {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())