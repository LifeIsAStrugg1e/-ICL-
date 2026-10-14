# ICL_toolkit

ICL/ICO 图片处理工具库，与 C 提取器完全互通。

## 安装依赖

```bash
pip install pillow numpy
```

## 使用

```python
from ICL_toolkit import extract, pack_ico, icl_to_ico, images_to_ico

# 解压 ICL/ICO -> BMP
count, fmt = extract("file.icl", "output_dir", fmt="bmp")

# 打包 BMP -> JXAG ICO（懒加载，逐批读取）
pack_ico([{'index': 0, 'path': 'a.bmp'}], "output.ico")

# 有损压缩（JPG 编码，quality 控制压缩率）
pack_ico(images, "output.ico", lossy=True, quality=85)

# ICL -> ICO 一步转换
icl_to_ico("input.icl", "output.ico")

# 图片(JPG/PNG/BMP) -> ICO
images_to_ico(["a.jpg", "b.png", "c.bmp"], "output.ico")
```

## API

| 函数 | 说明 |
|------|------|
| `extract(path, out_dir, fmt)` | 解压 ICL/ICO，fmt: raw/jpg/bmp/png |
| `pack_ico(images, out_path, lossy, quality, batch_size)` | 打包 JXAG ICO |
| `icl_to_ico(icl_path, ico_path)` | ICL 转 ICO |
| `images_to_ico(paths, out_path)` | 图片文件转 ICO |
| `folder_to_ico(folder, out_path)` | 文件夹内图片转 ICO |
| `detect(data)` | 检测格式: 'icl'/'ico'/None |
| `parse_icl(data)` | 解析 ICL 文件 |
| `extract_ico(data)` | 解压 ICO 数据 |
| `decode_jpg(data)` | 解码 JPG |
| `lzo_compress(data)` | LZO 压缩 |
| `lzo_decompress(data, size)` | LZO 解压 |

### pack_ico 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `images` | - | `[{'index': i, 'path': 'a.bmp'}]` 或 `[{'index': i, 'data': bytes}]` |
| `out_path` | - | 输出 ICO 路径 |
| `lossy` | `False` | False=LZO RGB565 无损, True=JPG 有损 |
| `quality` | `85` | JPG 压缩率 (10-100)，仅 lossy=True 时生效 |
| `batch_size` | `20` | 每批处理图片数，控制内存峰值 |

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
