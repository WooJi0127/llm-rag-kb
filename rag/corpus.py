#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag/corpus.py — 语料加载与分块

支持 .md / .txt；按段落切块，长段再做滑动窗口切分，便于精准检索。
"""
import os
import re

CHUNK_SIZE = 240     # 每块约 240 字
CHUNK_OVERLAP = 40

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*")


def _split_sentences(text):
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def _chunk_text(text, source):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    idx = 0
    buf = ""
    for para in paras:
        buf = (buf + "\n" + para).strip()
        if len(buf) >= CHUNK_SIZE:
            chunks.append((f"{source}#c{idx}", buf))
            idx += 1
            # 滑动窗口：保留重叠部分
            sentences = _split_sentences(buf)
            buf = "".join(sentences[-3:]) if sentences else ""
    if buf.strip():
        chunks.append((f"{source}#c{idx}", buf))
    return chunks


def load_corpus(data_dir):
    """返回 [(doc_id, text), ...]"""
    out = []
    if not os.path.isdir(data_dir):
        return out
    for fn in sorted(os.listdir(data_dir)):
        if not (fn.endswith(".md") or fn.endswith(".txt")):
            continue
        path = os.path.join(data_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # 去掉 markdown 标题符号噪声（保留内容）
        text = re.sub(r"^#+\s*", "", text, flags=re.M)
        out.extend(_chunk_text(text, fn))
    return out
