"""轻量 BM25 检索器 + RRF 融合（无第三方依赖，用于混合检索增强长尾命中）。"""
import logging
import math
import re
log = logging.getLogger(__name__)

_CJK = re.compile(r"[\u4e00-\u9fff]")
_WORD = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    """中英混合分词：英文按单词，中文按单字 + bigram。"""
    text = (text or "").lower()
    tokens: list[str] = _WORD.findall(text)
    cjk_str = "".join(_CJK.findall(text))
    if cjk_str:
        tokens.extend(cjk_str)  # 单字
        tokens.extend(cjk_str[i:i + 2] for i in range(len(cjk_str) - 1))  # bigram
    return tokens


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._term_freq: dict[str, dict[str, int]] = {}   # term -> {point_id: count}
        self._doc_len: dict[str, int] = {}
        self._doc_freq: dict[str, int] = {}
        self._total_docs = 0
        self._avgdl = 0.0

    def add_document(self, point_id: str, text: str) -> None:
        terms = tokenize(text)
        if not terms:
            return
        counts: dict[str, int] = {}
        for t in terms:
            counts[t] = counts.get(t, 0) + 1
        for t, c in counts.items():
            if t not in self._term_freq:
                self._term_freq[t] = {}
                self._doc_freq[t] = 0
            if point_id not in self._term_freq[t]:
                self._term_freq[t][point_id] = 0
                self._doc_freq[t] += 1
            self._term_freq[t][point_id] += c
        self._doc_len[point_id] = len(terms)

    def build(self) -> None:
        if not self._doc_len:
            log.warning("BM25 index empty")
            return
        self._total_docs = len(self._doc_len)
        self._avgdl = sum(self._doc_len.values()) / self._total_docs
        log.info("BM25 index built: %d docs, avgdl=%.1f", self._total_docs, self._avgdl)

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if self._total_docs == 0:
            return []
        terms = tokenize(query)
        if not terms:
            return []
        scores: dict[str, float] = {}
        for t in set(terms):
            df = self._doc_freq.get(t, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._total_docs - df + 0.5) / (df + 0.5))
            for pid, f in self._term_freq.get(t, {}).items():
                dl = self._doc_len.get(pid, 0) or 1
                tf_part = (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                )
                scores[pid] = scores.get(pid, 0.0) + idf * tf_part
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def rrf_fuse(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion：按 point_id 融合多路召回。"""
    fused: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            pid = item.get("point_id")
            if not pid:
                continue
            if pid not in fused:
                fused[pid] = dict(item)
                fused[pid]["rrf_score"] = 0.0
            fused[pid]["rrf_score"] += 1.0 / (k + rank + 1)
    return sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
