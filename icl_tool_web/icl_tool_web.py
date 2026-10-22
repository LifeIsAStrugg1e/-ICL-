"""ICL/ICO 图片工具 - pywebview 版本入口

启动流程:
  1. 检测 WebView2 Runtime
  2. 缺失 → 尝试静默安装
  3. 仍失败 → 提示手动安装
  4. 就绪 → 启动窗口
"""
import os
import sys
import ctypes

# 保证能导入同目录核心模块
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# 核心逻辑在 icl_tool 目录（共用）
CORE = os.path.join(os.path.dirname(BASE), "icl_tool")
sys.path.insert(0, CORE)


def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def ensure_webview():
    """确保 WebView2 可用。返回 True=就绪, False=中止"""
    from webview_check import (is_webview2_installed, ensure_webview2,
                               get_manual_install_message)

    if is_webview2_installed():
        return True

    print("[*] WebView2 Runtime not found, trying to install...")
    ok, need_manual = ensure_webview2(silent=True)

    if ok:
        print("[+] WebView2 installed OK")
        return True

    # 安装失败 → 弹窗提示
    msg = get_manual_install_message()
    if need_manual:
        msg = msg
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("缺少 WebView2 Runtime", msg, parent=root)
        root.destroy()
    except Exception:
        print(msg)
        if sys.stdin.isatty():
            input("press enter to exit")
    return False


def main():
    # 1. 检测/安装 WebView2
    if not ensure_webview():
        sys.exit(1)

    # 2. 启动 pywebview
    import webview
    from webview_api import Api

    api = Api()
    html_path = os.path.join(BASE, "web", "index.html")

    window = webview.create_window(
        "ICL/ICO 图片工具",
        html_path,
        js_api=api,
        width=650,
        height=860,
        min_size=(600, 750),
        resizable=True,
        text_select=True,
    )
    api.set_window(window)

    webview.start(debug=False)


if __name__ == "__main__":
    main()
