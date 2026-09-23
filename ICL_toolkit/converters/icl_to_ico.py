"""ICL -> ICO 转换"""
import os

from ..icl import parse_icl, decode_jpg
from ..ico import pack_ico


def icl_to_bmp(icl_path, bmp_dir):
    """ICL -> BMP 文件，返回 BMP 路径列表"""
    with open(icl_path, 'rb') as f:
        data = f.read()

    images = parse_icl(data)
    if not images:
        raise ValueError("ICL 中没有找到图片: %s" % icl_path)

    from PIL import Image

    os.makedirs(bmp_dir, exist_ok=True)
    paths = []
    for seq, img in enumerate(images):
        decoded = decode_jpg(img['jpg'])
        if decoded is None:
            raise ValueError("图片 %d 解码失败" % img['index'])
        w, h, rgb = decoded

        pil = Image.frombytes('RGB', (w, h), rgb)
        path = os.path.join(bmp_dir, "%d.bmp" % seq)
        pil.save(path, 'BMP')
        paths.append(path)

    return paths


def icl_to_ico(icl_path, ico_path, bmp_dir=None, verbose=False):
    """ICL -> ICO 转换，返回 {bmp: N, ico: N, ico_size: N}"""
    if bmp_dir is None:
        bmp_dir = os.path.splitext(ico_path)[0] + "_bmp"

    if verbose:
        print("[1/2] ICL -> BMP: %s" % icl_path)

    bmp_paths = icl_to_bmp(icl_path, bmp_dir)

    if verbose:
        print("  保存 %d 个 BMP -> %s" % (len(bmp_paths), bmp_dir))
        print("[2/2] BMP -> ICO: %s" % ico_path)

    # 读取 BMP 打包
    images = []
    for i, p in enumerate(bmp_paths):
        with open(p, 'rb') as f:
            images.append({'index': i, 'bmp': f.read()})

    count = pack_ico(images, ico_path)
    size = os.path.getsize(ico_path)

    if verbose:
        print("  打包 %d 张 -> %s (%d bytes)" % (count, ico_path, size))

    return {'bmp': len(bmp_paths), 'ico': count, 'ico_size': size}
