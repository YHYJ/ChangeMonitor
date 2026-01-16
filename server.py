#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: server.py
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-10-11 15:59:02

Description:
"""

import os
from pathlib import Path
import threading
import uuid

from flask import Flask, jsonify, request
from logwrapper import get_logger
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

server_conf = monitor_conf.get('server', {})
path = server_conf.get('path', 'uploads')

# 配置
upload_folder = Path(path).resolve()

# 确保上传目录存在
upload_folder.mkdir(exist_ok=True)
logger.info('Upload folder: {}'.format(upload_folder))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = upload_folder

# 启动心跳线程
heartbeat_conf = config.get('heartbeat', {})
heartbeat = Heartbeat(config=heartbeat_conf, logger=logger)
heartbeat_thread = threading.Thread(target=heartbeat.start, daemon=True)
heartbeat_thread.start()


@app.route(rule, methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part in request"}), 400

        file = request.files['file']
        filename = file.filename
        if filename == '' or None:
            return jsonify({"error": "No file uploaded"}), 404

        if filename:
            suffix = Path(secure_filename(filename)).suffix
            ext = suffix if suffix else 'unknown'

            if isinstance(allowed, str):
                target = ext.lower() == allowed
            elif isinstance(allowed, list):
                target = ext.lower() in allowed
            else:
                return jsonify("Invalid configuration item: '{}'".format(
                    'monitor.allowed')), 600

            if not target:
                return jsonify(
                    {"error": "File type '{}' not allowed".format(ext)}), 402

            # 安全文件名 + UUID 防冲突
            unique_name = '{}-{}'.format(uuid.uuid4().hex, filename)
            filepath = upload_folder / unique_name

            # 保存文件
            file.save(filepath)
            logger.info('File uploaded: {} (original: {})'.format(
                unique_name, filename))

            return jsonify({
                "message": "File uploaded successfully",
                "filename": unique_name
            }), 200
        else:
            logger.error('No file part in request')
            return jsonify({"error": "No file part in request"}), 400
    except Exception as e:
        logger.error('Upload failed: {}'.format(e))
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    # 仅用于开发调试，生产环境请用 Gunicorn
    app.run(host=host, port=port, debug=False)
