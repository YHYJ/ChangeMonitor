#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: heartbeat.py
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-04-23 09:33:30

Description: 提供心跳信息
"""

from datetime import datetime
import threading


class Heartbeat:

    def __init__(self, config, logger):
        """初始化

        :config: 心跳信息配置
        :logger: 日志记录器
        """
        self.logger = logger
        self.interval = config.get('interval', 3600)
        self.with_timestamp = config.get('with_timestamp', True)
        self._stop_event = threading.Event()

    def start(self):
        """启动心跳（后台线程）"""
        while not self._stop_event.is_set():
            msg = {'status': 'alive'}
            if self.with_timestamp:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                msg['timestamp'] = timestamp
            self.logger.info("Heartbeat: {}".format(msg))
            self._stop_event.wait(timeout=self.interval)

    def stop(self):
        """停止心跳"""
        self._stop_event.set()
