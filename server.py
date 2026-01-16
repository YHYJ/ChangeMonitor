#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: server.py
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-10-11 15:59:02

Description: 文件接收器 -- 接收 Client 端发送的文件
"""

import os
from pathlib import Path
import threading
import uuid

from flask import Flask, jsonify, request
from logwrapper import get_logger
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from utils.config import scheduler
from utils.heartbeat import Heartbeat

# 配置文件
conf = 'conf'
confile = os.path.join(conf, 'app.toml')

# 程序配置项
config = scheduler(confile)

# 初始化日志记录器
logger_conf = config.get('logger', {})
logger = get_logger(logfolder='logs', config=logger_conf)

monitor_conf = config.get('monitor', {})
host = monitor_conf.get('host', '127.0.0.1')
port = monitor_conf.get('port', 1500)
rule = monitor_conf.get('rule', '/upload')
allowed = monitor_conf.get('allowed', [])
max_size = monitor_conf.get('max_size', 16)  # MB

server_conf = monitor_conf.get('server', {})
path = server_conf.get('path', 'uploads')

# 配置
upload_folder = Path(path).resolve()

# 确保上传目录存在
upload_folder.mkdir(parents=True, exist_ok=True)
logger.info('Upload folder: {}'.format(upload_folder))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = max_size * 1024 * 1024  # MB to bytes

# 启动心跳线程
heartbeat_conf = config.get('heartbeat', {})
heartbeat = Heartbeat(config=heartbeat_conf, logger=logger)
heartbeat_thread = threading.Thread(target=heartbeat.start, daemon=True)
heartbeat_thread.start()


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    logger.error('File too large: {}'.format(e))
    return jsonify({"error": "File too large"}), 413


@app.route(rule, methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            logger.error('No file part in request')
            return jsonify({"error": "No file part in request"}), 400

        file = request.files['file']
        filename = file.filename

        if not filename:
            logger.error('No file selected')
            return jsonify({"error": "No file selected"}), 400

        # 获取安全的文件名
        secure_fname = secure_filename(filename)
        if not secure_fname:
            logger.error('Invalid filename: {}'.format(filename))
            return jsonify({"error": "Invalid filename"}), 400

        # 获取文件扩展名
        suffix = Path(secure_fname).suffix
        ext = suffix.lower() if suffix else 'unknown'

        # 检查文件类型
        if isinstance(allowed, str):
            target = ext == allowed.lower()
        elif isinstance(allowed, list):
            target = ext in [item.lower() for item in allowed]
        else:
            logger.error("Invalid configuration item: 'monitor.allowed'")
            return jsonify(
                {"error":
                 "Invalid configuration item: 'monitor.allowed'"}), 500

        if not target:
            logger.warning("File type '{}' not allowed".format(ext))
            return jsonify({"error":
                            "File type '{}' not allowed".format(ext)}), 400

        # 生成唯一文件名防止冲突
        unique_name = '{}{}'.format(uuid.uuid4().hex, ext)
        filepath = upload_folder / unique_name

        # 保存文件
        file.save(filepath)
        logger.info('File uploaded: {}'.format(unique_name))

        return jsonify({
            "message": "File uploaded successfully",
            "filename": unique_name,
            "original": filename
        }), 200
    except RequestEntityTooLarge:
        logger.error('File too large')
        return jsonify({"error": "File too large"}), 413
    except Exception as e:
        logger.error('Upload failed: {}'.format(e))
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    # 仅用于开发调试，生产环境请用 Gunicorn
    app.run(host=host, port=port, debug=False)
