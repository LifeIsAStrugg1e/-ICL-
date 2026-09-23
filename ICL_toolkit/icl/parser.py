"""ICL 文件解析"""
import struct

ICL_ICONS_MAX = 65536


def is_icl(data):
    """检测是否为 ICL (GUS_3) 格式"""
    if len(data) < 16:
        return False
    return (data[1] == ord('G') and data[2] == ord('U') and
            data[3] == ord('S') and data[4] == ord('_') and
            data[5] == ord('3') and data[0x0C] == 0x04)


def _trim_eoi(jpg):
    """裁剪到 JPEG EOI 标记"""
    for i in range(len(jpg) - 2, -1, -1):
        if jpg[i] == 0xFF and jpg[i + 1] == 0xD9:
            return jpg[:i + 2]
    return jpg


def parse_icl(data):
    """解析 ICL 文件 -> list of {index, width, height, jpg: bytes}"""
    if not is_icl(data):
        raise ValueError("not a valid ICL file (GUS_3)")

    filesize = len(data)
    count = struct.unpack('>H', data[0x0D:0x0F])[0]

    max_idx = -1
    for i in range(min(count, ICL_ICONS_MAX)):
        off = 0x10 + i * 4
        if off + 4 > filesize:
            break
        addr = struct.unpack('>I', data[off:off + 4])[0]
        if addr == 0:
            continue
        if addr >= filesize:
            break
        max_idx = i

    if max_idx < 0:
        return []

    images = []
    for i in range(max_idx + 1):
        off = 0x10 + i * 4
        addr = struct.unpack('>I', data[off:off + 4])[0]
        if addr == 0 or addr + 10 > filesize:
            continue

        w = struct.unpack('>H', data[addr:addr + 2])[0]
        h = struct.unpack('>H', data[addr + 2:addr + 4])[0]
        len_low = struct.unpack('>H', data[addr + 4:addr + 6])[0]
        len_high = struct.unpack('>I', data[addr + 6:addr + 10])[0]
        length = len_low + len_high

        if length == 0 or addr + 10 + length > filesize:
            continue

        jpg = _trim_eoi(data[addr + 10:addr + 10 + length])
        images.append({'index': i, 'width': w, 'height': h, 'jpg': jpg})

    return images
