"""序列化编解码模块

提供 JSON ↔ Base64 等传输编码支持，属于 ETL Pipeline 的 Transport 层
"""
from .base64_codec import Base64Codec, encode_json, decode_base64

__all__ = ["Base64Codec", "encode_json", "decode_base64"]