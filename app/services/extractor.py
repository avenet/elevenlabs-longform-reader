import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_from_bytes(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only .txt and .pdf files are supported")

    if suffix == ".txt":
        for encoding in ("utf-8", "latin-1"):
            try:
                return normalize_whitespace(data.decode(encoding))
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode text file")

    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)
    text = normalize_whitespace("\n\n".join(pages))
    if not text:
        raise ValueError("No extractable text found in PDF")
    return text


def extract_from_text(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        raise ValueError("Text is empty")
    return cleaned
