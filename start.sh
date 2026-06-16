#!/bin/bash
# 云湖模拟服务器启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  云湖(YHChat)模拟服务器 启动脚本"
echo "========================================="

# 创建必要目录
mkdir -p data static/uploads cert

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 安装依赖
echo "检查依赖..."
pip3 install aiohttp 2>/dev/null || pip install aiohttp 2>/dev/null || {
    echo "错误: 无法安装aiohttp"
    exit 1
}

# 生成SSL证书
if [ ! -f cert/cert.pem ] || [ ! -f cert/key.pem ]; then
    echo "生成SSL证书..."
    python3 gen_cert.py
else
    echo "SSL证书已存在"
fi

# 启动服务器
echo "启动服务器..."
echo "  HTTPS: https://127.0.0.1:8443"
echo "  WSS:   wss://127.0.0.1:8444/ws"
echo "  Admin: https://127.0.0.1:8443/admin/"
echo "  默认管理员: admin / admin123"
echo "========================================="

python3 server.py
