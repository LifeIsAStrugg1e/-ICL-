"""通用提取接口"""
import os

from ..icl import is_icl, parse_icl, decode_jpg
from ..ico import is_ico, extract_ico


def detect(data):
    """检测文件格式: 'icl' | 'ico' | None"""
    if is_icl(data):
        return 'icl'
    if is_ico(data):
        return 'ico'
    return None


def extract(path, out_dir, fmt='raw', quality=95):
    """从 ICL/ICO 提取图片

    fmt: 'raw'（保留原始格式）| 'jpg' | 'bmp' | 'png'
    返回 (count, format_detected)
    """
    with open(path, 'rb') as f:
        data = f.read()

    file_fmt = detect(data)
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
    seq = 0

    from PIL import Image

    for img in images:
        raw = img['data']

        if fmt == 'raw':
            if raw[:2] == b'\xff\xd8':
                ext = 'jpg'
            elif raw[:8] == b'\x89PNG\r\n\x1a\n':
                ext = 'png'
            elif raw[:2] == b'BM':
                ext = 'bmp'
            else:
                ext = 'bin'
            outfile = os.path.join(out_dir, "%d.%s" % (seq, ext))
            with open(outfile, 'wb') as f:
                f.write(raw)
            saved += 1
            seq += 1
        else:
            # decode then re-encode
            import io
            if raw[:2] == b'\xff\xd8':
                result = decode_jpg(raw)
                if result is None:
                    continue
                w, h, rgb = result
                pil = Image.frombytes('RGB', (w, h), rgb)
            elif raw[:8] == b'\x89PNG\r\n\x1a\n' or raw[:2] == b'BM':
                pil = Image.open(io.BytesIO(raw))
                pil.load()
            else:
                continue

            outfile = os.path.join(out_dir, "%d.%s" % (seq, fmt))
            if fmt == 'jpg':
                pil.save(outfile, 'JPEG', quality=quality)
            elif fmt == 'bmp':
                pil.save(outfile, 'BMP')
            elif fmt == 'png':
                pil.save(outfile, 'PNG')
            else:
                pil.save(outfile)
            saved += 1
            seq += 1

    return saved, file_fmt
