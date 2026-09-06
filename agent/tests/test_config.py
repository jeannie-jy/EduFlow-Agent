from config import Settings


def test_minio_compose_credentials_are_accepted_by_host_api(monkeypatch):
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.setenv("MINIO_USER", "compose-access")
    monkeypatch.setenv("MINIO_PASSWORD", "compose-secret")

    settings = Settings(_env_file=None)

    assert settings.minio_access_key == "compose-access"
    assert settings.minio_secret_key == "compose-secret"


def test_video_script_compilation_is_deterministic_by_default():
    settings = Settings(_env_file=None)

    assert settings.manim_script_mode == "deterministic"
