"""pywebview API 桥接层

前端 JS 调用 pywebview.api.xxx() → 这里执行核心逻辑 → 返回结果
"""
import os
import sys
import threading

# 核心逻辑在 icl_tool 目录（共用）
_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icl_tool")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)

from icl_core import parse_icl, decode_jpg
from ico_core import pack_ico
from extract import extract_file, detect_format, extract_ico


class Api:
    """提供给前端 JS 的 API"""

    def __init__(self):
        self._window = None
        self._running = False
        # 进度状态
        self.progress = 0
        self.status = "就绪"
        self.logs = []

    def set_window(self, window):
        self._window = window

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
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith(tuple(exts)):
                    out.append(os.path.join(folder, name))
            return out
        except Exception:
            return []

    def select_output(self, mode):
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
            if mode == "extract":
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
                 output_format, comp_fmt, quality, rotation):
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

        # 自动补 .ico
        if mode in ("pack", "img2ico") and not output_path.lower().endswith(".ico"):
            output_path += ".ico"

        self._running = True
        self.progress = 0
        self.logs = []
        self._progress(0)
        self._status("运行中...")

        threading.Thread(
            target=self._worker,
            args=(mode, list(input_paths), output_path,
                  output_format, comp_fmt, int(quality), int(rotation)),
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

    def _worker(self, mode, paths, out_path, out_fmt, comp_fmt, q, rot):
        try:
            if mode == "extract":
                self._do_extract(paths, out_path, out_fmt)
            elif mode == "img2ico":
                self._do_img2ico(paths, out_path, comp_fmt, q, rot)
            else:
                self._do_pack(paths, out_path, comp_fmt, q, rot)
            self._status("完成")
            self._progress(100)
            self._log("任务完成")
        except Exception as e:
            self._status("出错")
            self._log("错误: %s" % e)
        finally:
            self._running = False

    def _do_extract(self, paths, out_dir, fmt):
        """解压提取"""
        quality = 100
        total = len(paths)
        total_images = 0

        for fi, path in enumerate(paths):
            base = os.path.splitext(os.path.basename(path))[0]
            self._log("[%d/%d] %s" % (fi + 1, total, os.path.basename(path)))

            sub_dir = os.path.join(out_dir, base) if total > 1 else out_dir
            try:
                count, file_fmt = extract_file(path, sub_dir,
                                               fmt_out=fmt, quality=quality)
                self._log("  [%s] 提取 %d 张 -> %s" % (file_fmt, count, sub_dir))
                total_images += count
            except Exception as e:
                self._log("  错误: %s" % e)

            self._progress((fi + 1) / total * 100)
            self._status("%d%%" % int((fi + 1) / total * 100))

        self._log("完成，共 %d 张图片" % total_images)

    def _do_pack(self, paths, out_path, fmt, q, rot):
        """打包 ICL/ICO → JXAG ICO"""
        total = len(paths)
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损',
                   'jpg': 'JPG q=%d' % q}[fmt]
        if rot:
            fmt_tag += ", 旋转%d°" % rot

        if total == 1:
            self._log("[1/1] %s (%s)" % (os.path.basename(paths[0]), fmt_tag))
            images = self._load_images(paths[0])
            if not images:
                self._log("  没有找到图片")
                return
            count = pack_ico(images, out_path, fmt=fmt, quality=q, rotation=rot)
            self._progress(100)
            self._log("  打包 %d 张 -> %s" % (count, out_path))
        else:
            out_dir = out_path
            if out_dir.lower().endswith(".ico"):
                out_dir = os.path.splitext(out_dir)[0] + "_out"
            os.makedirs(out_dir, exist_ok=True)

            for fi, path in enumerate(paths):
                base = os.path.splitext(os.path.basename(path))[0]
                self._log("[%d/%d] %s (%s)" % (fi + 1, total,
                                               os.path.basename(path), fmt_tag))
                try:
                    images = self._load_images(path)
                except Exception as e:
                    self._log("  错误: %s" % e)
                    continue
                if not images:
                    self._log("  没有找到图片")
                    continue

                self._progress((fi + 1) / total * 100)
                ico_path = os.path.join(out_dir, base + ".ico")
                count = pack_ico(images, ico_path, fmt=fmt,
                                 quality=q, rotation=rot)
                self._log("  打包 %d 张 -> %s" % (count, ico_path))

            self._progress(100)

    def _do_img2ico(self, paths, out_path, fmt, q, rot):
        """图片 → JXAG ICO（懒加载）"""
        total = len(paths)
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损',
                   'jpg': 'JPG q=%d' % q}[fmt]
        if rot:
            fmt_tag += ", 旋转%d°" % rot

        self._status("打包 %d 张 (%s)..." % (total, fmt_tag))
        images = [{'index': i, 'path': p} for i, p in enumerate(paths)]
        count = pack_ico(images, out_path, fmt=fmt, quality=q, rotation=rot)
        self._progress(100)
        self._log("打包 %d 张 -> %s [%s]" % (count, out_path, fmt_tag))

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


def msg_json(s):
    """简单 JSON 字符串转义（避免依赖 json 模块做简单场景）"""
    import json
    return json.dumps(s, ensure_ascii=False)
