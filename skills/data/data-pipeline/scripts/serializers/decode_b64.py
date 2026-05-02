#!/usr/bin/env python3
"""Base64 字符串反解析工具

支持自动检测压缩格式，还原 JSON 数据
"""
import base64
import json
import zlib
import gzip
import sys


def try_decompress(data: bytes) -> bytes | None:
    """尝试多种解压缩策略"""
    strategies = [
        ("zlib", lambda d: zlib.decompress(d)),
        ("zlib_raw", lambda d: zlib.decompress(d, -zlib.MAX_WBITS)),
        ("gzip", lambda d: gzip.decompress(d)),
        ("zlib_24", lambda d: zlib.decompress(d, 24)),
    ]
    for name, fn in strategies:
        try:
            result = fn(data)
            print(f"  ✓ {name} 解压成功 ({len(result)} bytes)", file=sys.stderr)
            return result
        except Exception as e:
            print(f"  ✗ {name}: {e}", file=sys.stderr)
    return None


def decode_base64_robust(encoded: str) -> dict | None:
    """鲁棒的 Base64 反解析：自动尝试多种解压策略"""
    print(f"输入 Base64 长度: {len(encoded)}", file=sys.stderr)

    # Step 1: Base64 解码
    try:
        data = base64.b64decode(encoded)
        print(f"Base64 解码成功: {len(data)} bytes, 前8字节: {data[:8].hex()}", file=sys.stderr)
    except Exception as e:
        print(f"Base64 解码失败: {e}", file=sys.stderr)
        return None

    # Step 2: 尝试解压缩
    decompressed = try_decompress(data)

    # Step 3: JSON 解析
    target = decompressed if decompressed else data
    try:
        obj = json.loads(target)
        print(f"JSON 解析成功", file=sys.stderr)
        return obj
    except Exception as e:
        print(f"JSON 解析失败: {e}", file=sys.stderr)
        # 打印原始内容前200字符用于调试
        try:
            preview = target[:500].decode("utf-8", errors="replace")
            print(f"原始内容预览: {preview}", file=sys.stderr)
        except Exception:
            print(f"原始内容 (hex): {target[:100].hex()}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) > 1:
        # 从文件或参数读取
        if sys.argv[1] == "--file" and len(sys.argv) > 2:
            with open(sys.argv[2], "r") as f:
                encoded = f.read().strip()
        else:
            encoded = sys.argv[1]
    else:
        # 从 stdin 读取
        encoded = sys.stdin.read().strip()

    result = decode_base64_robust(encoded)

    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    else:
        print("❌ 反解析失败", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
