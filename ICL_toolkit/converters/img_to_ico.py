"""图片文件 -> ICO 转换"""
import os

from ..ico import pack_ico

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def images_to_ico(image_paths, out_path):
    """多个图片文件 -> JXAG ICO

    image_paths: 图片路径列表（jpg/png/bmp）
    返回打包数量
    """
    if not image_paths:
        raise ValueError("no image files")

    images = []
    for i, p in enumerate(image_paths):
        with open(p, 'rb') as f:
            images.append({'index': i, 'data': f.read()})

    return pack_ico(images, out_path)


def folder_to_ico(folder, out_path):
    """文件夹内所有图片 -> JXAG ICO（按文件名排序）"""
    paths = []
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(IMAGE_EXTS):
            paths.append(os.path.join(folder, name))

    if not paths:
        raise ValueError("no image files in folder: %s" % folder)

    return images_to_ico(paths, out_path)
