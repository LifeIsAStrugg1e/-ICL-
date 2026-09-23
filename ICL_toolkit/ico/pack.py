"""JXAG ICO 打包"""
import struct

from ..lzo import compress as lzo_compress
from ..bmp import load_image, bmp_to_rgb565


def pack_ico(images, out_path):
    """打包 JXAG ICO 文件（LZO 压缩 RGB565）

    images: list of {index, jpg/bmp/data: bytes}
    返回打包的图片数量
    """
    if not images:
        raise ValueError("no images to pack")

    count = len(images)
    header_size = 16 + count * 4
    header_size = (header_size + 15) // 16 * 16

    addrs = [0] * count
    data_blobs = []
    offset = header_size

    for i, img in enumerate(sorted(images, key=lambda x: x['index'])):
        raw = img.get('jpg') or img.get('bmp') or img.get('data')
        pil = load_image(raw)
        w, h, rgb565 = bmp_to_rgb565(pil.tobytes() if False else _pil_to_bmp(pil))

        compressed = lzo_compress(rgb565)

        # 16-byte info header
        info = b'JXAG'
        info += bytes([0x01, 0x00, 0x00, 0x10])
        info += struct.pack('<HH', w, h)
        info += struct.pack('<I', len(compressed))

        blob = info + compressed
        write_size = (len(blob) + 15) // 16 * 16
        blob = blob.ljust(write_size, b'\x00')

        addrs[i] = offset
        data_blobs.append(blob)
        offset += write_size

    with open(out_path, 'wb') as f:
        f.write(b'JXAG')
        f.write(b'\x01\x00')
        f.write(b'\xf3\x9c\x9f\x4e')
        f.write(b'\xc3\x00')
        f.write(struct.pack('<H', count))
        f.write(b'\x00\x00')

        for a in addrs:
            f.write(struct.pack('<I', a))

        written = 16 + count * 4
        if written < header_size:
            f.write(b'\x00' * (header_size - written))

        for blob in data_blobs:
            f.write(blob)

    return count


def _pil_to_bmp(pil):
    """PIL Image -> BMP bytes"""
    import io
    pil = pil.convert('RGB')
    buf = io.BytesIO()
    pil.save(buf, 'BMP')
    return buf.getvalue()
