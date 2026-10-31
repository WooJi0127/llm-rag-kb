"""UTF-8 .md/.txt loading with deterministic character windows."""
import os
import re

CHUNK_SIZE = 240
CHUNK_OVERLAP = 40


def _chunk_text(text, source, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Stride=size-overlap; offsets count Python Unicode characters, not bytes."""
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError('chunk_size must be a positive integer')
    if type(overlap) is not int or not 0 <= overlap < chunk_size:
        raise ValueError('overlap must be an integer in [0, chunk_size)')
    text = text.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append((f'{source}#c{len(chunks)}', text[start:end]))
        if end == len(text):
            break
        start = end - overlap
    return chunks


def load_corpus(data_dir):
    """Flat directory, filename order; stable filename#cN IDs for unchanged files."""
    out = []
    if not os.path.isdir(data_dir):
        return out
    for fn in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, fn)
        if not fn.endswith(('.md', '.txt')) or not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            text = f.read()
        text = re.sub(r'^#+[^\S\n]*', '', text, flags=re.M)
        out.extend(_chunk_text(text, fn))
    return out
