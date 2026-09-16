from fastapi import UploadFile

from app.config import settings


class InputLimitError(Exception):
    def __init__(self, message: str, *, status_code: int = 413):
        super().__init__(message)
        self.status_code = status_code


def allowed_content_types() -> set[str]:
    return {
        item.strip().lower() for item in settings.allowed_content_types.split(",") if item.strip()
    }


def validate_upload_content_type(content_type: str | None) -> None:
    if not content_type:
        return
    base = content_type.split(";", 1)[0].strip().lower()
    if base in allowed_content_types():
        return
    if base in {"application/octet-stream", "binary/octet-stream"}:
        return
    raise InputLimitError(
        "Unsupported content type. Allowed: text/plain, application/pdf.",
        status_code=400,
    )


def validate_text_size(text: str) -> None:
    if len(text) > settings.max_text_chars:
        raise InputLimitError(
            f"Pasted text exceeds the maximum of {settings.max_text_chars} characters."
        )


def validate_section_count(count: int) -> None:
    if count > settings.max_sections:
        raise InputLimitError(
            f"Document would produce {count} sections; maximum is {settings.max_sections}."
        )


async def read_upload_limited(upload: UploadFile) -> bytes:
    max_bytes = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise InputLimitError(f"Upload exceeds the maximum of {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)
