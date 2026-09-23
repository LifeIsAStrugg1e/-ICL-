"""LZO 压缩/解压（基于 lzo.dll）"""
import ctypes
import os

_compressor = None
_decompressor = None


def _dll_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        '_dlls', 'lzo.dll')


def _load_dll():
    global _compressor, _decompressor
    if _compressor is None:
        path = _dll_path()
        if not os.path.exists(path):
            raise FileNotFoundError("lzo.dll not found: " + path)
        dll = ctypes.CDLL(path)

        dll.lzo_compress.argtypes = [
            ctypes.c_char_p, ctypes.c_uint, ctypes.c_char_p
        ]
        dll.lzo_compress.restype = ctypes.c_uint

        dll.lzo_decompress.restype = ctypes.c_uint
        dll.lzo_decompress.argtypes = [
            ctypes.c_char_p, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_char_p,
        ]

        _compressor = dll.lzo_compress
        _decompressor = dll.lzo_decompress
    return _compressor, _decompressor


def compress(data):
    """LZO 压缩 -> bytes"""
    comp, _ = _load_dll()
    src = ctypes.create_string_buffer(data, len(data))
    dst_size = len(data) + len(data) // 16 + 64 + 3
    dst = ctypes.create_string_buffer(dst_size)
    out_len = comp(src, len(data), dst)
    if out_len == 0:
        raise RuntimeError("LZO compress failed")
    return dst.raw[:out_len]


def decompress(data, out_size):
    """LZO 解压 -> bytes (长度必须等于 out_size)"""
    _, decomp = _load_dll()
    src = ctypes.create_string_buffer(data, len(data))
    dst = ctypes.create_string_buffer(out_size)
    n = decomp(src, len(data), out_size, dst)
    if n != out_size:
        raise RuntimeError("LZO decompress failed: got %d, expected %d" % (n, out_size))
    return dst.raw[:out_size]
