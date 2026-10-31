"""Offline document-level retrieval evaluation; never evaluates generated answers."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.corpus import load_corpus
from rag.retriever import BM25, validate_topk


def metrics(rows, k):
    """Deduplicate chunk hits to documents before applying k."""
    validate_topk(k)
    recalls, reciprocal = [], []
    answerable_zero = unanswerable_zero = unanswerable = zero = 0
    for row in rows:
        ranked = list(dict.fromkeys(i.rsplit('#c', 1)[0] for i in row['ranked']))[:k]
        relevant = set(row['relevant'])
        if not ranked:
            zero += 1
        if relevant:
            recalls.append(len(relevant.intersection(ranked)) / len(relevant))
            reciprocal.append(next((1 / rank for rank, doc in enumerate(ranked, 1) if doc in relevant), 0))
            answerable_zero += not ranked
        else:
            unanswerable += 1
            unanswerable_zero += not ranked
    return {
        'k': k, 'queries': len(rows), 'answerable_queries': len(recalls),
        'unanswerable_queries': unanswerable,
        'recall': sum(recalls) / len(recalls) if recalls else 0,
        'mrr': sum(reciprocal) / len(reciprocal) if reciprocal else 0,
        'zero_hit_total': zero, 'answerable_zero_hits': answerable_zero,
        'unanswerable_zero_hits': unanswerable_zero,
    }


def evaluate(k=3):
    bm = BM25()
    for did, text in load_corpus(ROOT / 'evaluation' / 'corpus'):
        bm.add(did, text)
    bm.build()
    queries = json.loads((ROOT / 'evaluation' / 'queries.json').read_text(encoding='utf-8'))
    # Rank all chunks via the unchanged public interface in this small fixture (<=20).
    if bm.N > 20:
        raise ValueError('evaluation fixture exceeds 20 chunks; add an explicit all-hit ranking interface first')
    rows = [{**q, 'ranked': [h['id'] for h in bm.search(q['query'], 20)]} for q in queries]
    return {
        'documents': len({i.rsplit('#c', 1)[0] for i in bm.doc_ids}),
        'chunks': bm.N, 'chunk_size': 240, 'overlap': 40,
        'bm25': {'k1': bm.k1, 'b': bm.b},
        'overall': metrics(rows, k),
        'groups': {g: metrics([r for r in rows if r['group'] == g], k)
                   for g in sorted({r['group'] for r in rows})},
        'rows': rows,
    }


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=3)
    options = parser.parse_args()
    print(json.dumps(evaluate(options.k), ensure_ascii=False, indent=2))
