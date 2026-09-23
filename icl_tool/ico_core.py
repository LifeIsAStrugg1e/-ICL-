import io
import os
import struct


def get_jpg_size(data):
    if data[:2] != b'\xff\xd8':
        return None
    i = 2
    while i < len(data) - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack('>HH', data[i + 5:i + 9])
            return w, h
        elif marker == 0xD9:
            break
        elif marker == 0xD8 or marker == 0x01 or (0xD0 <= marker <= 0xD7):
            i += 2
        else:
            if i + 4 > len(data):
                break
            seg_len = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + seg_len
    return None


def get_png_size(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    w, h = struct.unpack('>II', data[16:24])
    return w, h


def get_bmp_size(data):
    if data[:2] != b'BM':
        return None
    w, h = struct.unpack('<ii', data[18:26])
    return w, abs(h)


def _load_pil_image(raw):
    """Load jpg/png/bmp bytes -> PIL Image."""
    from PIL import Image
    if raw[:2] == b'\xff\xd8':
        from icl_core import decode_jpg
        result = decode_jpg(raw)
        if result is None:
            raise ValueError("JPG decode failed")
        w, h, rgb = result
        return Image.frombytes('RGB', (w, h), rgb)
    elif raw[:8] == b'\x89PNG\r\n\x1a\n':
        pil = Image.open(io.BytesIO(raw))
        pil.load()
        return pil
    elif raw[:2] == b'BM':
        pil = Image.open(io.BytesIO(raw))
        pil.load()
        return pil
    else:
        raise ValueError("unknown image format")


def _image_to_rgb565(pil):
    """PIL Image -> (width, height, RGB565 bytes top-down little-endian).

    C tool vram_to_bmp reads: color = (data[offset+1]<<8) | data[offset+0] (LE)
    Row access: offset = ((hight-1-i)*width + j)<<1 → data is top-down stored.
    """
    import numpy as np
    pil = pil.convert('RGB')
    w, h = pil.size
    arr = np.frombuffer(pil.tobytes(), dtype=np.uint8).reshape(h, w, 3)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    # top-down (row 0 = top of image), little-endian
    return w, h, rgb565.astype('<u2').tobytes()


def _lzo_compress(data):
    """Compress data using minilzo via lzo.dll.

    DLL exports: lzo_compress(in, in_len, out) -> compressed_len
    """
    import ctypes
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lzo.dll')
    if not os.path.exists(dll_path):
        raise FileNotFoundError("lzo.dll not found: " + dll_path)
    lzo = ctypes.CDLL(dll_path)

    src = ctypes.create_string_buffer(data, len(data))
    # Output buffer: worst case is slightly larger than input
    dst_size = len(data) + len(data) // 16 + 64 + 3
    dst = ctypes.create_string_buffer(dst_size)

    lzo.lzo_compress.argtypes = [
        ctypes.c_char_p, ctypes.c_uint, ctypes.c_char_p
    ]
    lzo.lzo_compress.restype = ctypes.c_uint

    out_len = lzo.lzo_compress(src, len(data), dst)
    if out_len == 0:
        raise RuntimeError("LZO compress failed")
    return dst.raw[:out_len]


def pack_ico(images, out_path):
    """Pack images into JXAG ICO file (LZO-compressed RGB565).

    Format matches C tool ico_recovery_picture JXAG path:
      - 16-byte header: "JXAG" + ... + count at 0x0C (LE)
      - address table at 0x10, 4 bytes each LE
      - per-image: 16-byte info header starting with "JXAG" + LZO RGB565 data
    """
    if not images:
        raise ValueError("no images to pack")

    count = len(images)
    header_size = 16 + count * 4  # 16-byte header + address table
    header_size = (header_size + 15) // 16 * 16

    addrs = [0] * count
    data_blobs = []
    offset = header_size

    for i, img in enumerate(sorted(images, key=lambda x: x['index'])):
        raw = img.get('jpg') or img.get('bmp') or img.get('data')
        pil = _load_pil_image(raw)
        w, h, rgb565 = _image_to_rgb565(pil)
        
        # LZO compress the RGB565 data
        compressed = _lzo_compress(rgb565)
        
        # 16-byte info header:
        #   0-3: "JXAG"
        #   4: compress flag (1 = LZO)
        #   5: 0x00
        #   6: 0x00
        #   7: 0x10 (16 bits? matches working ICO)
        #   8-9: width LE
        #   10-11: height LE
        #   12-15: compressed length LE
        info = b'JXAG'
        info += bytes([0x01, 0x00, 0x00, 0x10])  # compress=1, pad, 0x10
        info += struct.pack('<HH', w, h)
        info += struct.pack('<I', len(compressed))
        assert len(info) == 16

        blob = info + compressed
        write_size = (len(blob) + 15) // 16 * 16
        blob = blob.ljust(write_size, b'\x00')

        addrs[i] = offset
        data_blobs.append(blob)
        offset += write_size

    with open(out_path, 'wb') as f:
        # 16-byte file header
        f.write(b'JXAG')                           # 0-3: magic
        f.write(b'\x01\x00')                       # 4-5: version?
        f.write(b'\xf3\x9c\x9f\x4e')              # 6-9: checksum? (same as working ICO)
        f.write(b'\xc3\x00')                       # 10-11: ?
        f.write(struct.pack('<H', count))          # 12-13: count LE
        f.write(b'\x00\x00')                       # 14-15: pad

        # address table at 0x10
        for a in addrs:
            f.write(struct.pack('<I', a))

        # pad to header_size
        written = 16 + count * 4
        if written < header_size:
            f.write(b'\x00' * (header_size - written))

        # image data
        for blob in data_blobs:
            f.write(blob)

    return count
