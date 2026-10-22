"""JXAG ICO 解压提取"""
import struct

from ..lzo import decompress as lzo_decompress
from ..bmp import rgb565_to_bmp


def is_ico(data):
    """检测是否为 JXAG ICO 格式"""
    if len(data) < 4:
        return False
    return data[0:4] == b'JXAG'


def extract_ico(data):
    """解压 JXAG ICO -> list of {index, width, height, data}"""
    if not is_ico(data):
        raise ValueError("not a valid JXAG ICO file")

    filesize = len(data)
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

        img = _extract_image(data, addr, filesize, i)
        if img is not None:
            images.append(img)

    return images


def _extract_image(data, addr, filesize, index):
    """解压单张图片（JXAG 16字节信息头）

    支持格式:
      - flag=1, byte[7]=0x10: LZO RGB565 (C工具兼容)
      - flag=1, byte[7]=0x20: LZO BGRA32 (工具箱格式)
      - flag=2:               JPG/PNG/BMP payload (magic检测)
      - 其他:                 未压缩 RGB565 或 BGRA32

    输出: 24位 BMP (丢弃 Alpha，与工具箱行为一致)
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

    # JPEG/PNG/BMP payload
    if (payload[:2] == b'\xff\xd8' or payload[:8] == b'\x89PNG\r\n\x1a\n'
            or payload[:2] == b'BM'):
        return {'index': index, 'width': w, 'height': h, 'data': payload,
                'type': typ, 'fmt': 'JXAG_encoded'}

    # LZO compressed (flag=1)
    if typ == 1:
        import io
        from PIL import Image
        if byte7 == 0x20:  # BGRA32
            import numpy as np
            bgra = lzo_decompress(payload, w * h * 4)
            # BGRA -> RGB (drop alpha, 24-bit BMP)
            arr = np.frombuffer(bgra, dtype=np.uint8).reshape(h, w, 4)
            rgb = arr[:, :, [2, 1, 0]]  # BGR -> RGB
            pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
            buf = io.BytesIO()
            pil.save(buf, 'BMP')
            return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                    'type': typ, 'fmt': 'JXAG_LZO32'}
        else:  # RGB565
            rgb565 = lzo_decompress(payload, w * h * 2)
            bmp = rgb565_to_bmp(rgb565, w, h)
            return {'index': index, 'width': w, 'height': h, 'data': bmp,
                    'type': typ, 'fmt': 'JXAG_LZO'}

    # LZO compressed RGB24 (flag=2, non-standard)
    elif typ == 2:
        import io
        from PIL import Image
        rgb24 = lzo_decompress(payload, w * h * 3)
        pil = Image.frombytes('RGB', (w, h), rgb24)
        buf = io.BytesIO()
        pil.save(buf, 'BMP')
        return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                'type': typ, 'fmt': 'JXAG_LZO24'}

    else:
        import io
        from PIL import Image
        # uncompressed RGB565
        if length == w * h * 2:
            bmp = rgb565_to_bmp(payload, w, h)
            return {'index': index, 'width': w, 'height': h, 'data': bmp,
                    'type': typ, 'fmt': 'JXAG_raw565'}
        # uncompressed BGRA32
        if length == w * h * 4:
            import numpy as np
            arr = np.frombuffer(payload, dtype=np.uint8).reshape(h, w, 4)
            rgb = arr[:, :, [2, 1, 0]]  # BGR -> RGB
            pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
            buf = io.BytesIO()
            pil.save(buf, 'BMP')
            return {'index': index, 'width': w, 'height': h, 'data': buf.getvalue(),
                    'type': typ, 'fmt': 'JXAG_raw32'}

    return None
