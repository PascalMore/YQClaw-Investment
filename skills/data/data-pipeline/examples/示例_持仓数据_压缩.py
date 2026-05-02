"""
持仓数据压缩工具
- 读取 xlsx/csv
- 范式化为嵌套 JSON（产品 → 持仓）
- 压缩为单行文本（lzstring / hex / base64）
- 输出到文件，或从文件恢复
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

try:
    import lzstring
    _HAS_LZSTRING = True
except ImportError:
    _HAS_LZSTRING = False

try:
    import zlib
    _HAS_ZLIB = True
except ImportError:
    _HAS_ZLIB = False

# 复用 transformers.portfolio_normalizer 中的通用实现
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from transformers.portfolio_normalizer import flatten_to_nested


def normalize_portfolio(df: pd.DataFrame) -> dict:
    """将扁平持仓表转为嵌套 JSON（委托给 portfolio_normalizer）。"""
    return flatten_to_nested(
        df,
        date_field="截止日期",
        product_fields=["产品名称", "产品代码", "最新净值", "最新份额", "最新规模"],
        position_fields=["Wind代码", "资产名称", "持仓比例", "数量", "市值(本币)"],
        group_key="产品名称",
    )


def compress_lzstring(data: dict) -> str:
    """lzstring 压缩（UTF16 格式，短小适合拍照）"""
    if not _HAS_LZSTRING:
        raise RuntimeError("lzstring 未安装，请运行: pip install lzstring")
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    lz = lzstring.LZString()
    return lz.compressToUTF16(json_str)


def compress_zlib_hex(data: dict) -> str:
    """zlib 压缩 + hex 编码（纯十六进制，任意文本编辑器可显示）"""
    if not _HAS_ZLIB:
        raise RuntimeError("zlib 不可用")
    json_bytes = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    return compressed.hex()


def compress_base64(data: dict) -> str:
    """zlib 压缩 + base64（适合粘贴到 URL 参数）"""
    if not _HAS_ZLIB:
        raise RuntimeError("zlib 不可用")
    import base64
    json_bytes = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def decompress(encoded: str, method: str = "lzstring") -> dict:
    """从压缩文本还原"""
    if method == "lzstring":
        if not _HAS_LZSTRING:
            raise RuntimeError("lzstring 未安装")
        lz = lzstring.LZString()
        json_str = lz.decompressFromUTF16(encoded)
        return json.loads(json_str)
    elif method == "zlib_hex":
        import zlib
        compressed = bytes.fromhex(encoded)
        json_bytes = zlib.decompress(compressed)
        return json.loads(json_bytes.decode("utf-8"))
    elif method == "base64":
        import zlib, base64
        compressed = base64.urlsafe_b64decode(encoded)
        json_bytes = zlib.decompress(compressed)
        return json.loads(json_bytes.decode("utf-8"))
    else:
        raise ValueError(f"未知压缩方法: {method}")


def main():
    parser = argparse.ArgumentParser(description="持仓数据压缩工具")
    sub = parser.add_subparsers(dest="action", help="操作")

    # 压缩命令
    compress_cmd = sub.add_parser("compress", help="压缩 xlsx/csv 文件")
    compress_cmd.add_argument("input", help="输入文件（xlsx 或 csv）")
    compress_cmd.add_argument("-o", "--output", default="portfolio_compressed.txt", help="输出文件")
    compress_cmd.add_argument("-m", "--method", choices=["lzstring", "zlib_hex", "base64", "json"],
                              default="lzstring", help="压缩方法（默认 lzstring，最短）")

    # 解压命令
    decompress_cmd = sub.add_parser("decompress", help="从压缩文本还原")
    decompress_cmd.add_argument("input", help="压缩文本文件")
    decompress_cmd.add_argument("-m", "--method", choices=["lzstring", "zlib_hex", "base64"], default="lzstring")
    decompress_cmd.add_argument("-o", "--output", help="输出 JSON 文件")

    args = parser.parse_args()

    if args.action == "compress":
        path = Path(args.input)
        suffix = path.suffix.lower()

        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif suffix == ".csv":
            df = pd.read_csv(path)
        else:
            print(f"不支持的文件格式: {suffix}", file=sys.stderr)
            sys.exit(1)

        print(f"📖 读取 {len(df)} 行 × {len(df.columns)} 列", file=sys.stderr)

        data = normalize_portfolio(df)
        meta = data["metadata"]
        total_products = meta["total_products"]
        total_days = meta["total_days"]
        print(f"🔧 范式化完成: {total_days} 天, {total_products} 只产品, {meta['total_records']} 条持仓记录", file=sys.stderr)

        method = args.method
        if method == "lzstring":
            encoded = compress_lzstring(data)
            note = "lzstring（UTF16，可 OCR 识读）"
        elif method == "zlib_hex":
            encoded = compress_zlib_hex(data)
            note = "zlib+hex（纯十六进制）"
        elif method == "base64":
            encoded = compress_base64(data)
            note = "zlib+base64（URL 安全）"
        else:
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            note = "原始 JSON"

        # 写入文件
        Path(args.output).write_text(encoded, encoding="utf-8")

        # 统计信息
        original_size = len(json.dumps(data, ensure_ascii=False))
        compressed_size = len(encoded)
        ratio = original_size / compressed_size if compressed_size else 0

        print(f"\n✅ 压缩完成 → {args.output}", file=sys.stderr)
        print(f"   方法: {note}", file=sys.stderr)
        print(f"   原始: {original_size} 字符", file=sys.stderr)
        print(f"   压缩后: {compressed_size} 字符", file=sys.stderr)
        print(f"   压缩比: {ratio:.1f}x", file=sys.stderr)
        print(f"\n📄 压缩后文本长度 {compressed_size} 字符", file=sys.stderr)

    elif args.action == "decompress":
        encoded = Path(args.input).read_text(encoding="utf-8").strip()
        data = decompress(encoded, method=args.method)

        if args.output:
            Path(args.output).write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8"
            )
            print(f"✅ 已还原到 {args.output}")
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
