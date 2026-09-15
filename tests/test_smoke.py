def test_settings_load_isolated_environment():
    from app.config import settings

    assert settings.elevenlabs_api_key == "test-key"
    assert "reader-tests-" in settings.media_root


def test_app_imports():
    from app.main import app

    assert app.title
