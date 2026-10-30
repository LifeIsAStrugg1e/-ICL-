"""pywebview API 桥接层

前端 JS 调用 pywebview.api.xxx() → 这里执行核心逻辑 → 返回结果
"""
import os
import json
import re
import sys
import threading

# 核心逻辑在 icl_tool 目录（共用）
_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icl_tool")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)

from icl_core import parse_icl, decode_jpg
from ico_core import (pack_ico, _load_pil_image, _image_to_rgb565,
                       _lzo_compress)
from extract import extract_file, detect_format, extract_ico


def _source_image_indexes(paths):
    """保留纯数字图片文件名中的编号，其他名称顺序补齐空闲编号。"""
    indexes = []
    used = set()
    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        index = int(stem) if stem.isdigit() else None
        indexes.append(index)
        if index is not None:
            used.add(index)

    next_index = 0
    for position, index in enumerate(indexes):
        if index is not None:
            continue
        while next_index in used:
            next_index += 1
        indexes[position] = next_index
        used.add(next_index)
    return indexes


def _resolve_conflict(path, policy):
    if not os.path.exists(path) or policy == 'overwrite':
        return path
    if policy == 'skip':
        return None
    root, ext = os.path.splitext(path)
    suffix = 2
    candidate = '%s (%d)%s' % (root, suffix, ext)
    while os.path.exists(candidate):
        suffix += 1
        candidate = '%s (%d)%s' % (root, suffix, ext)
    return candidate


