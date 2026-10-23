"""WebView2 Runtime 检测与安装

流程:
  1. 检查注册表 → 已安装则跳过
  2. 下载 MicrosoftEdgeWebview2Setup.exe (~1.5MB)
  3. 尝试静默安装
  4. 失败 → 返回 False, 由调用方提示手动安装
"""
import os
import ctypes
import tempfile
import subprocess
import winreg

# WebView2 Runtime 注册表项 (Windows 10/11 通用)
_REG_PATHS = [
    (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients",
     "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    (r"SOFTWARE\Microsoft\EdgeUpdate\Clients",
     "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    # 旧版
    (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients",
     "{1C7CE5B4-198D-4B16-8D2B-9F5560005E00}"),
]

# 官方下载地址 (Evergreen Bootstrapper)
_BOOTSTRAPPER_URL = (
    "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
)
_MANUAL_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"


def _read_reg(hive, path, key_name):
    """读取注册表值，失败返回 None"""
    try:
        with winreg.OpenKey(hive, path) as key:
            val, _ = winreg.QueryValueEx(key, key_name)
            return val
    except (FileNotFoundError, OSError):
        return None


def is_webview2_installed():
    """检测 WebView2 Runtime 是否已安装"""
    # 检查版本值 (pv)
    for path, guid in _REG_PATHS:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            ver = _read_reg(hive, path + "\\" + guid, "pv")
            if ver and ver not in ("", "0.0.0.0"):
                return True

    # 备用: 检查 dll 是否存在
    local_app = os.environ.get("LOCALAPPDATA", "")
    edge_path = os.path.join(
        local_app, "Microsoft", "EdgeWebView", "Application")
    if os.path.isdir(edge_path):
        for d in os.listdir(edge_path):
            if os.path.isdir(os.path.join(edge_path, d)):
                return True
    return False


def download_bootstrapper(dest_path=None, timeout=60):
    """下载 WebView2 安装器 (~1.5MB)

    Returns: 下载成功返回路径, 失败返回 None
    """
    import urllib.request
    if dest_path is None:
        dest_path = os.path.join(tempfile.gettempdir(),
                                 "MicrosoftEdgeWebview2Setup.exe")
    try:
        req = urllib.request.Request(_BOOTSTRAPPER_URL,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100000:  # 至少应有 100KB
            return None
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path
    except Exception:
        return None


def install_webview2(silent=True, timeout=120):
    """安装 WebView2 Runtime

    Args:
        silent: True=静默安装, False=显示安装界面
        timeout: 超时秒数

    Returns:
        True=安装成功或已安装, False=安装失败(需手动安装)
    """
    if is_webview2_installed():
        return True

    # 下载安装器
    setup_path = download_bootstrapper()
    if setup_path is None:
        return False

    # 构建命令行
    if silent:
        args = [setup_path, "/silent", "/install"]
    else:
        args = [setup_path, "/install"]

    try:
        # 检查管理员权限
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

        if silent and not is_admin:
            # 静默安装需要权限，尝试用 runas 提升
            params = " ".join('"%s"' % a for a in args[1:])
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", setup_path, params, None, 1)
            # ShellExecuteW 返回 >32 表示成功
            if rc <= 32:
                return False
            # 等待安装完成
            import time
            for _ in range(timeout):
                time.sleep(1)
                if is_webview2_installed():
                    return True
            return is_webview2_installed()
        else:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                return False
            return is_webview2_installed()
    except Exception:
        return False


def get_manual_install_message():
    """返回手动安装提示信息"""
    return (
        "未检测到 Microsoft Edge WebView2 Runtime。\n\n"
        "自动安装失败（可能权限不足）。\n\n"
        "请手动安装：\n"
        "1. 访问: %s\n"
        "2. 下载并运行 WebView2 Runtime 安装程序\n"
        "3. 安装完成后重新启动本工具\n\n"
        "或尝试以管理员身份运行本工具后重试。"
    ) % _MANUAL_URL


def ensure_webview2(silent=True):
    """确保 WebView2 可用

    Returns:
        (ok, need_manual) 
        ok=True: 已就绪
        ok=False, need_manual=True: 需要手动安装
        ok=False, need_manual=False: 尝试安装中失败
    """
    if is_webview2_installed():
        return True, False
    ok = install_webview2(silent=silent)
    if ok:
        return True, False
    return False, True


if __name__ == "__main__":
    print("installed:", is_webview2_installed())
    ok, manual = ensure_webview2()
    print("ok:", ok, "need_manual:", manual)
