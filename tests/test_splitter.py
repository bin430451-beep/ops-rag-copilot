import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.rag.splitter import split_text
def test_short_text_single_chunk():
    chunks = split_text("hello world", chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
def test_long_text_multiple_chunks():
    text = "段落内容。" * 500
    chunks = split_text(text, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    assert all(len(c.text) <= 260 for c in chunks)
def test_markdown_headings_split():
    text = "## A\n内容A\n## B\n内容B\n## C\n内容C"
    chunks = split_text(text, chunk_size=12, chunk_overlap=0)
    assert len(chunks) >= 2
def test_empty_text():
    assert split_text("") == []
