#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag/retriever.py — 零依赖 BM25 检索（中文按字、英文按词）

不依赖任何第三方库即可完成「检索增强」的 Retriever 部分。
若想换成 Chroma / FAISS，只需替换本模块的实现，接口保持一致。
"""
import math
import re
from collections import Counter, defaultdict


def validate_topk(topk):
    if type(topk) is not int or not 1 <= topk <= 20:
        raise ValueError('topk must be an integer from 1 to 20')


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
        self.frequencies = []
        self.lengths = []
        self._dirty = False
        self.doc_ids = []
        self.doc_texts = []
        self.df = defaultdict(int)
        self.N = 0
        self.avgdl = 0.0
        self.idf = {}

    def add(self, doc_id, text):
        toks = tokenize(text)
        self.docs.append(toks)
        self.frequencies.append(Counter(toks))
        self.lengths.append(len(toks))
        self._dirty = True
        self.doc_ids.append(doc_id)
        self.doc_texts.append(text)
        for t in set(toks):
            self.df[t] += 1
        self.N += 1

    def build(self):
        self.avgdl = sum(self.lengths) / max(1, self.N)
        for t, df in self.df.items():
            self.idf[t] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))
        self._dirty = False

    def search(self, query, topk=5):
        validate_topk(topk)
        if self._dirty:
            self.build()
        q = tokenize(query)
        if not q or not self.avgdl:
            return []
        results = []
        for i, freq in enumerate(self.frequencies):
            score = 0.0
            dl = self.lengths[i]
            for term in q:
                if term in self.idf:
                    f = freq[term]
                    score += self.idf[term] * (
                        f * (self.k1 + 1)
                        / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                    )
            if score > 0:
                results.append((score, i))
        results.sort(key=lambda item: (-item[0], item[1]))
        return [
            {"id": self.doc_ids[i], "text": self.doc_texts[i], "score": round(s, 4)}
            for s, i in results[:topk]
        ]
