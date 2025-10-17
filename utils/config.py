#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: config.py
Author: YJ
Email: yj1516268@outlook.com
Created Time: 2025-03-25 08:05:23

Description: 读取结构化配置文件

由主文件 main.py 调用获取配置信息并传给其他模块
"""

import json
import os

import toml


def scheduler(confile: str):
    """结构化配置文件调度器
    目前支持 toml 和 json 格式

    :confile: 配置文件路径
    """
    # 检查文件是否存在
    if not os.path.isfile(confile):
        raise Exception("配置文件未找到: {}".format(confile))

    # 获取文件扩展名并转换为小写
    _, ext = os.path.splitext(confile)
    extension = ext.lower()

    try:
        if extension == '.toml':
            return toml.load(confile)
        elif extension == '.json':
            with open(confile, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise Exception("不支持的配置文件格式: {}".format(extension))
    except Exception as e:
        raise e




if __name__ == "__main__":
    toml_file = "../conf/app.toml"
    json_file = "../cache/access.json"

    try:
        toml_conf = scheduler(toml_file)
        json_conf = scheduler(json_file)
        print("TOML 文件内容 ({})：{}".format(type(toml_conf), toml_conf))
        print()
        print("JSON 文件内容 ({})：{}".format(type(json_conf), json_conf))
    except Exception as e:
        raise e
