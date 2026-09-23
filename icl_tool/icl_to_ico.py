"""ICL -> BMP -> ICO 转换工具

流程:
  1. ICL 解压 -> BMP 文件（ICL 内部的 JPG 在内存中解码，不落盘）
  2. BMP 文件 -> 打包 ICO（ICO 内存储 BMP 像素数据）

全程不产生 JPG 文件。
"""
import argparse
import os
import sys

from icl_core import parse_icl, decode_jpg
from ico_core import pack_ico


def icl_to_bmp(icl_path, bmp_dir):
    """步骤1: ICL -> BMP 文件。返回保存的 BMP 路径列表。"""
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


def bmp_to_ico(bmp_paths, ico_path):
    """步骤2: BMP 文件 -> 打包 ICO。"""
    files = {}
    for p in bmp_paths:
        name = os.path.splitext(os.path.basename(p))[0]
        if name.isdigit():
            files[int(name)] = p

    if not files:
        raise ValueError("没有 BMP 文件")

    images = []
    for idx in sorted(files.keys()):
        with open(files[idx], 'rb') as f:
            bmp = f.read()
        images.append({'index': idx, 'bmp': bmp})

    return pack_ico(images, ico_path)


def convert(icl_path, bmp_dir=None, ico_path=None, verbose=True):
    """ICL -> BMP -> ICO"""
    if bmp_dir is None and ico_path is None:
        base = os.path.splitext(icl_path)[0]
        bmp_dir = base + "_bmp"
        ico_path = base + ".ico"

    if verbose:
        print("[1/2] ICL -> BMP: %s" % icl_path)

    bmp_paths = icl_to_bmp(icl_path, bmp_dir) if bmp_dir else []

    if verbose and bmp_paths:
        print("  保存 %d 个 BMP -> %s" % (len(bmp_paths), bmp_dir))

    if not ico_path:
        return {'bmp': len(bmp_paths), 'ico': 0}

    if verbose:
        print("[2/2] BMP -> ICO: %s" % ico_path)

    if not bmp_paths:
        tmp_dir = bmp_dir or (os.path.splitext(ico_path)[0] + "_tmp_bmp")
        bmp_paths = icl_to_bmp(icl_path, tmp_dir)

    count = bmp_to_ico(bmp_paths, ico_path)
    size = os.path.getsize(ico_path)

    if verbose:
        print("  打包 %d 张 -> %s (%d bytes)" % (count, ico_path, size))

    return {'bmp': len(bmp_paths), 'ico': count, 'ico_size': size}


def main():
    parser = argparse.ArgumentParser(
        description="ICL -> BMP -> ICO（跳过 JPG，ICO 存 BMP 像素数据）")
    parser.add_argument("input", help="输入 ICL 文件")
    parser.add_argument("-b", "--bmp-dir", help="BMP 输出目录")
    parser.add_argument("-o", "--ico", help="输出 ICO 文件")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print("错误: 文件不存在: %s" % args.input)
        sys.exit(1)

    try:
        result = convert(args.input, bmp_dir=args.bmp_dir,
                         ico_path=args.ico, verbose=not args.quiet)
        if not args.quiet:
            print("完成: BMP=%d, ICO=%d" % (result['bmp'], result['ico']))
    except Exception as e:
        print("错误: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
