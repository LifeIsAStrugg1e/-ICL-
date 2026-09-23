"""RGB565 <-> BMP 转换"""
import io


def rgb565_to_bmp(rgb565, w, h, big_endian=False):
    """RGB565 bytes -> BMP file bytes

    数据为 top-down（row 0 = 顶部），默认小端。
    """
    import numpy as np
    from PIL import Image

    dtype = '>u2' if big_endian else '<u2'
    arr = np.frombuffer(rgb565, dtype=dtype)
    r = ((arr >> 11) & 0x1F) << 3
    g = ((arr >> 5) & 0x3F) << 2
    b = (arr & 0x1F) << 3
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    rgb = rgb.reshape(h, w, 3)
    pil = Image.frombytes('RGB', (w, h), rgb.tobytes())
    buf = io.BytesIO()
    pil.save(buf, 'BMP')
    return buf.getvalue()


def bmp_to_rgb565(bmp_bytes):
    """BMP/JPG/PNG bytes -> (width, height, RGB565 bytes top-down LE)"""
    import numpy as np
    from PIL import Image

    pil = Image.open(io.BytesIO(bmp_bytes))
    pil.load()
    pil = pil.convert('RGB')
    w, h = pil.size
    arr = np.frombuffer(pil.tobytes(), dtype=np.uint8).reshape(h, w, 3)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return w, h, rgb565.astype('<u2').tobytes()


def load_image(raw):
    """JPG/PNG/BMP bytes -> PIL Image"""
    from PIL import Image

    if raw[:2] == b'\xff\xd8':
        from ..icl.decoder import decode_jpg
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
