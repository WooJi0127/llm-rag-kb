#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm-rag-kb 启动入口

用法：
    python run.py                  # 启动 Web 对话（零依赖 Demo 模式）
    python run.py ask "什么是 MQTT" # 命令行问答
    USE_LLM=1 python run.py        # 启用本地 Ollama 生成（需先装并运行 Ollama）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import serve, ask, build_index

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ask":
        q = " ".join(sys.argv[2:]).strip()
        if not q:
            print("用法: python run.py ask \"你的问题\"")
            sys.exit(1)
        build_index()
        res = ask(q)
        print(f"\n[模式] {res['mode']}  [来源] {', '.join(res['sources']) or '无'}")
        print(f"[回答] {res['answer']}")
    else:
        serve()
