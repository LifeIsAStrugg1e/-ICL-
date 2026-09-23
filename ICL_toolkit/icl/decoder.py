"""JPG 解码（基于 tjpgd.dll）"""
import ctypes
import os

_dll = None


def _dll_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        '_dlls', 'tjpgd.dll')


def _load_dll():
    global _dll
    if _dll is None:
        path = _dll_path()
        if not os.path.exists(path):
            raise FileNotFoundError("tjpgd.dll not found: " + path)
        _dll = ctypes.CDLL(path)
        _dll.tjpgd_decode.restype = ctypes.POINTER(ctypes.c_uint16)
        _dll.tjpgd_decode.argtypes = [
            ctypes.c_char_p, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ]
        _dll.tjpgd_free.argtypes = [ctypes.c_void_p]
    return _dll


def decode_jpg(jpg_bytes):
    """解码 JPEG -> (width, height, RGB888 bytes)，失败返回 None"""
    dll = _load_dll()
    w = ctypes.c_uint(0)
    h = ctypes.c_uint(0)
    buf = dll.tjpgd_decode(jpg_bytes, len(jpg_bytes), ctypes.byref(w), ctypes.byref(h))
    if not buf:
        return None
    width, height = w.value, h.value
    n = width * height
    raw = ctypes.string_at(buf, n * 2)
    dll.tjpgd_free(buf)

    import numpy as np
    arr = np.frombuffer(raw, dtype=np.uint16).astype(np.uint32)
    r = ((arr >> 11) & 0x1F) << 3
    g = ((arr >> 5) & 0x3F) << 2
    b = (arr & 0x1F) << 3
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return width, height, rgb.tobytes()
