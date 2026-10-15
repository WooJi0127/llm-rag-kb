#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag/generator.py — 答案生成

- 演示模式（默认，零依赖）：抽取式作答，从检索结果中挑出与问题相关的句子
- 大模型模式（USE_LLM=1）：把检索到的上下文送给本地 Ollama 生成答案
两种模式都基于同一套「检索增强」流程，区别仅在生成环节。
"""
import json
import os
import re
import urllib.request

from rag.retriever import tokenize

USE_LLM = os.environ.get("USE_LLM", "0") == "1"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

_SENT = re.compile(r"(?<=[。！？!?；;])\s*")


def _sentences(text):
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def demo_answer(query, hits):
    q_tokens = set(tokenize(query))
    picked = []
    sources = []
    for h in hits[:3]:
        src = h["id"].split("#")[0]
        if src not in sources:
            sources.append(src)
        for s in _sentences(h["text"]):
            if q_tokens & set(tokenize(s)):
                picked.append(s)
            if len(picked) >= 4:
                break
        if len(picked) >= 4:
            break
    if picked:
        answer = "。".join(picked[:4]) + "。"
    elif hits:
        answer = "。".join(_sentences(hits[0]["text"])[:2]) + "。（未精确命中关键词，以下是相关资料）"
    else:
        answer = "知识库中未找到相关内容，请尝试更换关键词，或向 data/ 目录补充文档。"
    return answer, sources, hits


def llm_answer(query, hits):
    context = "\n\n".join(h["text"] for h in hits[:4])
    prompt = (
        "你是一个严谨的中文问答助手。请仅根据下面的「参考资料」回答问题，不要编造；"
        "若资料不足以回答，请说明资料不足。\n\n"
        f"参考资料：\n{context}\n\n问题：{query}\n回答："
    )
    try:
        payload = json.dumps(
            {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
        ).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            ans = json.load(r).get("response", "").strip()
        sources = [h["id"].split("#")[0] for h in hits[:4]]
        return ans or demo_answer(query, hits)[0], sources, hits
    except Exception:
        return demo_answer(query, hits)


def generate(query, hits):
    if USE_LLM and hits:
        return llm_answer(query, hits)
    return demo_answer(query, hits)
