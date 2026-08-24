"""Double-click this file or run: python start.py"""
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8000


def check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return whether the launcher can bind without touching other processes."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def check_dependencies():
    """检查必要的依赖是否安装"""
    try:
        import uvicorn
        import fastapi
        return True
    except ImportError as e:
        print(f"缺少依赖: {e}")
        return False


def main():
    print("=" * 50)
    print("  智演 Agent - 启动脚本")
    print("=" * 50)
    print()

    print(f"使用Python: {sys.executable}")
    print(f"Python版本: {sys.version}")
    print()

    # 检查依赖
    print("检查依赖...")
    if not check_dependencies():
        print("依赖检查失败，请手动安装: pip install -r requirements.txt")
        sys.exit(1)
    print("依赖检查通过")
    print()

    # 检查端口，不终止任何现有进程
    print(f"检查端口 {PORT} 状态...")
    if not check_port_available(PORT):
        print(f"端口 {PORT} 已被占用。请关闭对应服务，或直接访问现有服务。")
        sys.exit(1)

    print(f"端口 {PORT} 可用")
    print()

    # 启动服务
    print("启动服务...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
    )

    print(f"等待服务启动 (端口 {PORT})...")
    for _ in range(30):  # 增加等待时间到15秒
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            print("服务已就绪!")
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
            print(f"浏览器已打开。服务运行在 http://127.0.0.1:{PORT}")
            print(f"API文档: http://127.0.0.1:{PORT}/docs")
            print("按 Ctrl+C 停止服务。")
            proc.wait()
            break
        except Exception:
            continue
    else:
        print("服务启动失败。请检查上方的错误输出。")
        proc.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
