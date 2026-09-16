from app.services.tts import build_cache_key, normalize_for_cache


def test_same_normalized_text_same_key():
    a = build_cache_key("voice", "model", "Hello   world\n\nthere")
    b = build_cache_key("voice", "model", "Hello world there")
    assert normalize_for_cache("Hello   world\n\nthere") == "Hello world there"
    assert a == b


def test_different_voice_model_or_text_different_key():
    base = build_cache_key("voice-a", "model-a", "same text")
    assert build_cache_key("voice-b", "model-a", "same text") != base
    assert build_cache_key("voice-a", "model-b", "same text") != base
    assert build_cache_key("voice-a", "model-a", "other text") != base
