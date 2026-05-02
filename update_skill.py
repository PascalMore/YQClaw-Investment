#!/usr/bin/env python3
with open('/home/pascal/.openclaw/workspace-yquant/skills/data/data-pipeline/SKILL.md', 'r') as f:
    content = f.read()

old = '''| `Base64Codec` | ✅ 已完成 | JSON↔Base64 序列化/反序列化，支持可选 zlib 压缩 |

### Base64Codec 使用

```python
from serializers.base64_codec import Base64Codec, encode_json, decode_base64

codec = Base64Codec(compress=False)   # 纯 Base64
codec_gz = Base64Codec(compress=True) # Base64 + zlib 压缩

# 编码
b64_str = codec.encode({"key": "value"})


# 解码
data = codec.decode(b64_str)

# 便捷函数（单行调用）
b64_str = encode_json({"key": "value"})
data = decode_base64(b64_str)
```'''

new = '''| `Base64Codec` | ✅ 已完成 | JSON↔Base64，支持嵌套结构聚合 + zlib level=9 压缩 |

### Base64Codec 使用

```python
from serializers.base64_codec import Base64Codec, encode_json, decode_base64

# 嵌套结构 + zlib 压缩（默认，推荐，用于传输/存储）
codec = Base64Codec(
    compress=True,             # zlib level=9 压缩
    data_layout="nested",     # 按 group_key 分组聚合
    group_key="产品名称",     # 分组字段
    position_fields=[        # positions 内保留的字段
        "Wind代码", "资产名称", "持仓比例", "数量", "市值(本币)"
    ]
)
b64 = codec.encode(records)   # list[dict] → Base64
data = codec.decode(b64)       # Base64 → nested dict

# 扁平结构 + 无压缩（调试场景）
codec_flat = Base64Codec(compress=False, data_layout="flat")

# 便捷函数（单行调用，默认嵌套+压缩）
b64_str = encode_json(records, compress=True,
                      group_key="产品名称",
                      position_fields=["Wind代码","资产名称","持仓比例","数量","市值(本币)"])
data = decode_base64(b64_str)
```

### 嵌套结构说明

| 模式 | Base64 长度 | 适用场景 |
|------|-------------|----------|
| **nested + gzip** | ~5,700 chars | ✅ **生产/传输**（默认） |
| flat + plain | ~89,000 chars | 调试/可读性要求高 |

嵌套结构将每行重复的产品级字段提取到外层，只在 positions 数组内保留持仓字段，zlib 压缩前就消除了大量冗余文本。'''

if old in content:
    content = content.replace(old, new)
    with open('/home/pascal/.openclaw/workspace-yquant/skills/data/data-pipeline/SKILL.md', 'w') as f:
        f.write(content)
    print('Updated SKILL.md')
else:
    print('Pattern not found, showing snippet:')
    idx = content.find('Base64Codec')
    print(repr(content[idx:idx+400]))
