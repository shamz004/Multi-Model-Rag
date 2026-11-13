"""PDF text extraction and chunking. Chunks never cross a page boundary so
every chunk can be cited with an exact page number."""

import re
import unicodedata

import pymupdf as fitz


class PdfError(Exception):
    pass


def clean_text(text: str) -> str:
    # NFKC expands ligatures (the single-glyph "fi", "fl") and odd spaces that PDFs
    # often contain; without it keyword search would miss words such as "financial".
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "").replace("\u00ad", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated at line ends
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    # Single newlines are layout line-wraps; blank lines are paragraph breaks.
    paragraphs = [re.sub(r"\n", " ", p).strip() for p in re.split(r"\n{2,}", text)]
    return "\n\n".join(p for p in paragraphs if p)


def parse_pdf(path) -> list[dict]:
    """Returns [{'page': 1-based page number, 'text': cleaned text}] for every page."""
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PdfError(f"Could not open PDF: {exc}") from exc
    try:
        if doc.needs_pass:
            raise PdfError("PDF is password-protected.")
        pages = []
        for number, page in enumerate(doc, start=1):
            blocks = page.get_text("blocks", sort=True)
            text = "\n\n".join(b[4].strip() for b in blocks if b[6] == 0 and b[4].strip())
            pages.append({"page": number, "text": clean_text(text)})
        return pages
    finally:
        doc.close()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n{2,}", text)
    return [p.strip() for p in parts if p and p.strip()]


def _hard_split(piece: str, size: int) -> list[str]:
    """Splits an over-long sentence (e.g. a table dump) on word boundaries."""
    out, current = [], ""
    for word in piece.split(" "):
        while len(word) > size:
            if current:
                out.append(current)
                current = ""
            out.append(word[:size])
            word = word[size:]
        if current and len(current) + 1 + len(word) > size:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        out.append(current)
    return out


def _join(pieces: list[tuple[str, str]]) -> str:
    """Joins (separator, text) pieces; the first piece's separator is dropped."""
    return "".join(sep + text for sep, text in pieces)[1:] if pieces else ""


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Packs whole sentences into chunks of at most `size` characters. The last
    sentences of each chunk are repeated at the start of the next (`overlap`),
    so a fact that straddles a boundary is still found intact in one chunk.
    Paragraph breaks are kept as newlines, which keeps table rows on their own lines."""
    pieces: list[tuple[str, str]] = []  # (separator before the piece, text)
    for paragraph in re.split(r"\n{2,}", text):
        first = True
        for sentence in split_sentences(paragraph):
            for part in _hard_split(sentence, size) if len(sentence) > size else [sentence]:
                pieces.append(("\n" if first else " ", part))
                first = False

    chunks: list[str] = []
    current: list[tuple[str, str]] = []
    length = 0
    for piece in pieces:
        if current and length + 1 + len(piece[1]) > size:
            chunks.append(_join(current))
            # Carry trailing sentences forward as overlap.
            carried: list[tuple[str, str]] = []
            carried_len = 0
            for prev in reversed(current):
                if carried_len + len(prev[1]) > overlap:
                    break
                carried.insert(0, prev)
                carried_len += len(prev[1]) + 1
            if carried_len + len(piece[1]) > size:
                carried, carried_len = [], 0
            current, length = carried, max(carried_len - 1, 0)
        current.append(piece)
        length += len(piece[1]) + (1 if length else 0)
    if current:
        chunks.append(_join(current))
    return chunks


def chunk_pages(pages: list[dict], size: int, overlap: int) -> list[dict]:
    chunks: list[dict] = []
    for page in pages:
        for text in chunk_text(page["text"], size, overlap):
            chunks.append({"page": page["page"], "chunk_index": len(chunks), "text": text})
    return chunks
