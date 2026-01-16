#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: client.py
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-10-11 17:08:29

Description: 文件变化监视器 -- 监控指定类型文件的变动，将更新/新增的文件发往 Server 端
"""

import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import threading
import time

from logwrapper import get_logger
import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.config import scheduler
from utils.heartbeat import Heartbeat


class Monitor(FileSystemEventHandler):
    """文件变化监视器"""

    def __init__(self, config, logger):
        """初始化

        :config: 文件变化监视器配置
        :logger: 日志记录器
        """
        self.logger = logger

        # 读取配置
        host = config.get('host', '127.0.0.1')
        port = config.get('port', 1500)
        rule = config.get('rule', '/upload')
        self.allowed = config.get('allowed', [])

        client_conf = config.get('client', {})
        self.min_size = client_conf.get('min_size', 0.01)  # MB
        self.max_size = client_conf.get('max_size', 1)  # MB
        self.delay = client_conf.get('delay', 1.0)
        self.ttl = client_conf.get('ttl', 300)

        # 验证配置参数
        if self.min_size < 0:
            raise ValueError(
                "Configuration item 'monitor.client.min_size' must be non-negative"
            )
        if self.max_size <= 0:
            raise ValueError(
                "Configuration item 'monitor.client.max_size' must be positive"
            )
        if self.min_size > self.max_size:
            raise ValueError(
                "Configuration item 'monitor.client.min_size' must be less than or equal to 'monitor.client.max_size'"
            )
        if self.delay < 0:
            raise ValueError(
                "Configuration item 'monitor.client.delay' must be non-negative"
            )
        if self.ttl <= 0:
            raise ValueError(
                "Configuration item 'monitor.client.ttl' must be positive")

        # 缓存和锁
        self.uploaded_cache = {}  # 已上传文件缓存 {filepath: (md5_hash, timestamp)}
        self.cache_lock = threading.Lock()  # 用于控制缓存的互斥锁

        # 用于跟踪文件上传任务的定时器
        self.file_timers = {}  # 文件延迟上传定时器
        self.timer_lock = threading.Lock()  # 用于控制定时器的互斥锁

        self.url = url = 'http://{}:{}/{}'.format(host, port, rule)
        self.logger.info("File will be uploaded to '{}'".format(url))

    def on_created(self, event):
        """文件创建回调函数

        :event: watchdog.events.FileSystemEvent
        """
        if not event.is_directory:
            allowed = self._check_file(event)
            if allowed:
                filename = os.path.basename(event.src_path)
                self.logger.info("Add file '{}'".format(filename))
                self._schedule_upload(event.src_path)

    def on_modified(self, event):
        """文件修改回调函数

        :event: watchdog.events.FileSystemEvent
        """
        if not event.is_directory:
            allowed = self._check_file(event)
            if allowed:
                filename = os.path.basename(event.src_path)
                self.logger.info("Update file '{}'".format(filename))
                self._schedule_upload(event.src_path)

    def _check_file(self, event):
        """文件校验

        :event: watchdog.events.FileSystemEvent
        """
        file = event.src_path
        filename = os.path.basename(file)

        # 检查文件是否存在（防止文件新建时的临时文件干扰）
        if not os.path.exists(file):
            self.logger.debug(
                "File '{}' does not exist, skip".format(filename))
            return False

        try:
            filesize = os.path.getsize(file)
        except OSError as e:
            self.logger.debug("Could not get size of file '{}': {}".format(
                filename, e))
            return False

        min_size = self.min_size * 1024 * 1024
        max_size = self.max_size * 1024 * 1024

        ext = Path(file).suffix

        if isinstance(self.allowed, str):
            target = ext.lower() == self.allowed
        elif isinstance(self.allowed, list):
            target = ext.lower() in self.allowed
        else:
            self.logger.warning(
                "Invalid configuration item: '{}'".format('monitor.allowed'))
            return False

        if target:
            if min_size <= filesize <= max_size:
                return True
            else:
                self.logger.warning(
                    "File '{}' size '{}' exceeds the limit of [{}, {}] (MB), skip"
                    .format(filename, filesize, self.min_size, self.max_size))
                return False
        else:
            self.logger.info("File '{}' type '{}' not allowed".format(
                filename, ext))
            return False

    def _schedule_upload(self, filepath):
        """调度文件上传，延迟执行以避免重复上传

        :filepath: 文件路径
        """
        filepath = os.path.abspath(filepath)

        with self.timer_lock:
            # 取消已有的定时器
            if filepath in self.file_timers:
                self.file_timers[filepath].cancel()

            # 创建新的定时器，延迟执行上传
            timer = threading.Timer(self.delay,
                                    self._upload_file,
                                    args=[filepath])
            self.file_timers[filepath] = timer
            timer.start()

    def _cleanup_timer(self, filepath):
        """清理定时器记录

        :filepath: 文件路径
        """
        with self.timer_lock:
            if filepath in self.file_timers:
                del self.file_timers[filepath]

    def _upload_file(self, filepath):
        """上传文件

        :filepath: 文件路径
        """
        filepath = os.path.abspath(filepath)
        filename = os.path.basename(filepath)

        if not os.path.exists(filepath):
            self.logger.error(
                "File '{}' to be uploaded does not exist".format(filename))
            self._cleanup_timer(filepath)
            return

        try:
            with open(filepath, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.logger.warning("Failed to read file '{}': {}".format(
                filename, e))
            self._cleanup_timer(filepath)
            return

        now = time.time()
        with self.cache_lock:
            # 清理过期缓存
            to_remove = [
                fp for fp, (_, ts) in self.uploaded_cache.items()
                if now - ts > self.ttl
            ]
            for fp in to_remove:
                del self.uploaded_cache[fp]

            # 检查是否已上传相同内容
            if filepath in self.uploaded_cache:
                cached_hash, _ = self.uploaded_cache[filepath]
                if cached_hash == file_hash:
                    self.logger.debug(
                        "File '{}' has not been modified, skip".format(
                            filename))
                    self._cleanup_timer(filepath)
                    return

            # 执行上传
            try:
                # 根据文件扩展名确定 MIME 类型
                mime_type, _ = mimetypes.guess_type(filepath)
                if mime_type is None:
                    mime_type = 'application/octet-stream'

                with open(filepath, 'rb') as f:
                    files = {'file': (filename, f, mime_type)}
                    resp = requests.post(self.url, files=files, timeout=10)

                status = resp.status_code
                try:
                    text = json.loads(resp.text)
                except json.JSONDecodeError:
                    text = {'error': 'Invalid JSON response'}

                if status == 200:
                    self.logger.info(
                        "File '{}' uploaded success".format(filename))
                    self.uploaded_cache[filepath] = (file_hash, now)
                else:
                    self.logger.error(
                        "File '{}' uploaded failed: {} - {}".format(
                            filename, status, text.get('error',
                                                       'Unknown error')))
            except requests.exceptions.RequestException as e:
                self.logger.error("File '{}' upload request failed: {}".format(
                    filename, e))
            except Exception as e:
                self.logger.error("File '{}' uploaded exception: {}".format(
                    filename, e))

        self._cleanup_timer(filepath)


def main(config):
    """主函数：启动监控

    :config: 文件变化监视器配置
    """
    app_conf = config.get('app', {})
    name = app_conf.get('name', 'Change Monitor')
    version = app_conf.get('version', 'v0.0.0')

    # 初始化日志记录器
    logger_conf = config.get('logger', {})
    logger = get_logger(logfolder='logs', config=logger_conf)

    # 启动
    logger.info('Start {} {}'.format(name, version))

    monitor_conf = config.get('monitor', {})
    client_conf = monitor_conf.get('client', {})
    watch = client_conf.get('watch', 'cache')
    recursive = client_conf.get('recursive', False)
    interval = config.get('interval', 1.0)

    # 判断监控路径是否存在
    watch = Path(watch).resolve()
    if not watch.exists():
        logger.error("Monitoring path '{}' does not exist".format(watch))
        sys.exit(1)

    logger.info("Monitoring '{}'".format(watch))

    try:
        handler = Monitor(config=monitor_conf, logger=logger)
    except ValueError as e:
        logger.error("Configuration error: {}".format(e))
        sys.exit(1)

    observer = Observer()
    observer.schedule(handler, str(watch), recursive=bool(recursive))
    observer.start()

    # 启动心跳线程
    heartbeat_conf = config.get('heartbeat', {})
    heartbeat = Heartbeat(config=heartbeat_conf, logger=logger)
    heartbeat_thread = threading.Thread(target=heartbeat.start, daemon=True)
    heartbeat_thread.start()

    try:
        while True:
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info('Received interrupt signal, stopping {}'.format(name))
    finally:
        observer.stop()
        observer.join()
        heartbeat_thread.join(timeout=2)
        logger.info('Bye')


if __name__ == "__main__":
    conf = 'conf'
    confile = os.path.join(conf, 'app.toml')

    # 程序配置项
    config = scheduler(confile)

    main(config)
