# icl_tool 开发文档

## 概述

统一的 Python tkinter GUI 工具，支持 ICL/ICO 解压提取和 JXAG ICO 打包。

## 环境要求

- Python 3.7.9（32位）
- Pillow、numpy
- 32位 `tjpgd.dll`（JPG 解码）、`lzo.dll`（LZO 压缩/解压）

## 目录结构

```
icl_tool/
├── icl_tool.py        # tkinter GUI 主程序
├── icl_core.py        # ICL 解析 + JPG 解码
├── ico_core.py        # JXAG ICO 打包
├── extract.py         # ICL/ICO 统一解压
├── icl_to_ico.py      # ICL → BMP → ICO 转换
├── build.spec         # PyInstaller 打包配置
├── tjpgd.dll          # 32位 JPG 解码库
├── tjpgd_dll.c        # tjpgd DLL 源码
├── lzo.dll            # 32位 LZO 压缩库
└── lzo_dll.c          # lzo DLL 源码
```

## 文件格式

### ICL 格式（GUS_3）

| 偏移 | 长度 | 说明 |
|------|------|------|
| 0x00 | 5 | 魔数 `GUS_3` |
| 0x0C | 1 | 0x04 |
| 0x0D-0x0E | 2 | 图片数（大端） |
| 0x10 | 4×N | 地址表（大端） |
| ... | 10 | 每图信息头 |

ICL 内嵌非标准 JPG，需用 tjpgd 解码。

### JXAG ICO 格式（C 提取器唯一支持格式）

**文件头（16字节）：**

| 偏移 | 长度 | 说明 |
|------|------|------|
| 0x00 | 4 | 魔数 `JXAG` |
| 0x04 | 2 | 版本 `01 00` |
| 0x06 | 4 | 校验 `F3 9C 9F 4E` |
| 0x0A | 2 | `C3 00` |
| 0x0C | 2 | 最大图片编号（小端，图片数 - 1） |
| 0x0E | 2 | 保留 |

**地址表：** 从 0x10 开始，每项 4 字节小端。

**每图信息头（16字节）：**

| 偏移 | 长度 | 说明 |
|------|------|------|
| 0x00 | 4 | 魔数 `JXAG` |
| 0x04 | 1 | 压缩标志 flag |
| 0x05 | 2 | 保留 |
| 0x07 | 1 | 位深（0x10=16位，0x20=32位） |
| 0x08 | 2 | 宽度（小端） |
| 0x0A | 2 | 高度（小端） |
| 0x0C | 4 | 压缩后长度（小端） |

### 三种压缩格式

| 格式 | flag | byte[7] | 数据 | 压缩 | C工具兼容 |
|------|------|---------|------|------|-----------|
| `rgb565` | 1 | 0x10 | RGB565 (16bpp) | LZO | ✅ |
| `rgb24` | 1 | 0x20 | BGRA32 (32bpp) | LZO | ❌ |
| `jpg` | 2 | 0x20 | JPG payload | 无 | ✅ |

**像素格式说明：**
- `rgb24`：存储为 **BGRA** 顺序（B,G,R,A），与工具箱 `download.js` 一致
- 解压输出：丢弃 Alpha，生成 **24位 BMP**（Windows 属性显示"24位"）

## 关键实现

### RGB565 编码（ico_core.py）

```python
r = (R >> 3) << 11
g = (G >> 2) << 5
b = B >> 3
rgb565 = r | g | b  # 存储为 little-endian，top-down 行序
```

### BGRA 转换（ico_core.py）

```python
# 工具箱源码 fillPixel: push(B, G, R, A) → BGRA order
bgra[:, :, 0] = rgba[:, :, 2]  # B
bgra[:, :, 1] = rgba[:, :, 1]  # G
bgra[:, :, 2] = rgba[:, :, 0]  # R
bgra[:, :, 3] = rgba[:, :, 3]  # A
```

### 24位 BMP 输出（extract.py）

```python
# 解压 BGRA 后丢弃 Alpha，输出 24位 BMP
rgb = bgra[:, :, [2, 1, 0]]  # BGR → RGB
pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
```

### LZO 压缩（lzo.dll）

```c
// 导出函数
unsigned int lzo_compress(const unsigned char *in, unsigned int in_len, unsigned char *out);
unsigned int lzo_decompress(const unsigned char *in, unsigned int in_len, 
                           unsigned int out_len, unsigned char *out);
```

### JPG 解码（tjpgd.dll）

调用 tjpgd 库解码 ICL 内嵌的非标准 JPG。

## 工作流程

### 解压（ICL/ICO → 图片）

```
输入文件 → 格式检测 → 解析 → 解码 → 保存 BMP(24位)/JPG/PNG
```

### 打包（图片 → JXAG ICO）

```
图片 → 格式转换 → [LZO压缩] → 写入 JXAG 格式
  ├─ rgb565: RGB565 → LZO
  ├─ rgb24:  BGRA32 → LZO
  └─ jpg:    JPG encode（无LZO）
```

### ICL → ICO 转换

```
ICL → 内存解码 JPG → RGB565 + LZO → JXAG ICO
```

全程不产生 JPG 文件。

## 与 C 工具互通

C 提取器 `ICL&ICO文件提取器 V1.2.exe` 实测：

| 格式 | C工具解压 | 说明 |
|------|-----------|------|
| rgb565 | ✅ | 18/18 张，100% 像素匹配 |
| jpg | ✅ | 3/3 张解压成功 |
| rgb24 | ❌ | C工具不支持32位 |

## 与工具箱互通（download.js）

工具箱源码分析（`源代码/download.js`）：

- **像素序**：`push(B, G, R, A)` → BGRA
- **解压输出**：只取前3字节 → 24位 BMP
- **JPG flag**：2，byte[7]=32，quality 默认 90

## 历史问题记录

1. **JXFIL 格式不工作**：C 工具虽有 JXFIL 分支代码，但实际不走该分支
2. **RGB565 行序**：必须 top-down，否则像素上下翻转
3. **RGB565 端序**：必须 little-endian，C 工具直接读取不做转换
4. **编号上限字段**：JXAG 在 0x0C 偏移写入最大图片编号；稀疏编号必须保留原地址槽位，地址表长度为最大编号 + 1。连续编号时最大编号才等于图片数 - 1。
5. **BGRA vs RGBA**：必须 BGRA，否则蓝/红互换（曾导致蓝色变橘红色）
6. **BMP 位深**：解压输出必须 24位（丢弃 Alpha），与工具箱一致

## 开发命令

```bash
# 解压 ICL/ICO
python extract.py --format bmp file.icl

# 打包 ICO（RGB565）
python icl_to_ico.py input.icl -o output.ico

# 打包 ICO（BGRA无损）
python icl_to_ico.py input.icl -o output.ico --fmt rgb24

# 打包 ICO（JPG有损，质量90）
python icl_to_ico.py input.icl -o output.ico --fmt jpg --quality 90

# 启动 GUI
python icl_tool.py

# 打包 exe
pyinstaller build.spec --noconfirm
```

## ICL_toolkit 库

独立可复用库，位于 `../ICL_toolkit/`：

```python
from ICL_toolkit import pack_ico, extract, images_to_ico, icl_to_ico

# 打包
pack_ico(images, 'out.ico', fmt='rgb565', quality=90, rotation=0)

# 解压
count, fmt = extract('in.ico', 'output_dir', fmt='bmp')

# 图片 → ICO
images_to_ico(['a.png', 'b.jpg'], 'out.ico', fmt='jpg')

# ICL → ICO
icl_to_ico('input.icl', 'out.ico', fmt='rgb565')
```
