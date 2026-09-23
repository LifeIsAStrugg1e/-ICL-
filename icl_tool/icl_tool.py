import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from icl_core import parse_icl, decode_jpg
from ico_core import pack_ico
from extract import extract_file, detect_format


class App:
    def __init__(self, root):
        self.root = root
        root.title("ICL/ICO 图片工具")
        root.resizable(False, False)

        self.input_paths = []
        self.mode = tk.StringVar(value="extract")   # extract | pack
        self.output_format = tk.StringVar(value="raw")  # raw | jpg | bmp | png (extract) / ico (pack)
        self.output_path = tk.StringVar()
        self.quality = tk.IntVar(value=95)
        self.running = False

        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 8, 'pady': 4}

        # ===== mode =====
        frm_mode = ttk.LabelFrame(self.root, text="操作模式")
        frm_mode.pack(fill="x", **pad)
        ttk.Radiobutton(frm_mode, text="解压提取（ICL / ICO → 图片）",
                        variable=self.mode, value="extract",
                        command=self._on_mode_change).pack(anchor="w", padx=8, pady=2)
        ttk.Radiobutton(frm_mode, text="打包（ICL → ICO 设备格式）",
                        variable=self.mode, value="pack",
                        command=self._on_mode_change).pack(anchor="w", padx=8, pady=2)

        # ===== input files =====
        frm_file = ttk.LabelFrame(self.root, text="输入文件")
        frm_file.pack(fill="x", **pad)

        self.lst_files = tk.Listbox(frm_file, height=4, width=60)
        self.lst_files.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        frm_btn = ttk.Frame(frm_file)
        frm_btn.pack(side="right", padx=4, pady=4)
        ttk.Button(frm_btn, text="添加文件", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(frm_btn, text="添加文件夹", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(frm_btn, text="移除选中", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(frm_btn, text="清空", command=self.clear_files).pack(fill="x", pady=2)

        # ===== output format =====
        frm_fmt = ttk.LabelFrame(self.root, text="输出格式")
        frm_fmt.pack(fill="x", **pad)

        self.frm_extract_fmt = ttk.Frame(frm_fmt)
        self.frm_extract_fmt.pack(fill="x", padx=8, pady=2)
        for val, label in [("raw", "原始文件（保持 jpg/png 不动）"),
                           ("jpg", "JPG（解码后重编码）"),
                           ("bmp", "BMP"),
                           ("png", "PNG")]:
            ttk.Radiobutton(self.frm_extract_fmt, text=label,
                            variable=self.output_format, value=val).pack(anchor="w", pady=1)

        self.frm_pack_fmt = ttk.Frame(frm_fmt)
        # quality slider (both modes when outputting image files)
        self.frm_quality = ttk.Frame(frm_fmt)
        self.frm_quality.pack(fill="x", padx=8, pady=2)
        ttk.Label(self.frm_quality, text="JPG 质量:").pack(side="left")
        self.scl_quality = ttk.Scale(self.frm_quality, from_=50, to=100,
                                     variable=self.quality, length=200)
        self.scl_quality.pack(side="left", padx=4)
        self.lbl_quality = ttk.Label(self.frm_quality, text="95")
        self.lbl_quality.pack(side="left")
        self.quality.trace_add("write", lambda *_: self.lbl_quality.config(
            text=str(int(self.quality.get()))))

        # ===== output path =====
        frm_out = ttk.LabelFrame(self.root, text="输出路径")
        frm_out.pack(fill="x", **pad)

        self.lbl_out_desc = ttk.Label(frm_out, text="输出文件夹:")
        self.lbl_out_desc.pack(anchor="w", padx=8, pady=(4, 0))

        row = ttk.Frame(frm_out)
        row.pack(fill="x", padx=8, pady=4)
        self.ent_out = ttk.Entry(row, textvariable=self.output_path, width=55)
        self.ent_out.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="浏览...", command=self.browse_output).pack(side="right", padx=(4, 0))

        # ===== run =====
        frm_run = ttk.Frame(self.root)
        frm_run.pack(fill="x", **pad)

        self.btn_start = ttk.Button(frm_run, text="开始", command=self.start)
        self.btn_start.pack(side="left", padx=8)

        self.prg = ttk.Progressbar(frm_run, length=350, mode="determinate")
        self.prg.pack(side="left", fill="x", expand=True, padx=8)

        self.lbl_status = ttk.Label(frm_run, text="就绪")
        self.lbl_status.pack(side="left", padx=8)

        # ===== log =====
        frm_log = ttk.LabelFrame(self.root, text="日志")
        frm_log.pack(fill="both", expand=True, **pad)

        self.txt_log = tk.Text(frm_log, height=10, width=70, state="disabled",
                               font=("Consolas", 9))
        scroll = ttk.Scrollbar(frm_log, command=self.txt_log.yview)
        self.txt_log.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.txt_log.pack(fill="both", expand=True, padx=4, pady=4)

        self._on_mode_change()

    # ---- mode ----

    def _on_mode_change(self):
        mode = self.mode.get()
        for w in self.frm_extract_fmt.winfo_children():
            w.destroy()
        self.frm_pack_fmt.pack_forget()
        self.frm_extract_fmt.pack_forget()

        if mode == "extract":
            self.frm_extract_fmt.pack(fill="x", padx=8, pady=2)
            for val, label in [("raw", "原始文件（保持 jpg/png 不动）"),
                               ("jpg", "JPG（解码后重编码）"),
                               ("bmp", "BMP"),
                               ("png", "PNG")]:
                ttk.Radiobutton(self.frm_extract_fmt, text=label,
                                variable=self.output_format, value=val).pack(anchor="w", pady=1)
            if self.output_format.get() not in ("raw", "jpg", "bmp", "png"):
                self.output_format.set("raw")
            self.lbl_out_desc.config(text="输出文件夹:")
            self.frm_quality.pack(fill="x", padx=8, pady=2)
        else:
            self.output_format.set("ico")
            self.lbl_out_desc.config(text="输出 ICO 文件:")
            self.frm_quality.pack_forget()
        self.output_path.set("")

    # ---- file selection ----

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 ICL / ICO 文件",
            filetypes=[("图片容器", "*.icl *.ico"), ("ICL files", "*.icl"),
                       ("ICO files", "*.ico"), ("All files", "*.*")])
        for p in paths:
            if p not in self.input_paths:
                self.input_paths.append(p)
                self.lst_files.insert("end", os.path.basename(p))

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含 ICL/ICO 的文件夹")
        if not folder:
            return
        count = 0
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".icl", ".ico")):
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
            self.txt_log.config(state="normal")
            self.txt_log.insert("end", msg + "\n")
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")
        self.root.after(0, _do)

    def _status(self, msg):
        self.root.after(0, lambda: self.lbl_status.config(text=msg))

    def _progress(self, value):
        self.root.after(0, lambda: self.prg.configure(value=value))

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
        if mode == "pack" and not out.lower().endswith(".ico"):
            out += ".ico"
            self.output_path.set(out)

        self.running = True
        self.btn_start.config(state="disabled")
        self.prg["value"] = 0
        self._log("=" * 50)

        threading.Thread(target=self._worker, args=(out, mode), daemon=True).start()

    def _worker(self, out, mode):
        try:
            if mode == "extract":
                self._do_extract(out)
            else:
                self._do_pack(out)
            self._status("完成")
        except Exception as e:
            self._status("出错")
            self._log(f"错误: {e}")
        finally:
            self.running = False
            self.root.after(0, lambda: self.btn_start.config(state="normal"))

    def _do_extract(self, out_dir):
        fmt = self.output_format.get()
        quality = int(self.quality.get())
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
        fmt = self.output_format.get()
        total = len(self.input_paths)

        if total == 1:
            path = self.input_paths[0]
            base = os.path.splitext(os.path.basename(path))[0]
            self._log(f"[1/1] {os.path.basename(path)}")

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

            count = pack_ico(images, out_path)
            self._log(f"  打包 {count} 张 -> {out_path} ({os.path.getsize(out_path)} bytes)")
            self._progress(100)
        else:
            out_dir = out_path
            if out_dir.lower().endswith(".ico"):
                out_dir = os.path.splitext(out_dir)[0] + "_out"
            os.makedirs(out_dir, exist_ok=True)

            for fi, path in enumerate(self.input_paths):
                base = os.path.splitext(os.path.basename(path))[0]
                self._log(f"[{fi+1}/{total}] {os.path.basename(path)}")

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
                count = pack_ico(images, ico_path)
                self._log(f"  打包 {count} 张 -> {ico_path}")

            self._progress(100)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
