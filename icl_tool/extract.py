import ctypes
import os
import struct
import sys

from icl_core import parse_icl, decode_jpg, is_icl

_lzo_dll = None


def _load_lzo():
    global _lzo_dll
    if _lzo_dll is None:
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lzo.dll')
        _lzo_dll = ctypes.CDLL(dll_path)
        _lzo_dll.lzo_decompress.restype = ctypes.c_uint
        _lzo_dll.lzo_decompress.argtypes = [
            ctypes.c_char_p, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_char_p,
        ]
    return _lzo_dll


def _rgb565_to_bmp(rgb565, w, h, big_endian=False):
    """Convert raw RGB565 bytes to BMP file bytes (BGR, 24-bit).

    Data is top-down LE (or BE if big_endian), row 0 = top of image.
    PIL Image.frombytes expects top-down data.
    """
    import numpy as np
    from PIL import Image
    dtype = '>u2' if big_endian else '<u2'
    arr = np.frombuffer(rgb565, dtype=dtype)
    r = ((arr >> 11) & 0x1F) << 3
    g = ((arr >> 5) & 0x3F) << 2
    b = (arr & 0x1F) << 3
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    # data is top-down, use directly for PIL
    rgb = rgb.reshape(h, w, 3)
    pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
    import io
    buf = io.BytesIO()
    pil.save(buf, 'BMP')
    return buf.getvalue()


def is_ico_jxag(data):
    """Check JXAG magic (only format supported by C tool)."""
    if len(data) < 4:
        return False
    return data[0:4] == b'JXAG'


def extract_ico(data):
    """Extract images from JXAG ICO file -> list of {index, width, height, data}."""
    if not is_ico_jxag(data):
        raise ValueError("not a valid JXAG ICO file")

    filesize = len(data)

    # JXAG format: 16-byte header, address table at 0x10, LE
    count = (data[0x0D] << 8) | data[0x0C]
    table_off = 0x10

    images = []
    for i in range(count + 1):
        off = table_off + i * 4
        if off + 4 > filesize:
            break
        addr = struct.unpack('<I', data[off:off + 4])[0]
        if addr == 0:
            continue
        if addr >= filesize:
            break

        img = _extract_jxag_image(data, addr, filesize, i)
        if img is not None:
            images.append(img)

    return images


def _extract_jxag_image(data, addr, filesize, index):
    """Extract single image from JXAG 16-byte info header.

    Supported formats:
      - flag=1, byte[7]=0x10: LZO compressed RGB565 (C tool compatible)
      - flag=1, byte[7]=0x20: LZO compressed BGRA32 (tool's format)
      - flag=2:               JPG/PNG/BMP payload (magic bytes detected)
      - flag=0/else:          uncompressed RGB565 or BGRA32

    Output: 24-bit BMP (alpha dropped, matching tool behavior)
    """
    if addr + 16 > filesize:
        return None
    if data[addr:addr + 4] != b'JXAG':
        return None

    typ = struct.unpack('<H', data[addr + 4:addr + 6])[0]
    byte7 = data[addr + 7]
    w = struct.unpack('<H', data[addr + 8:addr + 10])[0]
    h = struct.unpack('<H', data[addr + 10:addr + 12])[0]
    length = struct.unpack('<I', data[addr + 12:addr + 16])[0]

    if not (0 < w <= 16384 and 0 < h <= 16384 and 0 < length):
        return None
    if addr + 16 + length > filesize:
        return None

    payload = data[addr + 16:addr + 16 + length]

    # JPEG/PNG/BMP payload (lossy mode or original encoded)
    if (payload[:2] == b'\xff\xd8' or payload[:8] == b'\x89PNG\r\n\x1a\n'
            or payload[:2] == b'BM'):
        return {'index': index, 'width': w, 'height': h, 'data': payload,
                'type': typ, 'fmt': 'JXAG_encoded'}

    # LZO compressed (flag=1)
    if typ == 1:
        dll = _load_lzo()
        if byte7 == 0x20:  # 32 bits per pixel (BGRA)
            out_size = w * h * 4
            outbuf = ctypes.create_string_buffer(out_size)
            n = dll.lzo_decompress(payload, length, out_size, outbuf)
            if n == out_size:
                from PIL import Image
                import numpy as np
                # BGRA -> RGB (drop alpha, 24-bit BMP)
                arr = np.frombuffer(outbuf.raw, dtype=np.uint8).reshape(h, w, 4)
                rgb = arr[:, :, [2, 1, 0]]  # BGR -> RGB
                pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
                import io as _io
                buf = _io.BytesIO()
                pil.save(buf, 'BMP')
                return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                        'type': typ, 'fmt': 'JXAG_LZO32'}
        else:  # 16 bits per pixel (RGB565)
            out_size = w * h * 2
            outbuf = ctypes.create_string_buffer(out_size)
            n = dll.lzo_decompress(payload, length, out_size, outbuf)
            if n == out_size:
                bmp = _rgb565_to_bmp(outbuf.raw, w, h)
                return {'index': index, 'width': w, 'height': h, 'data': bmp,
                        'type': typ, 'fmt': 'JXAG_LZO'}

    # LZO compressed RGB24 (flag=2, byte[7]=16, NOT standard)
    elif typ == 2:
        out_size = w * h * 3
        dll = _load_lzo()
        outbuf = ctypes.create_string_buffer(out_size)
        n = dll.lzo_decompress(payload, length, out_size, outbuf)
        if n == out_size:
            from PIL import Image
            pil = Image.frombytes('RGB', (w, h), outbuf.raw)
            import io as _io
            buf = _io.BytesIO()
            pil.save(buf, 'BMP')
            return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                    'type': typ, 'fmt': 'JXAG_LZO24'}

    else:
        # uncompressed RGB565
        if length == w * h * 2:
            bmp = _rgb565_to_bmp(payload, w, h)
            return {'index': index, 'width': w, 'height': h, 'data': bmp,
                    'type': typ, 'fmt': 'JXAG_raw565'}
        # uncompressed BGRA32
        if length == w * h * 4:
            from PIL import Image
            import numpy as np
            # BGRA -> RGB (drop alpha, 24-bit BMP)
            arr = np.frombuffer(payload, dtype=np.uint8).reshape(h, w, 4)
            rgb = arr[:, :, [2, 1, 0]]  # BGR -> RGB
            pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
            import io as _io
            buf = _io.BytesIO()
            pil.save(buf, 'BMP')
            return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                    'type': typ, 'fmt': 'JXAG_raw32'}

    return None


