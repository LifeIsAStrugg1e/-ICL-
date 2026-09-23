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
| 0x0C | 2 | 图片数（小端） |
| 0x0E | 2 | 保留 |

**地址表：** 从 0x10 开始，每项 4 字节小端。

**每图信息头（16字节）：**

| 偏移 | 长度 | 说明 |
|------|------|------|
| 0x00 | 4 | 魔数 `JXAG` |
| 0x04 | 1 | 压缩标志（1=LZO） |
| 0x05 | 2 | 保留 |
| 0x07 | 1 | 0x10 |
| 0x08 | 2 | 宽度（小端） |
| 0x0A | 2 | 高度（小端） |
| 0x0C | 4 | 压缩后长度（小端） |

**像素数据：** LZO 压缩的 RGB565（top-down、小端）。

## 关键实现

### RGB565 编码（ico_core.py）

```python
r = (R >> 3) << 11
g = (G >> 2) << 5
b = B >> 3
rgb565 = r | g | b  # 存储为 little-endian，top-down 行序
```

C 工具 `vram_to_bmp` 读取方式：
- 端序：`(data[offset+1]<<8) | data[offset+0]`（LE）
- 行序：`offset = ((h-1-i)*width + j)<<1` → 数据为 top-down

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
输入文件 → 格式检测 → 解析 → 解码 → 保存 BMP/JPG/PNG
```

### 打包（图片 → JXAG ICO）

```
图片 → RGB565 转换 → LZO 压缩 → 写入 JXAG 格式
```

### ICL → ICO 转换

```
ICL → 内存解码 JPG → BMP 文件（落盘）→ RGB565 + LZO → JXAG ICO
```

全程不产生 JPG 文件。

## 与 C 工具互通

C 提取器 `ICL&ICO文件提取器 V1.2.exe` 实测：

- ✅ JXAG 格式：18/18 张解压成功，100% 像素匹配
- ❌ JXFIL 格式：不支持（走进 else 分支产生乱码）

**结论：只使用 JXAG 格式。**

## 历史问题记录

1. **JXFIL 格式不工作**：C 工具虽有 JXFIL 分支代码，但实际不走该分支
2. **RGB565 行序**：必须 top-down，否则像素上下翻转
3. **RGB565 端序**：必须 little-endian，C 工具直接读取不做转换
4. **count 字段**：JXAG 格式图片数在 0x0C 偏移（小端）

## 开发命令

```bash
# 解压 ICL/ICO
python extract.py --format bmp file.icl

# 打包 ICO
python icl_to_ico.py input.icl -o output.ico

# 启动 GUI
python icl_tool.py
```
