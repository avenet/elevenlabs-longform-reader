from __future__ import annotations

import logging

from elevenlabs.core.api_error import ApiError

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

RETRYING_MESSAGE = "Audio generation temporarily failed. Retrying."
FAILED_MESSAGE = "Audio generation failed."
VOICE_UNAVAILABLE_MESSAGE = "This voice is unavailable."
CONFIG_ERROR_MESSAGE = "Audio service configuration error."
INVALID_REQUEST_MESSAGE = "Audio generation request was invalid."
PDF_NO_TEXT_MESSAGE = "The uploaded PDF contains no extractable text."
EMPTY_UPLOAD_MESSAGE = "Uploaded file is empty."
EMPTY_TEXT_MESSAGE = "Text is empty."
UNSUPPORTED_FILE_MESSAGE = "Only .txt and .pdf files are supported."
DECODE_FAILED_MESSAGE = "Could not decode text file."
MISSING_INPUT_MESSAGE = "Provide either text or a .txt/.pdf file."
NO_SECTIONS_MESSAGE = "No readable sections found."
GENERIC_INTERNAL_MESSAGE = "Something went wrong. Please try again."
READING_NOT_FOUND_MESSAGE = "Reading not found."
AUDIO_NOT_READY_MESSAGE = "Audio not ready."

_INPUT_ERROR_MAP = {
    "no extractable text found in pdf": PDF_NO_TEXT_MESSAGE,
    "uploaded file is empty": EMPTY_UPLOAD_MESSAGE,
    "text is empty": EMPTY_TEXT_MESSAGE,
    "only .txt and .pdf files are supported": UNSUPPORTED_FILE_MESSAGE,
    "could not decode text file": DECODE_FAILED_MESSAGE,
    "provide either text or a .txt/.pdf file": MISSING_INPUT_MESSAGE,
    "no readable sections found": NO_SECTIONS_MESSAGE,
}


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RuntimeError):
        message = str(exc).lower()
        if "not configured" in message or "empty audio" in message:
            return False

    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True

    if httpx is not None and isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.TransportError,
        ),
    ):
        return True

    if isinstance(exc, ApiError):
        code = exc.status_code
        if code is None:
            return True
        if code == 429 or code >= 500:
            return True
        if code in {400, 401, 403, 404, 422}:
            return False
        return False

    return True


def user_facing_error(exc: BaseException, *, retrying: bool = False) -> str:
    if retrying:
        return RETRYING_MESSAGE

    if isinstance(exc, RuntimeError) and "not configured" in str(exc).lower():
        return CONFIG_ERROR_MESSAGE

    if isinstance(exc, ApiError):
        code = exc.status_code
        if code in {401, 403}:
            return CONFIG_ERROR_MESSAGE
        if code in {404, 422}:
            return VOICE_UNAVAILABLE_MESSAGE
        if code == 400:
            return INVALID_REQUEST_MESSAGE

    return FAILED_MESSAGE


def map_input_error(exc: BaseException) -> str:
    key = str(exc).strip().lower()
    if key in _INPUT_ERROR_MAP:
        return _INPUT_ERROR_MAP[key]
    for needle, message in _INPUT_ERROR_MAP.items():
        if needle in key:
            return message
    logger.warning("Unmapped input error: %s", type(exc).__name__)
    return GENERIC_INTERNAL_MESSAGE


def log_internal_error(exc: BaseException) -> None:
    logger.exception("Internal server error: %s", type(exc).__name__)
