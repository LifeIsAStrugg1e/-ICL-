"""ICL_toolkit - ICL/ICO 图片处理工具库

支持:
- ICL 解压提取
- JXAG ICO 打包/解压
- ICL -> ICO 转换
- 与 C 提取器完全互通

使用示例:
    from ICL_toolkit import extract, pack_ico, icl_to_ico

    # 解压
    count, fmt = extract("file.icl", "output_dir", fmt="bmp")

    # 打包
    pack_ico([{'index': 0, 'bmp': bmp_bytes}], "output.ico")

    # ICL 转 ICO
    icl_to_ico("input.icl", "output.ico")
"""

__version__ = '1.0.0'

# 统一入口
from .converters import detect, extract, icl_to_bmp, icl_to_ico
from .icl import is_icl, parse_icl, decode_jpg
from .ico import is_ico, pack_ico, extract_ico
from .lzo import compress as lzo_compress, decompress as lzo_decompress
from .bmp import rgb565_to_bmp, bmp_to_rgb565, load_image

__all__ = [
    # 转换器
    'detect', 'extract', 'icl_to_bmp', 'icl_to_ico',
    # ICL
    'is_icl', 'parse_icl', 'decode_jpg',
    # ICO
    'is_ico', 'pack_ico', 'extract_ico',
    # LZO
    'lzo_compress', 'lzo_decompress',
    # BMP/RGB565
    'rgb565_to_bmp', 'bmp_to_rgb565', 'load_image',
]