class Api:
    """提供给前端 JS 的 API"""

    def __init__(self):
        self._window = None
        self._running = False
        self._file_info_lock = threading.Lock()
        # 进度状态
        self.progress = 0
        self.status = "就绪"
        self.logs = []

    def set_window(self, window):
        self._window = window

    def get_settings(self):
        """读取当前用户的界面设置。"""
        settings_path = self._settings_path()
        try:
            with open(settings_path, 'r', encoding='utf-8') as settings_file:
                settings = json.load(settings_file)
            font_size = int(settings.get('font_size', 15))
            if font_size < 13 or font_size > 21:
                font_size = 15
            return {'ok': True, 'font_size': font_size}
        except (IOError, ValueError, TypeError):
            return {'ok': True, 'font_size': 15}

    def save_settings(self, settings):
        """保存当前用户的界面设置，不写入程序目录。"""
        try:
            font_size = int(settings.get('font_size', 15))
            if font_size < 13 or font_size > 21:
                return {'ok': False, 'message': '文字大小必须在 13 到 21 之间'}
            settings_path = self._settings_path()
            folder = os.path.dirname(settings_path)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            with open(settings_path, 'w', encoding='utf-8') as settings_file:
                json.dump({'font_size': font_size}, settings_file,
                          ensure_ascii=False, indent=2)
            return {'ok': True, 'font_size': font_size}
        except Exception as e:
            return {'ok': False, 'message': str(e)}

    @staticmethod
    def _settings_path():
        app_data = os.environ.get('APPDATA')
        if not app_data:
            app_data = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
        return os.path.join(app_data, 'ICL_ICO_Tool', 'settings.json')

    def handle_file_drop(self, event):
        paths = [item.get('pywebviewFullPath') for item in
                 event.get('dataTransfer', {}).get('files', [])
                 if item.get('pywebviewFullPath')]
        if self._window and paths:
            import json
            self._window.evaluate_js(
                'window.handleDroppedPaths(%s)' % json.dumps(paths)
            )

    def _log(self, msg):
        """追加日志并推送到前端"""
        self.logs.append(msg)
        if self._window:
            try:
                self._window.evaluate_js(
                    f"window.__onLog && window.__onLog({msg_json(msg)})"
                )
            except Exception:
                pass

    def _progress(self, value):
        """更新进度 0-100"""
        self.progress = value
        if self._window:
            try:
                self._window.evaluate_js(
                    f"window.__onProgress && window.__onProgress({value})"
                )
            except Exception:
                pass

    def _status(self, msg):
        self.status = msg
        if self._window:
            try:
                self._window.evaluate_js(
                    f"window.__onStatus && window.__onStatus({msg_json(msg)})"
                )
            except Exception:
                pass

    # ---- 文件选择 ----

    def select_files(self, mode):
        """打开文件选择对话框

        Args:
            mode: 'extract'/'pack' → ICL/ICO, 'img2ico' → 图片
        Returns: 选中的文件路径列表
        """
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if mode == "img2ico":
                paths = filedialog.askopenfilenames(
                    title="选择图片文件",
                    filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"),
                               ("JPG", "*.jpg *.jpeg"),
                               ("PNG", "*.png"),
                               ("BMP", "*.bmp"),
                               ("All files", "*.*")])
            else:
                paths = filedialog.askopenfilenames(
                    title="选择 ICL / ICO 文件",
                    filetypes=[("图片容器", "*.icl *.ico"),
                               ("ICL files", "*.icl"),
                               ("ICO files", "*.ico"),
                               ("All files", "*.*")])
        finally:
            root.destroy()
        return list(paths)

    def select_folder(self):
        """打开文件夹选择对话框，返回文件夹路径"""
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            p = filedialog.askdirectory(title="选择文件夹")
        finally:
            root.destroy()
        return p or ""

    def get_default_output(self, first_path, mode, batch=False):
        """计算默认输出路径（Python 端归一化，兼容 / 和 \ 混用）

        Args:
            first_path: 第一个输入文件的完整路径
            mode: 'extract' → <目录>/extracted; 其他 → <目录>/<文件名>.ico
        Returns: 归一化后的输出路径
        """
        try:
            input_path = os.path.normpath(first_path)
            d = os.path.normpath(os.path.dirname(input_path))
            if mode == 'extract':
                return os.path.join(d, 'extracted')
            if mode == 'pack' and batch:
                return os.path.join(d, 'packed')
            if mode == 'img2ico':
                folder_name = os.path.basename(d)
                return os.path.join(d, folder_name + '.ico')
            base = os.path.splitext(os.path.basename(first_path))[0]
            return os.path.join(d, base + '.ico')
        except Exception:
            return ""

    def list_files(self, folder, exts):
        """列出文件夹中匹配扩展名的文件

        Args:
            folder: 文件夹路径
            exts: 扩展名列表 ['.icl', '.ico']
        Returns: 完整路径列表
        """
        try:
            exts = [e.lower() for e in exts]
            out = []
            for name in sorted(os.listdir(folder), key=self._natural_sort_key):
                if name.lower().endswith(tuple(exts)):
                    out.append(os.path.join(folder, name))
            return out
        except Exception:
            return []

    @staticmethod
    def _natural_sort_key(name):
        return [int(part) if part.isdigit() else part.casefold()
                for part in re.split(r'(\d+)', name)]

    def select_output(self, mode, batch=False):
        """打开输出路径选择

        Args:
            mode: 'extract' → 文件夹, 其他 → 保存 .ico 文件
        Returns: 路径字符串，取消返回空
        """
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if mode == "extract" or (mode == "pack" and batch):
                p = filedialog.askdirectory(title="选择输出文件夹")
            else:
                p = filedialog.asksaveasfilename(
                    title="保存 ICO 文件",
                    defaultextension=".ico",
                    filetypes=[("ICO files", "*.ico"), ("All files", "*.*")])
        finally:
            root.destroy()
        return p or ""

    # ---- 任务执行 ----

    def run_task(self, mode, input_paths, output_path,
                 output_format, comp_fmt, quality, rotation,
                 conflict_policy='overwrite', preserve_indices=True):
        """启动任务（异步）

        Args:
            mode: 'extract' | 'pack' | 'img2ico'
            input_paths: 输入文件路径列表
            output_path: 输出路径
            output_format: extract 时为 bmp/jpg/png, 其他为 ico
            comp_fmt: rgb565/rgb24/jpg
            quality: JPG 质量 10-100
            rotation: 0/90/180/270

        Returns: dict {ok, message} 立即返回，实际执行在后台线程
        """
        if self._running:
            return {"ok": False, "message": "任务正在运行中"}
        if not input_paths:
            return {"ok": False, "message": "请先添加文件"}
        if not output_path:
            return {"ok": False, "message": "请选择输出路径"}
        if conflict_policy not in ('skip', 'overwrite', 'rename'):
            return {"ok": False, "message": "无效的冲突处理方式"}

        # 自动补 .ico
        batch_pack = mode == 'pack' and len(input_paths) > 1
        if mode in ("pack", "img2ico") and not batch_pack and not output_path.lower().endswith(".ico"):
            output_path += ".ico"

        self._running = True
        self.progress = 0
        self.logs = []
        self._progress(0)
        self._status("运行中...")

        threading.Thread(
            target=self._worker,
            args=(mode, list(input_paths), output_path,
                  output_format, comp_fmt, int(quality), int(rotation),
                  conflict_policy, bool(preserve_indices)),
            daemon=True,
        ).start()

        return {"ok": True, "message": "started", "output_path": output_path}

    def get_state(self):
        """前端轮询获取状态"""
        return {
            "running": self._running,
            "progress": self.progress,
            "status": self.status,
            "logs": self.logs[-100:],  # 最近100条
        }

    # ---- 后台工作 ----

    def _worker(self, mode, paths, out_path, out_fmt, comp_fmt, q, rot,
                conflict_policy, preserve_indices):
        try:
            if mode == "extract":
                result = self._do_extract(paths, out_path, out_fmt,
                                          conflict_policy, preserve_indices)
            elif mode == "img2ico":
                result = self._do_img2ico(paths, out_path, comp_fmt, q, rot,
                                          conflict_policy)
            else:
                result = self._do_pack(paths, out_path, comp_fmt, q, rot,
                                       conflict_policy)
            if result:
                self._status("完成：成功 %d，失败 %d，跳过 %d" % result)
                self._progress(100)
                return
            self._status("完成")
            self._progress(100)
            self._log("任务完成")
        except Exception as e:
            self._status("出错")
            self._log("错误: %s" % e)
        finally:
            self._running = False

    def _do_extract(self, paths, out_dir, fmt, conflict_policy='overwrite',
                    preserve_indices=True):
        """解压提取"""
        quality = 100
        total = len(paths)
        total_images = 0
        failed = 0
        skipped = 0

        for fi, path in enumerate(paths):
            base = os.path.splitext(os.path.basename(path))[0]
            self._log("[%d/%d] %s" % (fi + 1, total, os.path.basename(path)))

            sub_dir = os.path.join(out_dir, base) if total > 1 else out_dir

            def _cb(done, total_img, fname, _fi=fi, _total=total):
                self._log("    提取 %d/%d -> %s" % (done, total_img, fname))
                base_pct = _fi / _total * 100
                pct = base_pct + (done / float(total_img or 1)) / _total * 100
                self._progress(pct)
                self._status("%d%%" % int(pct))

            try:
                def _skip(name):
                    nonlocal skipped
                    skipped += 1
                    self._log("    跳过已存在文件: %s" % name)

                count, file_fmt = extract_file(path, sub_dir,
                                               fmt_out=fmt, quality=quality,
                                               progress_cb=_cb,
                                               preserve_indices=preserve_indices,
                                               conflict_policy=conflict_policy,
                                               skip_cb=_skip)
                self._log("  [%s] 提取 %d 张 -> %s" % (file_fmt, count, sub_dir))
                total_images += count
            except Exception as e:
                self._log("  错误: %s" % e)
                failed += 1

        self._log("完成，共 %d 张图片" % total_images)
        return total_images, failed, skipped

    def _do_pack(self, paths, out_path, fmt, q, rot,
                 conflict_policy='overwrite'):
        """打包 ICL/ICO → JXAG ICO"""
        total = len(paths)
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损',
                   'jpg': 'JPG q=%d' % q, 'jpgpng': 'JPG/PNG原格式 q=%d' % q}[fmt]
        if rot:
            fmt_tag += ", 逆时针旋转%d°" % rot

        if total == 1:
            self._log("[1/1] %s (%s)" % (os.path.basename(paths[0]), fmt_tag))
            images = self._load_images(paths[0])
            if not images:
                self._log("  没有找到图片")
                return
            out_dir = os.path.dirname(out_path)
            out_name = os.path.splitext(os.path.basename(paths[0]))[0] + ".ico"
            ico_path = os.path.join(out_dir, out_name)
            ico_path = _resolve_conflict(ico_path, conflict_policy)
            if ico_path is None:
                self._log("  跳过: 输出文件已存在")
                return 0, 0, 1
            count = pack_ico(images, ico_path, fmt=fmt, quality=q, rotation=-rot)
            self._progress(100)
            self._log("  打包 %d 张 -> %s" % (count, ico_path))
            return count, 0, 0
        else:
            out_dir = out_path
            os.makedirs(out_dir, exist_ok=True)
            succeeded = 0
            failed = 0
            skipped = 0

            for fi, path in enumerate(paths):
                base = os.path.splitext(os.path.basename(path))[0]
                self._log("[%d/%d] %s (%s)" % (fi + 1, total,
                                               os.path.basename(path), fmt_tag))
                try:
                    images = self._load_images(path)
                except Exception as e:
                    self._log("  错误: %s" % e)
                    failed += 1
                    self._progress((fi + 1) / total * 100)
                    continue
                if not images:
                    self._log("  没有找到图片")
                    skipped += 1
                    self._progress((fi + 1) / total * 100)
                    continue

                self._progress((fi + 1) / total * 100)
                ico_path = os.path.join(out_dir, base + ".ico")
                ico_path = _resolve_conflict(ico_path, conflict_policy)
                if ico_path is None:
                    self._log("  跳过: 输出文件已存在 (%s.ico)" % base)
                    skipped += 1
                    continue
                try:
                    count = pack_ico(images, ico_path, fmt=fmt,
                                     quality=q, rotation=-rot)
                    succeeded += 1
                    self._log("  打包 %d 张 -> %s" % (count, ico_path))
                except Exception as e:
                    failed += 1
                    self._log("  错误: %s" % e)

            self._progress(100)
            self._log("批量结果：成功 %d，失败 %d，跳过 %d" %
                      (succeeded, failed, skipped))
            return succeeded, failed, skipped

    def _do_img2ico(self, paths, out_path, fmt, q, rot,
                    conflict_policy='overwrite'):
        """图片 → JXAG ICO（懒加载）"""
        total = len(paths)
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损',
                   'jpg': 'JPG q=%d' % q, 'jpgpng': 'JPG/PNG原格式 q=%d' % q}[fmt]
        if rot:
            fmt_tag += ", 逆时针旋转%d°" % rot

        self._status("打包 %d 张 (%s)..." % (total, fmt_tag))
        requested_path = out_path
        out_path = _resolve_conflict(requested_path, conflict_policy)
        if out_path is None:
            self._log("跳过: 输出文件已存在 (%s)" % os.path.basename(requested_path))
            return 0, 0, 1
        indexes = _source_image_indexes(paths)
        images = [{'index': index, 'path': path}
                  for index, path in zip(indexes, paths)]
        count = pack_ico(images, out_path, fmt=fmt, quality=q, rotation=-rot)
        self._progress(100)
        self._log("打包 %d 张 -> %s [%s]" % (count, out_path, fmt_tag))
        return count, 0, 0

    def _load_images(self, path):
        """加载单个 ICL/ICO 为图片列表"""
        with open(path, 'rb') as f:
            data = f.read()
        file_fmt = detect_format(data)
        if file_fmt == 'icl':
            return parse_icl(data)
        elif file_fmt == 'ico':
            images = extract_ico(data)
            for img in images:
                img['jpg'] = img.pop('data')
            return images
        return []

    def get_numbering_info(self, paths, mode):
        """预检每个输出 ICO 将使用的编号槽位。"""
        try:
            checks = []
            if mode == 'img2ico':
                indexes = _source_image_indexes(paths or [])
                groups = [('输入图片', indexes)]
            else:
                groups = []
                for path in paths or []:
                    images = self._load_images(path)
                    groups.append((os.path.basename(path),
                                   [image['index'] for image in images]))

            for name, indexes in groups:
                counts = {}
                for index in indexes:
                    counts[index] = counts.get(index, 0) + 1
                unique = sorted(counts)
                maximum = unique[-1] if unique else -1
                missing = [index for index in range(maximum + 1)
                           if index not in counts]
                checks.append({
                    'file': name,
                    'indices': unique[:40],
                    'index_count': len(unique),
                    'missing': missing[:100],
                    'missing_count': len(missing),
                    'duplicates': sorted(index for index, count in counts.items()
                                         if count > 1),
                    'invalid': [index for index in unique
                                if index < 0 or index > 0xFFFF],
                })
            return {'ok': True, 'checks': checks}
        except Exception as e:
            return {'ok': False, 'message': str(e)}

    # ---- 预览 ----

    def get_preview(self, path, index, fmt, rotation, quality, max_w=256):
        """获取单张图的 原图/效果图 预览 (base64)

        Args:
            path:     输入文件路径 (ICL/ICO 或图片文件)
            index:    第几张图 (图片压缩模式 = 文件在列表中的序号对应)
            fmt:      rgb565 / rgb24 / jpg / jpgpng
            rotation: 0/90/180/270
            quality:  JPG 质量 10-100

        Returns:
            {ok, origin, preview}  均为 data:image/jpeg;base64,...
        """
        try:
            from PIL import Image
            import io
            import base64

            pil = self._load_preview_source(path, index)
            if pil is None:
                return {"ok": False, "message": "无法加载图片"}

            max_w = max(256, min(int(max_w), 4096))
            origin = self._pil_to_data_url(pil, max_w=max_w)

            # 应用变换: 逆时针旋转 → 格式效果
            work = pil.copy()
            if int(rotation) in (90, 180, 270):
                work = work.rotate(int(rotation), expand=True)
            if fmt == 'jpgpng':
                # 保持原格式: PNG 源无损(不变), 其他按 quality 模拟 JPG
                fmt = 'jpg' if not self._is_png_source(path, index) else 'none'
            work = self._simulate_fmt(work, fmt, int(quality))

            preview = self._pil_to_data_url(work, max_w=max_w)
            return {"ok": True, "origin": origin, "preview": preview}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def get_preview_count(self, path):
        """返回输入文件的图片数量 (预览翻页用)"""
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.bmp'):
                return 1
            return len(self._load_images(path))
        except Exception:
            return 0

    def get_file_info(self, paths, fmt='rgb565', quality=90, rotation=0):
        """Serialize native image processing used by concurrent UI refreshes."""
        with self._file_info_lock:
            return self._calculate_file_info(paths, fmt, quality, rotation)

    def _calculate_file_info(self, paths, fmt, quality, rotation):
        """按实际编码流程计算输入信息和 ICO 大小。"""
        try:
            import io
            from PIL import Image
            total_images = 0
            source_bytes = 0
            dimensions = []
            output_dimensions = []
            image_sizes = []
            output_indexes = []
            paths = paths or []
            image_indexes = _source_image_indexes(paths)
            for path_position, path in enumerate(paths):
                source_bytes += os.path.getsize(path)
                ext = os.path.splitext(path)[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.bmp'):
                    with open(path, 'rb') as source_file:
                        image_sources = [source_file.read()]
                    source_indexes = [image_indexes[path_position]]
                else:
                    loaded_images = self._load_images(path)
                    image_sources = [image.get('jpg') or image.get('data')
                                     for image in loaded_images]
                    source_indexes = [image['index'] for image in loaded_images]

                for raw, source_index in zip(image_sources, source_indexes):
                    if not raw:
                        continue
                    output_indexes.append(source_index)
                    pil = _load_pil_image(raw)
                    dimensions.append(pil.size)
                    if int(rotation) in (90, 180, 270):
                        pil = pil.rotate(int(rotation), expand=True)
                    width, height = pil.size
                    output_dimensions.append((width, height))

                    if fmt == 'rgb565':
                        _, _, encoded = _image_to_rgb565(pil)
                        payload = _lzo_compress(encoded)
                    elif fmt == 'rgb24':
                        pil = pil.convert('RGBA')
                        rgba = pil.tobytes()
                        import numpy as np
                        arr = np.frombuffer(rgba, dtype=np.uint8).reshape(height, width, 4)
                        bgra = np.empty_like(arr)
                        bgra[:, :, 0] = arr[:, :, 2]
                        bgra[:, :, 1] = arr[:, :, 1]
                        bgra[:, :, 2] = arr[:, :, 0]
                        bgra[:, :, 3] = arr[:, :, 3]
                        payload = _lzo_compress(bgra.tobytes())
                    elif fmt == 'jpg':
                        buffer = io.BytesIO()
                        pil.convert('RGB').save(buffer, 'JPEG', quality=int(quality))
                        payload = buffer.getvalue()
                    elif fmt == 'jpgpng':
                        buffer = io.BytesIO()
                        if raw[:8] == b'\x89PNG\r\n\x1a\n':
                            pil.save(buffer, 'PNG')
                        else:
                            pil.convert('RGB').save(buffer, 'JPEG', quality=int(quality))
                        payload = buffer.getvalue()
                    else:
                        raise ValueError('unsupported compression format: ' + str(fmt))

                    image_sizes.append(((16 + len(payload) + 15) // 16) * 16)
                    total_images += 1

            if not total_images:
                return {"ok": True, "file_count": len(paths or []),
                        "image_count": 0, "source_bytes": source_bytes,
                        "dimensions": [], "output_dimensions": [],
                        "estimated_bytes": 0}

            table_size = max(output_indexes, default=-1) + 1
            header_bytes = ((16 + table_size * 4 + 15) // 16 * 16)

            unique_dimensions = sorted(set(dimensions))
            unique_output_dimensions = sorted(set(output_dimensions))
            return {
                "ok": True,
                "file_count": len(paths or []),
                "image_count": total_images,
                "source_bytes": source_bytes,
                "dimensions": unique_dimensions[:8],
                "more_dimensions": max(0, len(unique_dimensions) - 8),
                "output_dimensions": unique_output_dimensions[:8],
                "more_output_dimensions": max(0, len(unique_output_dimensions) - 8),
                "estimated_bytes": header_bytes + sum(image_sizes),
                "estimated_exact": True,
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _is_png_source(self, path, index):
        """jpgpng 模式: 判断源是否 PNG (决定预览是否模拟 JPG 有损)"""
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.bmp'):
                return False
            if ext == '.png':
                return True
            images = self._load_images(path)
            if index >= len(images):
                return False
            raw = images[index].get('jpg') or images[index].get('data') or b''
            return raw[:8] == b'\x89PNG\r\n\x1a\n'
        except Exception:
            return False

    def _load_preview_source(self, path, index):
        """加载预览源图 -> PIL Image"""
        from PIL import Image
        import io

        ext = os.path.splitext(path)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.bmp'):
            pil = Image.open(path)
            pil.load()
            return pil

        images = self._load_images(path)
        if index >= len(images):
            return None
        raw = images[index].get('jpg') or images[index].get('data')
        if raw[:2] == b'\xff\xd8':
            result = decode_jpg(raw)
            if result is None:
                return None
            w, h, rgb = result
            return Image.frombytes('RGB', (w, h), rgb)
        elif raw[:2] == b'BM' or raw[:8] == b'\x89PNG\r\n\x1a\n':
            pil = Image.open(io.BytesIO(raw))
            pil.load()
            return pil
        return None

    def _simulate_fmt(self, pil, fmt, quality):
        """模拟压缩格式的视觉效果 (旋转已应用)"""
        import io
        from PIL import Image

        if fmt == 'jpg':
            buf = io.BytesIO()
            pil.convert('RGB').save(buf, 'JPEG', quality=quality)
            buf.seek(0)
            out = Image.open(buf)
            out.load()
            return out
        elif fmt == 'rgb565':
            # 模拟 16bit 量化损失
            import numpy as np
            pil = pil.convert('RGB')
            arr = np.frombuffer(pil.tobytes(), dtype=np.uint8).reshape(
                pil.size[1], pil.size[0], 3)
            r = (arr[:, :, 0] >> 3).astype(np.uint16)
            g = (arr[:, :, 1] >> 2).astype(np.uint16)
            b = (arr[:, :, 2] >> 3).astype(np.uint16)
            v565 = (r << 11) | (g << 5) | b
            r8 = ((v565 >> 11) & 0x1F) << 3
            g8 = ((v565 >> 5) & 0x3F) << 2
            b8 = (v565 & 0x1F) << 3
            out = np.stack([r8, g8, b8], axis=-1).astype(np.uint8)
            return Image.frombytes('RGB', pil.size, out.tobytes())
        # rgb24(BGRA无损) 与原图一致
        return pil

    def _pil_to_data_url(self, pil, max_w=256):
        """PIL → 缩放到 max_w 宽的 jpeg data URL"""
        import io
        import base64
        from PIL import Image

        pil = pil.convert('RGB')
        w, h = pil.size
        if w > max_w:
            nh = int(h * max_w / w)
            resample = getattr(Image, 'LANCZOS', Image.BILINEAR)
            pil = pil.resize((max_w, nh), resample)
        buf = io.BytesIO()
        pil.save(buf, 'JPEG', quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        return "data:image/jpeg;base64," + b64


def msg_json(s):
    """简单 JSON 字符串转义（避免依赖 json 模块做简单场景）"""
    import json
    return json.dumps(s, ensure_ascii=False)
