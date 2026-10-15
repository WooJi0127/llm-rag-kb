#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag/retriever.py — 零依赖 BM25 检索（中文按字、英文按词）

不依赖任何第三方库即可完成「检索增强」的 Retriever 部分。
若想换成 Chroma / FAISS，只需替换本模块的实现，接口保持一致。
"""
import math
import re
from collections import defaultdict


def tokenize(text):
    """中文按单字切分，英文/数字按词切分。"""
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    cjk = re.findall(r"[一-鿿]", text)
    return tokens + cjk


class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = []        # 每个文档的 token 列表
        self.doc_ids = []
        self.doc_texts = []
        self.df = defaultdict(int)
        self.N = 0
        self.avgdl = 0.0
        self.idf = {}

    def add(self, doc_id, text):
        toks = tokenize(text)
        self.docs.append(toks)
        self.doc_ids.append(doc_id)
        self.doc_texts.append(text)
        for t in set(toks):
            self.df[t] += 1
        self.N += 1

    def build(self):
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.N)
        for t, df in self.df.items():
            self.idf[t] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def search(self, query, topk=5):
        q = tokenize(query)
        if not q:
            return []
        results = []
        for i, toks in enumerate(self.docs):
            freq = defaultdict(int)
            for t in toks:
                freq[t] += 1
            score = 0.0
            dl = len(toks)
            for term in q:
                if term in self.idf:
                    f = freq[term]
                    score += self.idf[term] * (
                        f * (self.k1 + 1)
                        / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                    )
            if score > 0:
                results.append((score, i))
        results.sort(reverse=True)
        return [
            {"id": self.doc_ids[i], "text": self.doc_texts[i], "score": round(s, 4)}
            for s, i in results[:topk]
        ]
