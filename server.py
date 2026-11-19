#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入党积极分子刷题库 · 本地局域网服务器（仅用 Python 标准库）

用法（双击 start.bat 即可，也可命令行运行）：
    python server.py            # 默认端口 8080
    python server.py --port 9000
    python server.py --open     # 启动后自动打开浏览器

电脑打开 http://localhost:8080 ，
手机连同一个 WiFi，扫码或访问 http://<本机局域网IP>:8080
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def detect_lan_ip() -> str:
    """尽量拿到本机在局域网中的 IPv4 地址。"""
    ip = ""
    # 方法 1：UDP 连接外网地址，不会真正发包，仅用于选出默认出口网卡
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        ip = ""
    # 方法 2：解析主机名
    if not ip or ip.startswith("127."):
        try:
            cand = socket.gethostbyname(socket.gethostname())
            if cand and not cand.startswith("127."):
                ip = cand
        except OSError:
            pass
    if not ip or ip.startswith("127."):
        ip = "127.0.0.1"
    return ip


class QuizHandler(SimpleHTTPRequestHandler):
    server_version = "DangjianQuiz/1.0"

    def do_GET(self):  # noqa: N802 (http.server 约定)
        if self.path.split("?", 1)[0] == "/api/info":
            payload = json.dumps(
                {"lan": self.server.lan_ip, "port": self.server.server_port},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, fmt, *args):  # 精简日志
        sys.stdout.write("  %s\n" % (fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser(description="入党积极分子刷题库本地服务器")
    parser.add_argument("--port", type=int, default=8080, help="监听端口（默认 8080）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()

    lan_ip = detect_lan_ip()
    handler = partial(QuizHandler, directory=str(ROOT))

    # 端口被占用时自动尝试后面几个端口
    port = args.port
    httpd = None
    for candidate in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer((args.host, candidate), handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        print("[错误] 端口被占用，且 8080~8089 均不可用，请用 --port 指定其他端口。")
        sys.exit(1)

    httpd.lan_ip = lan_ip  # 供 /api/info 使用

    local_url = f"http://localhost:{port}/"
    lan_url = f"http://{lan_ip}:{port}/"

    bar = "=" * 52
    print(bar)
    print("  入党积极分子刷题库 · 本地服务已启动")
    print(bar)
    print(f"  电脑访问： {local_url}")
    print(f"  手机访问： {lan_url}")
    print("  （手机需和电脑连在同一个 WiFi/局域网）")
    if lan_ip.startswith("127."):
        print("  [提示] 未能识别局域网 IP，请检查网络连接。")
    print("  关闭本窗口即停止服务。")
    print(bar)

    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(local_url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
