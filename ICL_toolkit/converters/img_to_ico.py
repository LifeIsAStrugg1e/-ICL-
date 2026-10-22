"""图片文件 -> ICO 转换"""
import os

from ..ico import pack_ico

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp')


def images_to_ico(image_paths, out_path, fmt='rgb565', quality=90,
                  batch_size=20, rotation=0):
    """多个图片文件 -> JXAG ICO（懒加载，逐批读取）

    image_paths: 图片路径列表（jpg/png/bmp）
    fmt: 'rgb565'/'rgb24'/'jpg'
    quality: JPG压缩率 (10-99)
    batch_size: 每批处理图片数
    rotation: 0/90/180/270 度，顺时针旋转
    返回打包数量
    """
    if not image_paths:
        raise ValueError("no image files")

    images = [{'index': i, 'path': p} for i, p in enumerate(image_paths)]
    return pack_ico(images, out_path, fmt=fmt, quality=quality,
                    batch_size=batch_size, rotation=rotation)


def folder_to_ico(folder, out_path, fmt='rgb565', quality=90,
                  batch_size=20, rotation=0):
    """文件夹内所有图片 -> JXAG ICO（按文件名排序，懒加载）"""
    paths = []
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(IMAGE_EXTS):
            paths.append(os.path.join(folder, name))

    if not paths:
        raise ValueError("no image files in folder: %s" % folder)

    return images_to_ico(paths, out_path, fmt=fmt, quality=quality,
                         batch_size=batch_size, rotation=rotation)