def detect_format(data):
    """Detect file format: 'icl', 'ico', or None."""
    if is_icl(data):
        return 'icl'
    if is_ico_jxag(data):
        return 'ico'
    return None


def extract_file(path, out_dir, fmt_out='bmp', quality=95, progress_cb=None,
                 preserve_indices=True, conflict_policy='overwrite',
                 skip_cb=None):
    """Extract images from ICL or ICO file.

    Args:
        path:    input ICL or ICO file
        out_dir: output directory (created if not exists)
        fmt_out: 'bmp'  = 24-bit BMP (default, lossless)
                 'jpg'  = re-encode as JPG (quality 10-100)
                 'png'  = convert to PNG (lossless)
        quality: JPG quality (only used when fmt_out='jpg')
        progress_cb: optional callback(done, total, filename) called
                     after each image is saved

    Returns: (count, format_detected) where format is 'icl' or 'ico'
    """
    with open(path, 'rb') as f:
        data = f.read()

    file_fmt = detect_format(data)
    if file_fmt is None:
        raise ValueError("unknown file format: %s" % path)

    if file_fmt == 'icl':
        images = parse_icl(data)
        for img in images:
            img['data'] = img.pop('jpg')
    else:
        images = extract_ico(data)

    if not images:
        return 0, file_fmt

    os.makedirs(out_dir, exist_ok=True)
    saved = 0
    sequence = 0
    total_count = len(images)

    from PIL import Image

    for img in images:
        idx = img['index']
        raw = img['data']

        # decode source to PIL
        if raw[:2] == b'\xff\xd8':
            result = decode_jpg(raw)
            if result is None:
                print("  [%04d] decode failed" % idx)
                continue
            w, h, rgb = result
            pil = Image.frombytes('RGB', (w, h), rgb)
        elif raw[:8] == b'\x89PNG\r\n\x1a\n':
            import io
            pil = Image.open(io.BytesIO(raw))
            pil.load()
        elif raw[:2] == b'BM':
            import io
            pil = Image.open(io.BytesIO(raw))
            pil.load()
        else:
            print("  [%04d] unknown format, skip" % idx)
            continue

        # save as requested format
        output_index = idx if preserve_indices else sequence
        outfile = os.path.join(out_dir, "%d.%s" % (output_index, fmt_out))
        if os.path.exists(outfile):
            if conflict_policy == 'skip':
                if skip_cb:
                    skip_cb(os.path.basename(outfile))
                sequence += 1
                continue
            if conflict_policy == 'rename':
                base = os.path.splitext(outfile)[0]
                suffix = 2
                while os.path.exists('%s (%d).%s' % (base, suffix, fmt_out)):
                    suffix += 1
                outfile = '%s (%d).%s' % (base, suffix, fmt_out)
        if fmt_out == 'jpg':
            pil.convert('RGB').save(outfile, 'JPEG', quality=quality)
        elif fmt_out == 'png':
            pil.save(outfile, 'PNG')
        else:  # bmp (default)
            pil.save(outfile, 'BMP')
        saved += 1
        sequence += 1

        if progress_cb:
            try:
                progress_cb(saved, total_count, os.path.basename(outfile))
            except Exception:
                pass

    return saved, file_fmt


def main():
    fmt_out = 'bmp'
    quality = 95
    files = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--format' and i + 1 < len(args):
            fmt_out = args[i + 1]
            i += 2
        elif args[i] == '--quality' and i + 1 < len(args):
            quality = int(args[i + 1])
            i += 2
        else:
            files.append(args[i])
            i += 1

    if not files:
        # auto-find in current dir
        for f in sorted(os.listdir('.')):
            if f.lower().endswith(('.icl', '.ico')):
                files.append(f)

    if not files:
        print("usage: python extract.py [--format bmp|jpg|png] [--quality N] file.icl|file.ico ...")
        print("  or put .icl/.ico files in this folder")
        if sys.stdin.isatty():
            input("press enter to exit")
        return

    total = 0
    for path in files:
        out_dir = os.path.join("extracted", os.path.splitext(os.path.basename(path))[0])
        try:
            count, file_fmt = extract_file(path, out_dir, fmt_out=fmt_out, quality=quality)
            print("%s [%s] -> %d images -> %s/" % (os.path.basename(path), file_fmt, count, out_dir))
            total += count
        except Exception as e:
            print("%s: ERROR %s" % (os.path.basename(path), e))

    print("total: %d images" % total)
    if sys.stdin.isatty():
        input("press enter to exit")


if __name__ == "__main__":
    main()
