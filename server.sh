#!/usr/bin/env bash

: <<!
Name: server.sh
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-10-13 10:36:13

Description: 启动文件服务

Attentions:
- host/port 的值一定要和 conf/app.toml 的 monitor.host/monitor.port 一致

Depends:
-
!

workers=2
host='127.0.0.1'
port=1500
timeout=60
name='server'

if command -v gunicorn &>/dev/null; then
  gunicorn=gunicorn
elif command -v /usr/local/python3.11.0/bin/gunicorn &>/dev/null; then
  gunicorn='/usr/local/python3.11.0/bin/gunicorn'
else
  echo -e "\033[31m需要先安装 gunicorn\033[0m"
  exit
fi

$gunicorn -w $workers -b $host:$port --timeout $timeout $name:app
