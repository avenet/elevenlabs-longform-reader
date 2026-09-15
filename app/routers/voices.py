from fastapi import APIRouter

from app.config import settings
from app.schemas import VoiceOut
from app.services.tts import list_voices

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("", response_model=list[VoiceOut])
def get_voices() -> list[VoiceOut]:
    try:
        voices = list_voices()
        if voices:
            return [VoiceOut(**voice) for voice in voices]
    except Exception:
        pass

    return [
        VoiceOut(
            voice_id=settings.elevenlabs_voice_id,
            name="Default voice",
            preview_url=None,
        )
    ]
