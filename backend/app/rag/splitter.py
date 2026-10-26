"""轻量递归字符切分，无重依赖，方便测试与替换。"""
from dataclasses import dataclass
DEFAULT_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", "。", "；", " ", ""]
@dataclass
class Chunk:
    text: str
    index: int
def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    separators: list[str] | None = None,
) -> list[Chunk]:
    text = (text or "").strip()
    if not text:
        return []
    separators = separators or DEFAULT_SEPARATORS
    pieces = _recursive_split(text, separators, chunk_size)
    merged = _merge(pieces, chunk_size, chunk_overlap)
    return [Chunk(text=c, index=i) for i, c in enumerate(merged)]
def _recursive_split(text: str, separators: list[str], size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    for sep in separators:
        if sep == "":
            continue
        if sep in text:
            parts = text.split(sep)
            out: list[str] = []
            for i, p in enumerate(parts):
                piece = p + (sep if i < len(parts) - 1 else "")
                if not piece.strip():
                    continue
                if len(piece) <= size:
                    out.append(piece)
                else:
                    next_seps = separators[separators.index(sep) + 1:]
                    out.extend(_recursive_split(piece, next_seps, size))
            return out
    return [text[i:i + size] for i in range(0, len(text), size)]
def _merge(pieces: list[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    buf = ""
    for p in pieces:
        if len(buf) + len(p) <= size:
            buf += p
        else:
            if buf.strip():
                chunks.append(buf.strip())
            tail = buf[-overlap:] if overlap and len(buf) > overlap else ""
            buf = tail + p
    if buf.strip():
        chunks.append(buf.strip())
    return chunks
