"""ICL/ICO 图片工具 - CustomTkinter 版本

功能与 icl_tool.py 完全一致，仅 UI 框架不同。
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from icl_core import parse_icl, decode_jpg
from ico_core import pack_ico
from extract import extract_file, detect_format

# 主题配置
ctk.set_appearance_mode("dark")          # dark / light / system
ctk.set_default_color_theme("blue")      # blue / dark-blue / green


def _labeled_frame(parent, text):
    """创建带标题的 Frame（模拟 LabelFrame）"""
    frame = ctk.CTkFrame(parent)
    label = ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=13, weight="bold"))
    label.pack(anchor="w", padx=10, pady=(8, 2))
    return frame


class App:
    """ICL/ICO 图片工具 GUI (CustomTkinter).

    Three modes:
      - extract: ICL/ICO → images (BMP/JPG/PNG/raw)
      - pack:    ICL/ICO → JXAG ICO (rgb565/rgb24/jpg)
      - img2ico: images → JXAG ICO (jpg/png/bmp input)
    """

    def __init__(self, root):
        self.root = root
        root.title("ICL/ICO 图片工具")
        root.geometry("700x720")
        root.resizable(False, False)

        self.input_paths = []
        self.mode = tk.StringVar(value="extract")
        self.output_format = tk.StringVar(value="raw")
        self.output_path = tk.StringVar()
        self.comp_fmt = tk.StringVar(value="rgb565")
        self.lossy_quality = tk.DoubleVar(value=90)
        self.rotation = tk.StringVar(value="0")
        self.running = False

        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 12, 'pady': 6}

        # ===== mode =====
        frm_mode = _labeled_frame(self.root, "操作模式")
        frm_mode.pack(fill="x", **pad)

        for val, label in [("extract", "解压提取（ICL / ICO → 图片）"),
                           ("pack", "打包（ICL / ICO → ICO 设备格式）"),
                           ("img2ico", "图片压缩（JPG/PNG/BMP → ICO）")]:
            ctk.CTkRadioButton(frm_mode, text=label,
                               variable=self.mode, value=val,
                               command=self._on_mode_change).pack(anchor="w", padx=16, pady=3)

        # ===== input files =====
        frm_file = _labeled_frame(self.root, "输入文件")
        frm_file.pack(fill="x", **pad)

        # 文件列表（CTk 无 Listbox，保留 tkinter）
        list_frame = ctk.CTkFrame(frm_file, fg_color="transparent")
        list_frame.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=(0, 8))

        self.lst_files = tk.Listbox(list_frame, height=4, width=60,
                                    bg="#2b2b2b", fg="#d4d4d4",
                                    selectbackground="#1f538d",
                                    selectforeground="#ffffff",
                                    relief="flat", borderwidth=0,
                                    font=("Microsoft YaHei UI", 10))
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.lst_files.yview)
        self.lst_files.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.lst_files.pack(fill="x", expand=True)

        frm_btn = ctk.CTkFrame(frm_file, fg_color="transparent")
        frm_btn.pack(side="right", padx=(4, 10), pady=(0, 8))
        ctk.CTkButton(frm_btn, text="添加文件", width=120, command=self.add_files).pack(fill="x", pady=3)
        ctk.CTkButton(frm_btn, text="添加文件夹", width=120, command=self.add_folder).pack(fill="x", pady=3)
        ctk.CTkButton(frm_btn, text="移除选中", width=120, fg_color="#8b3a3a", hover_color="#a04444",
                      command=self.remove_selected).pack(fill="x", pady=3)
        ctk.CTkButton(frm_btn, text="清空", width=120, fg_color="#5a5a5a", hover_color="#6a6a6a",
                      command=self.clear_files).pack(fill="x", pady=3)

        # ===== output format =====
        frm_fmt = _labeled_frame(self.root, "输出格式")
        frm_fmt.pack(fill="x", **pad)

        self.frm_extract_fmt = ctk.CTkFrame(frm_fmt, fg_color="transparent")
        self.frm_lossy = ctk.CTkFrame(frm_fmt, fg_color="transparent")
        self.frm_rotate = ctk.CTkFrame(frm_fmt, fg_color="transparent")

        # ===== output path =====
        frm_out = _labeled_frame(self.root, "输出路径")
        frm_out.pack(fill="x", **pad)

        self.lbl_out_desc = ctk.CTkLabel(frm_out, text="输出文件夹:")
        self.lbl_out_desc.pack(anchor="w", padx=10, pady=(0, 2))

        row = ctk.CTkFrame(frm_out, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        self.ent_out = ctk.CTkEntry(row, textvariable=self.output_path, width=480,
                                    placeholder_text="选择输出路径...")
        self.ent_out.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row, text="浏览...", width=80, command=self.browse_output).pack(side="right")

        # ===== run =====
        frm_run = ctk.CTkFrame(self.root, fg_color="transparent")
        frm_run.pack(fill="x", **pad)

        self.btn_start = ctk.CTkButton(frm_run, text="开始", width=100, height=36,
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color="#2d8a4e", hover_color="#35a35a",
                                       command=self.start)
        self.btn_start.pack(side="left", padx=(12, 8))

        self.prg = ctk.CTkProgressBar(frm_run, width=360)
        self.prg.pack(side="left", fill="x", expand=True, padx=8)
        self.prg.set(0)

        self.lbl_status = ctk.CTkLabel(frm_run, text="就绪", width=80)
        self.lbl_status.pack(side="left", padx=(8, 12))

        # ===== log =====
        frm_log = _labeled_frame(self.root, "日志")
        frm_log.pack(fill="both", expand=True, **pad)

        self.txt_log = ctk.CTkTextbox(frm_log, height=180,
                                      font=("Consolas", 10),
                                      state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._on_mode_change()

    # ---- mode ----

    def _on_mode_change(self):
        mode = self.mode.get()

        # 清除旧内容
        for w in self.frm_extract_fmt.winfo_children():
            w.destroy()
        for w in self.frm_lossy.winfo_children():
            w.destroy()
        for w in self.frm_rotate.winfo_children():
            w.destroy()

        self.frm_extract_fmt.pack_forget()
        self.frm_lossy.pack_forget()
        self.frm_rotate.pack_forget()

        if mode == "extract":
            self.frm_extract_fmt.pack(fill="x", padx=10, pady=(0, 8))
            for val, label in [("raw", "原始文件（保持 jpg/png 不动）"),
                               ("jpg", "JPG（解码后重编码）"),
                               ("bmp", "BMP"),
                               ("png", "PNG")]:
                ctk.CTkRadioButton(self.frm_extract_fmt, text=label,
                                   variable=self.output_format, value=val).pack(anchor="w", pady=2)
            if self.output_format.get() not in ("raw", "jpg", "bmp", "png"):
                self.output_format.set("raw")
            self.lbl_out_desc.configure(text="输出文件夹:")

        elif mode in ("img2ico", "pack"):
            self.output_format.set("ico")
            self.lbl_out_desc.configure(text="输出 ICO 文件:")

            # 压缩格式
            self.frm_lossy.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(self.frm_lossy, text="压缩格式:").pack(anchor="w", pady=(0, 2))
            for val, label in [("rgb565", "RGB565 16-bit 无损（C工具兼容）"),
                               ("rgb24", "RGB24 24-bit 无损（BGRA）"),
                               ("jpg", "JPG 24-bit 有损压缩")]:
                ctk.CTkRadioButton(self.frm_lossy, text=label,
                                   variable=self.comp_fmt, value=val,
                                   command=self._on_fmt_change).pack(anchor="w", pady=2, padx=16)

            # 质量滑块
            self.frm_lossy_quality = ctk.CTkFrame(self.frm_lossy, fg_color="transparent")
            ctk.CTkLabel(self.frm_lossy_quality, text="压缩率:").pack(side="left")
            self.scl_lossy_q = ctk.CTkSlider(self.frm_lossy_quality, from_=10, to=100,
                                             variable=self.lossy_quality, width=200,
                                             command=self._on_quality_change)
            self.scl_lossy_q.pack(side="left", padx=8)
            self.lbl_lossy_q = ctk.CTkLabel(self.frm_lossy_quality, text="90", width=30)
            self.lbl_lossy_q.pack(side="left")

            # 旋转
            self.frm_rotate.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(self.frm_rotate, text="旋转:").pack(side="left", padx=(0, 8))
            for val, label in [("0", "不旋转"), ("90", "90°"),
                               ("180", "180°"), ("270", "270°")]:
                ctk.CTkRadioButton(self.frm_rotate, text=label,
                                   variable=self.rotation, value=val).pack(side="left", padx=6)

            self._on_fmt_change()

        self.output_path.set("")

    def _on_fmt_change(self):
        if self.comp_fmt.get() == "jpg":
            self.frm_lossy_quality.pack(fill="x", padx=16, pady=(4, 4))
        else:
            self.frm_lossy_quality.pack_forget()

    def _on_quality_change(self, value):
        self.lbl_lossy_q.configure(text=str(int(float(value))))

    # ---- file selection ----

    def add_files(self):
        mode = self.mode.get()
        if mode == "img2ico":
            paths = filedialog.askopenfilenames(
                title="选择图片文件",
                filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"),
                           ("JPG", "*.jpg *.jpeg"), ("PNG", "*.png"),
                           ("BMP", "*.bmp"), ("All files", "*.*")])
        else:
            paths = filedialog.askopenfilenames(
                title="选择 ICL / ICO 文件",
                filetypes=[("图片容器", "*.icl *.ico"), ("ICL files", "*.icl"),
                           ("ICO files", "*.ico"), ("All files", "*.*")])
        for p in paths:
            if p not in self.input_paths:
                self.input_paths.append(p)
                self.lst_files.insert("end", os.path.basename(p))

    def add_folder(self):
        mode = self.mode.get()
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return
        if mode == "img2ico":
            exts = (".jpg", ".jpeg", ".png", ".bmp")
        else:
            exts = (".icl", ".ico")
        count = 0
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(exts):
                p = os.path.join(folder, name)
                if p not in self.input_paths:
                    self.input_paths.append(p)
                    self.lst_files.insert("end", name)
                    count += 1
        self._log(f"从文件夹添加 {count} 个文件")

    def remove_selected(self):
        sel = list(self.lst_files.curselection())
        for i in reversed(sel):
            self.lst_files.delete(i)
            del self.input_paths[i]

    def clear_files(self):
        self.lst_files.delete(0, "end")
        self.input_paths.clear()

    # ---- output ----

    def browse_output(self):
        mode = self.mode.get()
        if mode == "extract":
            p = filedialog.askdirectory(title="选择输出文件夹")
        else:
            p = filedialog.asksaveasfilename(
                title="保存 ICO 文件",
                defaultextension=".ico",
                filetypes=[("ICO files", "*.ico"), ("All files", "*.*")])
        if p:
            self.output_path.set(p)

    # ---- logging ----

    def _log(self, msg):
        def _do():
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", msg + "\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        self.root.after(0, _do)

    def _status(self, msg):
        self.root.after(0, lambda: self.lbl_status.configure(text=msg))

    def _progress(self, value):
        self.root.after(0, lambda: self.prg.set(value / 100))

    # ---- run ----

    def start(self):
        if self.running:
            return
        if not self.input_paths:
            messagebox.showwarning("提示", "请先添加文件")
            return
        out = self.output_path.get().strip()
        if not out:
            messagebox.showwarning("提示", "请选择输出路径")
            return

        mode = self.mode.get()
        if mode in ("pack", "img2ico") and not out.lower().endswith(".ico"):
            out += ".ico"
            self.output_path.set(out)

        self.running = True
        self.btn_start.configure(state="disabled")
        self.prg.set(0)
        self._log("=" * 50)

        threading.Thread(target=self._worker, args=(out, mode), daemon=True).start()

    def _worker(self, out, mode):
        """Background thread worker: dispatch to mode handler."""
        try:
            if mode == "extract":
                self._do_extract(out)
            elif mode == "img2ico":
                self._do_img2ico(out)
            else:
                self._do_pack(out)
            self._status("完成")
        except Exception as e:
            self._status("出错")
            self._log(f"错误: {e}")
        finally:
            self.running = False
            self.root.after(0, lambda: self.btn_start.configure(state="normal"))

    def _do_extract(self, out_dir):
        """Extract mode: ICL/ICO → images (quality fixed to 100)."""
        fmt = self.output_format.get()
        quality = 100
        total = len(self.input_paths)
        total_images = 0

        for fi, path in enumerate(self.input_paths):
            base = os.path.splitext(os.path.basename(path))[0]
            self._log(f"[{fi+1}/{total}] {os.path.basename(path)}")

            sub_dir = os.path.join(out_dir, base) if total > 1 else out_dir
            try:
                count, file_fmt = extract_file(path, sub_dir, fmt_out=fmt, quality=quality)
                self._log(f"  [{file_fmt}] 提取 {count} 张 -> {sub_dir}")
                total_images += count
            except Exception as e:
                self._log(f"  错误: {e}")

            self._progress((fi + 1) / total * 100)
            self._status(f"{int((fi+1)/total*100)}%")

        self._progress(100)
        self._log(f"完成，共 {total_images} 张图片")

    def _do_pack(self, out_path):
        """Pack mode: ICL/ICO → JXAG ICO (three compression formats)."""
        total = len(self.input_paths)
        fmt = self.comp_fmt.get()
        q = int(self.lossy_quality.get())
        rot = int(self.rotation.get())
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损', 'jpg': f'JPG q={q}'}[fmt]
        if rot:
            fmt_tag += f", 旋转{rot}°"

        if total == 1:
            path = self.input_paths[0]
            base = os.path.splitext(os.path.basename(path))[0]
            self._log(f"[1/1] {os.path.basename(path)} ({fmt_tag})")

            with open(path, 'rb') as f:
                data = f.read()
            file_fmt = detect_format(data)
            if file_fmt == 'icl':
                images = parse_icl(data)
            else:
                from extract import extract_ico
                images = extract_ico(data)
                for img in images:
                    img['jpg'] = img.pop('data')

            if not images:
                self._log("  没有找到图片")
                return

            for ii, img in enumerate(images):
                self._status(f"打包 {ii+1}/{len(images)}")
                self._progress((ii + 1) / len(images) * 100)

            count = pack_ico(images, out_path, fmt=fmt, quality=q, rotation=rot)
            self._log(f"  打包 {count} 张 -> {out_path} ({os.path.getsize(out_path)} bytes)")
            self._progress(100)
        else:
            out_dir = out_path
            if out_dir.lower().endswith(".ico"):
                out_dir = os.path.splitext(out_dir)[0] + "_out"
            os.makedirs(out_dir, exist_ok=True)

            for fi, path in enumerate(self.input_paths):
                base = os.path.splitext(os.path.basename(path))[0]
                self._log(f"[{fi+1}/{total}] {os.path.basename(path)} ({fmt_tag})")

                with open(path, 'rb') as f:
                    data = f.read()
                try:
                    file_fmt = detect_format(data)
                    if file_fmt == 'icl':
                        images = parse_icl(data)
                    elif file_fmt == 'ico':
                        from extract import extract_ico
                        images = extract_ico(data)
                        for img in images:
                            img['jpg'] = img.pop('data')
                    else:
                        self._log("  未知格式")
                        continue
                except Exception as e:
                    self._log(f"  错误: {e}")
                    continue

                if not images:
                    self._log("  没有找到图片")
                    continue

                self._status(f"{fi+1}/{total}")
                self._progress((fi + 1) / total * 100)

                ico_path = os.path.join(out_dir, base + ".ico")
                count = pack_ico(images, ico_path, fmt=fmt, quality=q, rotation=rot)
                self._log(f"  打包 {count} 张 -> {ico_path}")

            self._progress(100)

    def _do_img2ico(self, out_path):
        """图片文件直接打包为 JXAG ICO（懒加载，逐批读取）"""
        total = len(self.input_paths)
        fmt = self.comp_fmt.get()
        q = int(self.lossy_quality.get())
        rot = int(self.rotation.get())
        fmt_tag = {'rgb565': 'RGB565无损', 'rgb24': 'RGB24无损', 'jpg': f'JPG q={q}'}[fmt]
        if rot:
            fmt_tag += f", 旋转{rot}°"

        # 懒加载：只传路径，pack_ico 内部逐批读取
        images = [{'index': fi, 'path': path}
                  for fi, path in enumerate(self.input_paths)]

        self._status(f"打包 {total} 张 ({fmt_tag})...")
        count = pack_ico(images, out_path, fmt=fmt, quality=q, rotation=rot)
        self._progress(100)
        self._log(f"打包 {count} 张 -> {out_path} ({os.path.getsize(out_path)} bytes) [{fmt_tag}]")


def main():
    root = ctk.CTk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
