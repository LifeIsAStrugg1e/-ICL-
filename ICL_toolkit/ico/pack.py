"""JXAG ICO 打包"""
import io
import struct

from ..lzo import compress as lzo_compress
from ..bmp import load_image, bmp_to_rgb565


def pack_ico(images, out_path, fmt='rgb565', quality=90, batch_size=20, rotation=0):
    """打包 JXAG ICO 文件

    Args:
        images:    list of dicts, each with 'index' and 'path' (lazy) or 'jpg'/'bmp'/'data'
        out_path:  output ICO path
        fmt:       'rgb565' = 16-bit LZO (flag=1, byte[7]=0x10, C工具兼容)
                   'rgb24'  = BGRA32 LZO 无损 (flag=1, byte[7]=0x20, 不兼容C工具)
                   'jpg'    = JPG payload (flag=2, byte[7]=0x20, C工具兼容)
        quality:   JPG 压缩率 10-100 (仅 fmt='jpg', 默认 90)
        batch_size: 每批处理的图片数（控制内存峰值, 默认 20）
        rotation:  0/90/180/270 度，压缩前顺时针旋转

    Returns: 打包的图片数量

    JXAG 像素格式（与工具箱 download.js 一致）:
      - rgb565: little-endian RGB565, top-down
      - rgb24:  BGRA order (B,G,R,A)
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
                    # BGRA32 + LZO (byte[7]=32, flag=1)
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
                    payload = lzo_compress(bgra.tobytes())
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
                    del rgba, arr, bgra

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
