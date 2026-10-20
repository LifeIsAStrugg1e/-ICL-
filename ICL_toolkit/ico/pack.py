"""JXAG ICO 打包"""
import io
import struct

from ..lzo import compress as lzo_compress
from ..bmp import load_image, bmp_to_rgb565


def pack_ico(images, out_path, fmt='rgb565', quality=90, batch_size=20, rotation=0):
    """打包 JXAG ICO 文件

    images: list of dicts. Each dict must have 'index' and one of:
            'path' (file path, loaded lazily per batch) OR
            'jpg'/'bmp'/'data' (raw bytes)
    fmt:    'rgb565' = 16-bit LZO (C工具兼容, flag=1)
            'rgb24'  = 24-bit LZO 无损 (flag=2, 不兼容C工具)
            'jpg'    = 24-bit JPG 有损 (C工具兼容, flag=0)
    quality: JPG 压缩率 10-100 (仅 fmt='jpg' 时生效)
    batch_size: 每批处理的图片数（控制内存峰值）
    rotation: 0/90/180/270 度，压缩前顺时针旋转
    返回打包的图片数量
    """
    if not images:
        raise ValueError("no images to pack")
    if fmt not in ('rgb565', 'rgb24', 'jpg'):
        raise ValueError("fmt must be 'rgb565', 'rgb24', or 'jpg'")

    sorted_images = sorted(images, key=lambda x: x['index'])
    count = len(sorted_images)
    header_size = 16 + count * 4
    header_size = (header_size + 15) // 16 * 16

    addrs = [0] * count

    with open(out_path, 'wb') as f:
        f.write(b'JXAG')
        f.write(b'\x01\x00')
        f.write(b'\xf3\x9c\x9f\x4e')
        f.write(b'\xc3\x00')
        f.write(struct.pack('<H', count))
        f.write(b'\x00\x00')
        f.write(b'\x00' * (header_size - 16))

        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch = sorted_images[batch_start:batch_end]
            offset = f.tell()

            for local_i, img in enumerate(batch):
                i = batch_start + local_i

                path = img.get('path')
                if path:
                    with open(path, 'rb') as pf:
                        raw = pf.read()
                else:
                    raw = img.get('jpg') or img.get('bmp') or img.get('data')

                pil = load_image(raw)

                if rotation in (90, 180, 270):
                    pil = pil.rotate(-rotation, expand=True)

                if fmt == 'jpg':
                    w, h = pil.size
                    buf = io.BytesIO()
                    pil.convert('RGB').save(buf, 'JPEG', quality=quality)
                    payload = buf.getvalue()
                    compress_flag = 2
                    byte7 = 0x20
                elif fmt == 'rgb24':
                    # RGBA32 + LZO (byte[7]=32, flag=1)
                    pil = pil.convert('RGBA')
                    w, h = pil.size
                    rgba32 = pil.tobytes()  # w*h*4 bytes
                    payload = lzo_compress(rgba32)
                    compress_flag = 1
                    byte7 = 0x20
                else:  # rgb565
                    w, h, rgb565 = _pil_to_rgb565(pil)
                    payload = lzo_compress(rgb565)
                    compress_flag = 1
                    byte7 = 0x10

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

                del raw, pil, payload, blob
                if fmt == 'rgb565':
                    del rgb565
                elif fmt == 'rgb24':
                    del rgba32

        f.seek(16)
        for a in addrs:
            f.write(struct.pack('<I', a))

    return count


def _pil_to_rgb565(pil):
    """PIL Image -> (width, height, RGB565 bytes top-down LE)"""
    import numpy as np
    pil = pil.convert('RGB')
    w, h = pil.size
    arr = np.frombuffer(pil.tobytes(), dtype=np.uint8).reshape(h, w, 3)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return w, h, rgb565.astype('<u2').tobytes()
