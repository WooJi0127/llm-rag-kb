#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm-rag-kb · 应用入口（CLI + 零依赖 Web UI）

检索：自研 BM25（中文按字/英文按词）
生成：默认「抽取式演示」零依赖；设 USE_LLM=1 走本地 Ollama 真·RAG 生成
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.retriever import BM25, validate_topk
from rag.corpus import load_corpus
from rag.generator import generate_result, USE_LLM

PORT = int(os.environ.get("RAG_PORT", "8002"))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("RAG_DATA", os.path.join(HERE, "data"))

_bm = None


def build_index(data_dir=DATA_DIR):
    global _bm
    bm = BM25()
    docs = load_corpus(data_dir)
    for did, text in docs:
        bm.add(did, text)
    bm.build()
    _bm = bm
    return len(docs)


def ask(query, topk=5):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("q must be a nonempty string of at most 2000 characters")
    query.encode('utf-8')  # Reject unpaired JSON surrogate escapes before generation.
    validate_topk(topk)
    query = query.strip()
    if _bm is None:
        build_index()
    hits = _bm.search(query, topk)
    result = generate_result(query, hits)
    return {
        "query": query,
        **result,
        "hits": [{"id": h["id"], "score": h["score"]} for h in hits],
        "doc_count": _bm.N if _bm else 0,
    }


def _chat_html():
    path = os.path.join(HERE, "dashboard", "chat.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, _chat_html(), "text/html; charset=utf-8")
        elif parsed.path == "/health":
            self._send(200, json.dumps({"doc_count": _bm.N if _bm else 0, "mode": "llm" if USE_LLM else "demo", "mode_is_configured": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urlparse(self.path).path != "/ask":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Transfer-Encoding is not supported")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise ValueError("valid Content-Length required")
            length = int(lengths[0])
            if length > 65536:
                self._send(413, json.dumps({"error": "request body exceeds 64 KiB"}))
                return
            self.connection.settimeout(5)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete request body")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            q = payload.get("q")
            topk = payload.get("topk", 5)
            if not isinstance(q, str) or not q.strip() or len(q) > 2000:
                raise ValueError("q must be a nonempty string of at most 2000 characters")
            q.encode('utf-8')
            validate_topk(topk)
        except (ValueError, UnicodeError, RecursionError) as e:
            self._send(400, json.dumps({"error": str(e)}))
            return
        except OSError:
            self._send(408, json.dumps({"error": "request body timed out"}))
            return
        try:
            self._send(200, json.dumps(ask(q, topk), ensure_ascii=False))
        except Exception:
            self._send(500, json.dumps({"error": "internal server error"}))

    def log_message(self, *args):
        pass


def serve():
    build_index()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[llm-rag-kb] 本地知识库已启动（模式: {'LLM' if USE_LLM else 'Demo'}）")
    print(f"  对话:  http://localhost:{PORT}/")
    print(f"  接口:  POST http://localhost:{PORT}/ask  {{\"q\": \"你的问题\"}}")
    print(f"  语料:  {DATA_DIR}（{_bm.N} 个文本块）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    serve()
