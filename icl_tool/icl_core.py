import ctypes
import os
import struct

ICL_ICONS_MAX = 65536

_dll = None


def _load_dll():
    global _dll
    if _dll is None:
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tjpgd.dll')
        _dll = ctypes.CDLL(dll_path)
        _dll.tjpgd_decode.restype = ctypes.POINTER(ctypes.c_uint16)
        _dll.tjpgd_decode.argtypes = [
            ctypes.c_char_p, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ]
        _dll.tjpgd_free.argtypes = [ctypes.c_void_p]
    return _dll


def is_icl(data):
    if len(data) < 16:
        return False
    return (data[1] == ord('G') and data[2] == ord('U') and
            data[3] == ord('S') and data[4] == ord('_') and
            data[5] == ord('3') and data[0x0C] == 0x04)


def _trim_eoi(jpg):
    for i in range(len(jpg) - 2, -1, -1):
        if jpg[i] == 0xFF and jpg[i + 1] == 0xD9:
            return jpg[:i + 2]
    return jpg


def decode_jpg(jpg_bytes):
    """Decode JPEG via tjpgd -> (width, height, RGB888 bytes). None on failure."""
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


def parse_icl(data):
    """Parse ICL file -> list of dicts: {index, width, height, jpg: bytes}"""
    if not is_icl(data):
        raise ValueError("not a valid ICL file (GUS_3)")

    filesize = len(data)
    count = struct.unpack('>H', data[0x0D:0x0F])[0]

    max_idx = -1
    for i in range(min(count, ICL_ICONS_MAX)):
        off = 0x10 + i * 4
        if off + 4 > filesize:
            break
        addr = struct.unpack('>I', data[off:off + 4])[0]
        if addr == 0:
            continue
        if addr >= filesize:
            break
        max_idx = i

    if max_idx < 0:
        return []

    images = []
    for i in range(max_idx + 1):
        off = 0x10 + i * 4
        addr = struct.unpack('>I', data[off:off + 4])[0]
        if addr == 0 or addr + 10 > filesize:
            continue

        w = struct.unpack('>H', data[addr:addr + 2])[0]
        h = struct.unpack('>H', data[addr + 2:addr + 4])[0]
        len_low = struct.unpack('>H', data[addr + 4:addr + 6])[0]
        len_high = struct.unpack('>I', data[addr + 6:addr + 10])[0]
        length = len_low + len_high

        if length == 0 or addr + 10 + length > filesize:
            continue

        jpg = _trim_eoi(data[addr + 10:addr + 10 + length])
        images.append({'index': i, 'width': w, 'height': h, 'jpg': jpg})

    return images
