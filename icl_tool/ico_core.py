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


def pack_ico(images, out_path, fmt='rgb565', quality=90, batch_size=20, rotation=0):
    """Pack images into JXAG ICO file.

    Args:
        images:    list of dicts. Each must have 'index' and one of:
                   'path' (lazy-loaded per batch) OR 'jpg'/'bmp'/'data' (raw bytes)
        out_path:  output ICO file path
        fmt:       'rgb565' = 16-bit LZO (flag=1, byte[7]=0x10, C tool compatible)
                   'rgb24'  = BGRA32 LZO lossless (flag=1, byte[7]=0x20, NOT C tool compatible)
                   'jpg'    = JPG payload (flag=2, byte[7]=0x20, C tool compatible)
                   'jpgpng' = keep original format: PNG input -> PNG payload
                              (flag=3, byte[7]=0x20), others -> JPG (flag=2, quality)
        quality:   JPG quality 10-100 (only used when fmt='jpg', default 90)
        batch_size: images processed in memory at once (default 20, for memory optimization)
        rotation:  0/90/180/270 degrees clockwise, applied before compression

    Returns: number of images packed

    JXAG format (only format supported by C tool):
      - 16-byte header: "JXAG" + version + checksum + count@0x0C(LE)
      - address table @0x10, 4 bytes each LE
      - per-image: 16-byte info header + payload, padded to 16 bytes

    Pixel format reference (download.js source):
      - rgb565: little-endian RGB565, top-down row order
      - rgb24:  BGRA order (B,G,R,A), matching tool's fillPixel()
    """
    if not images:
        raise ValueError("no images to pack")
    if fmt not in ('rgb565', 'rgb24', 'jpg', 'jpgpng'):
        raise ValueError("fmt must be 'rgb565', 'rgb24', 'jpg', or 'jpgpng'")

    sorted_images = sorted(images, key=lambda x: x['index'])
    count = len(sorted_images)
    header_size = 16 + count * 4  # 16-byte header + address table
    header_size = (header_size + 15) // 16 * 16

    addrs = [0] * count

    with open(out_path, 'wb') as f:
        # 16-byte file header
        f.write(b'JXAG')                           # 0-3: magic
        f.write(b'\x01\x00')                       # 4-5: version?
        f.write(b'\xf3\x9c\x9f\x4e')              # 6-9: checksum? (same as working ICO)
        f.write(b'\xc3\x00')                       # 10-11: ?
        f.write(struct.pack('<H', count))          # 12-13: count LE
        f.write(b'\x00\x00')                       # 14-15: pad

        # placeholder for address table
        f.write(b'\x00' * (header_size - 16))

        # process in batches
        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch = sorted_images[batch_start:batch_end]
            offset = f.tell()

            for local_i, img in enumerate(batch):
                i = batch_start + local_i

                # Lazy load from path, or use pre-loaded bytes
                path = img.get('path')
                if path:
                    with open(path, 'rb') as pf:
                        raw = pf.read()
                else:
                    raw = img.get('jpg') or img.get('bmp') or img.get('data')

                pil = _load_pil_image(raw)

                if rotation in (90, 180, 270):
                    pil = pil.rotate(-rotation, expand=True)

                if fmt == 'jpg':
                    # JPG encode (lossy)
                    w, h = pil.size
                    buf = io.BytesIO()
                    pil.convert('RGB').save(buf, 'JPEG', quality=quality)
                    payload = buf.getvalue()
                    compress_flag = 2
                    byte7 = 0x20
                elif fmt == 'jpgpng':
                    # Keep original format (toolbox's jpg/png mode):
                    #   PNG input -> PNG payload (flag=3), others -> JPG (flag=2)
                    w, h = pil.size
                    if raw[:8] == b'\x89PNG\r\n\x1a\n':
                        buf = io.BytesIO()
                        pil.save(buf, 'PNG')
                        payload = buf.getvalue()
                        compress_flag = 3
                    else:
                        buf = io.BytesIO()
                        pil.convert('RGB').save(buf, 'JPEG', quality=quality)
                        payload = buf.getvalue()
                        compress_flag = 2
                    byte7 = 0x20
                elif fmt == 'rgb24':
                    # BGRA32 + LZO (24-bit lossless, byte[7]=32, flag=1)
                    # 工具箱源码: push(B, G, R, A) → BGRA order
                    pil = pil.convert('RGBA')
                    w, h = pil.size
                    rgba = pil.tobytes()
                    # RGBA -> BGRA
                    import numpy as np
                    arr = np.frombuffer(rgba, dtype=np.uint8).reshape(h, w, 4)
                    bgra = np.empty_like(arr)
                    bgra[:, :, 0] = arr[:, :, 2]  # B
                    bgra[:, :, 1] = arr[:, :, 1]  # G
                    bgra[:, :, 2] = arr[:, :, 0]  # R
                    bgra[:, :, 3] = arr[:, :, 3]  # A
                    payload = _lzo_compress(bgra.tobytes())
                    compress_flag = 1
                    byte7 = 0x20  # 32 bits per pixel
                else:  # rgb565 (default)
                    # RGB565 + LZO (lossless storage, C tool compatible)
                    w, h, rgb565 = _image_to_rgb565(pil)
                    payload = _lzo_compress(rgb565)
                    compress_flag = 1
                    byte7 = 0x10  # 16 bits per pixel

                # 16-byte info header
                info = b'JXAG'
                info += bytes([compress_flag, 0x00, 0x00, byte7])
                info += struct.pack('<HH', w, h)
                info += struct.pack('<I', len(payload))

                blob = info + payload
                write_size = (len(blob) + 15) // 16 * 16
                blob = blob.ljust(write_size, b'\x00')

                addrs[i] = offset
                f.write(blob)
                offset += write_size

                # free memory for this image
                del raw, pil, payload, blob
                if fmt == 'rgb565':
                    del rgb565
                elif fmt == 'rgb24':
                    del rgba, arr, bgra

        # seek back and write address table
        f.seek(16)
        for a in addrs:
            f.write(struct.pack('<I', a))

    return count
