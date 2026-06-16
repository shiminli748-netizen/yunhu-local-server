#!/usr/bin/env python3
"""生成自签名SSL证书用于本地HTTPS/WSS服务器"""

import os
import subprocess
import sys

CERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cert")
CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE = os.path.join(CERT_DIR, "key.pem")


def generate_cert():
    os.makedirs(CERT_DIR, exist_ok=True)

    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"SSL证书已存在: {CERT_FILE}")
        return

    print("正在生成自签名SSL证书...")

    # 使用openssl生成自签名证书
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", KEY_FILE,
        "-out", CERT_FILE,
        "-days", "3650",
        "-nodes",
        "-subj", "/CN=127.0.0.1/O=YHChat Local Server/C=CN",
        "-addext", "subjectAltName=IP:127.0.0.1,IP:0.0.0.0,DNS:localhost",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"证书生成成功: {CERT_FILE}")
        print(f"私钥生成成功: {KEY_FILE}")
    except subprocess.CalledProcessError as e:
        print(f"证书生成失败: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("错误: 未找到openssl命令，请先安装openssl")
        sys.exit(1)


if __name__ == "__main__":
    generate_cert()
