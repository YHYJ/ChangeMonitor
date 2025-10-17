# README

<!-- File: README.md -->
<!-- Author: YJ -->
<!-- Email: yj1516268@outlook.com -->
<!-- Created Time: 2025-10-13 11:09:26 -->

---

## Table of Contents

<!-- vim-markdown-toc GFM -->

* [概述](#概述)
* [功能](#功能)
* [编译](#编译)

<!-- vim-markdown-toc -->

---

<!-- Object info -->

---

## 概述

- ChangeMonitor 采用 CS 架构
- server.py 和 client.py 是两个主要文件，统一由 conf/app.toml 配置

## 功能

- client.py 用于监控文件变化，当文件更新/新建时，会自动将该文件发送到 server.py 启动的文件服务
- server.py 用于提供文件服务，接收 client.py 发来的文件，将文件保存到指定目录
- conf/app.toml 是配置文件
- server.sh 是启动 server.py 的脚本，用于生产环境，调试时用命令`python server.py` 即可

## 编译

```bash
pyinstaller --onefile --clean client.py
```
