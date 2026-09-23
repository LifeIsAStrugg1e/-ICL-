# ICL_toolkit

ICL/ICO 图片处理工具库，与 C 提取器完全互通。

## 安装依赖

```bash
pip install pillow numpy
```

## 使用

```python
from ICL_toolkit import extract, pack_ico, icl_to_ico

# 解压 ICL/ICO -> BMP
count, fmt = extract("file.icl", "output_dir", fmt="bmp")

# 打包 BMP -> JXAG ICO
pack_ico([{'index': 0, 'bmp': bmp_bytes}], "output.ico")

# ICL -> ICO 一步转换
icl_to_ico("input.icl", "output.ico")
```

## API

| 函数 | 说明 |
|------|------|
| `extract(path, out_dir, fmt)` | 解压 ICL/ICO，fmt: raw/jpg/bmp/png |
| `pack_ico(images, out_path)` | 打包 JXAG ICO |
| `icl_to_ico(icl_path, ico_path)` | ICL 转 ICO |
| `detect(data)` | 检测格式: 'icl'/'ico'/None |
| `parse_icl(data)` | 解析 ICL 文件 |
| `extract_ico(data)` | 解压 ICO 数据 |
| `decode_jpg(data)` | 解码 JPG |
| `lzo_compress(data)` | LZO 压缩 |
| `lzo_decompress(data, size)` | LZO 解压 |

## 目录结构

```
ICL_toolkit/
├── __init__.py        # 统一入口
├── icl/               # ICL 解析 + JPG 解码
├── ico/               # JXAG ICO 打包/解压
├── lzo/               # LZO 压缩
├── bmp/               # RGB565/BMP 转换
├── converters/        # 组合转换器
└── _dlls/             # 32位 DLL 依赖
```
