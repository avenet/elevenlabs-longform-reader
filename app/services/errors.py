from __future__ import annotations

from elevenlabs.core.api_error import ApiError

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


RETRYING_MESSAGE = "Audio generation temporarily failed. Retrying."
FAILED_MESSAGE = "Audio generation failed."
VOICE_UNAVAILABLE_MESSAGE = "This voice is unavailable."
CONFIG_ERROR_MESSAGE = "Audio service configuration error."
INVALID_REQUEST_MESSAGE = "Audio generation request was invalid."


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
