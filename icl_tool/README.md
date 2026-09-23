# ICL Tool

ICL/ICO 图片解压与打包工具，支持 JXAG 格式，与 C 提取器完全互通。

## 功能

- **解压提取**：ICL / ICO → BMP / JPG / PNG
- **ICO 打包**：图片 → JXAG 格式 ICO（LZO 压缩 RGB565）
- **ICL 转 ICO**：ICL → BMP → ICO（全程不产生 JPG）
- **GUI 界面**：tkinter 图形界面

## 环境要求

- Python 3.7+（32位）
- Pillow、numpy

```bash
pip install pillow numpy
```

## 使用方法

### GUI 界面

```bash
python icl_tool.py
```

### 命令行

```bash
# 解压 ICL/ICO
python extract.py --format bmp file.icl
python extract.py --format jpg file.ico

# ICL 转 ICO
python icl_to_ico.py input.icl -o output.ico
```

## 文件格式

### JXAG ICO（C 提取器唯一支持格式）

```
文件头(16B): JXAG + 版本 + 校验 + 图片数
地址表: 每项 4 字节小端
每图信息头(16B): JXAG + 压缩标志 + 宽高 + 数据长度
像素数据: LZO 压缩的 RGB565 (top-down, LE)
```

### ICL

```
文件头: GUS_3 + 图片数(大端)
地址表: 每项 4 字节大端
每图信息头(10B) + 内嵌 JPG
```

## 与 C 工具互通

| 格式 | 支持状态 |
|------|----------|
| JXAG | ✅ 100% 像素匹配 |
| JXFIL | ❌ 不支持（已屏蔽） |

## 目录结构

```
icl_tool/
├── icl_tool.py        # GUI 主程序
├── icl_core.py        # ICL 解析 + JPG 解码
├── ico_core.py        # JXAG ICO 打包
├── extract.py         # 统一解压
├── icl_to_ico.py      # ICL → ICO 转换
├── tjpgd.dll          # JPG 解码库
├── lzo.dll            # LZO 压缩库
└── DEVELOPMENT_DOC.md # 开发文档
```

## 开发文档

详见 [DEVELOPMENT_DOC.md](DEVELOPMENT_DOC.md)
