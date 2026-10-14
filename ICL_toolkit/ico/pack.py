"""JXAG ICO 打包"""
import io
import struct

from ..lzo import compress as lzo_compress
from ..bmp import load_image, bmp_to_rgb565


def pack_ico(images, out_path, lossy=False, quality=85, batch_size=20):
    """打包 JXAG ICO 文件

    images: list of dicts. Each dict must have 'index' and one of:
            'path' (file path, loaded lazily per batch) OR
            'jpg'/'bmp'/'data' (raw bytes)
    lossy=False: LZO RGB565 (flag=1, 无损存储)
    lossy=True:  JPG 编码 (flag=0, quality 控制压缩率)
    batch_size:  每批处理的图片数（控制内存峰值）
    返回打包的图片数量
    """
    if not images:
        raise ValueError("no images to pack")

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

                if lossy:
                    w, h = pil.size
                    buf = io.BytesIO()
                    pil.convert('RGB').save(buf, 'JPEG', quality=quality)
                    payload = buf.getvalue()
                    compress_flag = 0
                else:
                    w, h, rgb565 = bmp_to_rgb565(_pil_to_bmp(pil))
                    payload = lzo_compress(rgb565)
                    compress_flag = 1

                info = b'JXAG'
                info += bytes([compress_flag, 0x00, 0x00, 0x10])
                info += struct.pack('<HH', w, h)
                info += struct.pack('<I', len(payload))

                blob = info + payload
                write_size = (len(blob) + 15) // 16 * 16
                blob = blob.ljust(write_size, b'\x00')

                addrs[i] = offset
                f.write(blob)
                offset += write_size

                del raw, pil, payload, blob
                if not lossy:
                    del rgb565

        f.seek(16)
        for a in addrs:
            f.write(struct.pack('<I', a))

    return count


def _pil_to_bmp(pil):
    """PIL Image -> BMP bytes"""
    pil = pil.convert('RGB')
    buf = io.BytesIO()
    pil.save(buf, 'BMP')
    return buf.getvalue()
