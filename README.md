# ICL 工具集

ICL/ICO 图片处理工具，包含图形化工具和可复用的库。

## 目录结构

```
├── icl_tool/        # 图形化工具（tkinter GUI）
├── ICL_toolkit/     # 可复用库（供工具箱调用）
└── README.md
```

## icl_tool（图形化工具）

独立的 tkinter GUI，支持 ICL/ICO 解压提取和打包。

```bash
cd icl_tool
python icl_tool.py
```

## ICL_toolkit（库）

模块化设计，可集成到其他项目中。

```python
from ICL_toolkit import extract, pack_ico, icl_to_ico

# 解压
count, fmt = extract("file.icl", "output_dir", fmt="bmp")

# 打包
pack_ico([{'index': 0, 'bmp': bmp_bytes}], "output.ico")

# ICL 转 ICO
icl_to_ico("input.icl", "output.ico")
```

详见 [ICL_toolkit/README.md](ICL_toolkit/README.md)

## 依赖

```bash
pip install pillow numpy
```

## 格式说明

- **ICL**: GUS_3 格式，内嵌 JPG
- **ICO**: JXAG 格式，LZO 压缩 RGB565（与 C 提取器互通）
