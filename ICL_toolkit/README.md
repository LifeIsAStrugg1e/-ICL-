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

# 有损压缩（fmt='jpg'，quality 控制压缩率 10-99）
pack_ico(images, "output.ico", fmt='jpg', quality=85)

# ICL -> ICO 一步转换
icl_to_ico("input.icl", "output.ico")

# 图片(JPG/PNG/BMP) -> ICO
images_to_ico(["a.jpg", "b.png", "c.bmp"], "output.ico")
```

## API

| 函数 | 说明 |
|------|------|
| `extract(path, out_dir, fmt, quality, progress_cb)` | 解压 ICL/ICO，fmt: raw/jpg/bmp/png |
| `pack_ico(images, out_path, fmt, quality, batch_size, rotation)` | 打包 JXAG ICO |
| `icl_to_ico(icl_path, ico_path, fmt, quality, rotation)` | ICL 转 ICO |
| `images_to_ico(paths, out_path, fmt, quality, rotation)` | 图片文件转 ICO |
| `folder_to_ico(folder, out_path, fmt, quality, rotation)` | 文件夹内图片转 ICO |
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
| `fmt` | `'rgb565'` | `rgb565`=16位LZO无损(C工具兼容) / `rgb24`=BGRA32无损 / `jpg`=JPG有损 |
| `quality` | `90` | JPG 压缩率 10-99（自动截断），仅 fmt='jpg' 时生效 |
| `batch_size` | `20` | 每批处理图片数，控制内存峰值 |
| `rotation` | `0` | 压缩前顺时针旋转 0/90/180/270 度 |

### extract 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `path` | - | 输入 .icl/.ico 路径 |
| `out_dir` | - | 输出目录（自动创建） |
| `fmt` | `'raw'` | `raw`=保留原始格式 / `jpg` / `bmp` / `png` |
| `quality` | `95` | JPG 重编码质量（仅 fmt='jpg'） |
| `progress_cb` | `None` | 回调 `(done, total, filename)`，每张保存后调用 |

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
