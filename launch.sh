#!/usr/bin/env bash
# ============================================================
# 本机专用启动脚本 (Linux) —— 用项目虚拟环境 .venv 运行 demo
#
# 用法:
#   bash launch.sh
#   (或 chmod +x launch.sh 后直接 ./launch.sh)
# ============================================================
set -e

# 无论从哪个目录调用, 都切到脚本所在目录
cd "$(dirname "$(readlink -f "$0")")"

# 清理会影响 httpx/gradio 的网络代理变量 (仅本进程, 不改用户全局环境)
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy \
      all_proxy ALL_PROXY no_proxy NO_PROXY \
      ftp_proxy FTP_PROXY

# 首次运行: 如果还没有虚拟环境, 自动创建并装依赖
if [ ! -x ".venv/bin/python" ]; then
    echo "[launch] 未找到 .venv, 正在创建虚拟环境并安装依赖 ..."
    python3 -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install -r requirements.txt
fi

echo "[launch] 启动 Gradio demo (.venv) ..."
exec ./.venv/bin/python app.py
