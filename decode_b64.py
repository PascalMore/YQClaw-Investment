#!/usr/bin/env python3
"""Auto-detect and decompress base64-encoded data"""
import base64, zlib, gzip, json, sys

def decompress_any(data):
    """Try multiple decompression strategies"""
    methods = [
        ("zlib.decompress", lambda d: zlib.decompress(d)),
        ("zlib decompress w/ -MAX_WBITS", lambda d: zlib.decompress(d, -zlib.MAX_WBITS)),
        ("gzip.decompress", lambda d: gzip.decompress(d)),
        ("zlib + strip adler", lambda d: zlib.decompress(d, 32)),
    ]
    for name, fn in methods:
        try:
            result = fn(data)
            print(f"✓ {name} worked! Length: {len(result)}")
            return result
        except Exception as e:
            print(f"✗ {name}: {e}")
    return None

b64 = sys.stdin.read().strip()
print(f"Base64 length: {len(b64)}")
data = base64.b64decode(b64)
print(f"Decoded data length: {len(data)}")
print(f"First bytes hex: {data[:10].hex()}")

decoded = decompress_any(data)
if decoded:
    try:
        obj = json.loads(decoded)
        print("\n=== JSON OUTPUT ===")
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"Decoded text (first 500 chars): {decoded[:500]}")
else:
    print("All decompression methods failed")