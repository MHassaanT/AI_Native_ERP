import pytest

from erp.config import Settings


@pytest.fixture
def production_settings() -> dict[str, object]:
    return {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "SECRET_KEY": "a-production-secret-key-for-tests",
        "WEBHOOK_SIGNING_SECRET": "a-production-webhook-secret-for-tests",
        "DATABASE_URL": "postgresql://erp:strong-test-password@db:5432/erp",
    }


def test_production_starts_without_cors_origins(production_settings: dict[str, object]) -> None:
    with pytest.warns(RuntimeWarning, match="CORS_ALLOWED_ORIGINS is empty"):
        settings = Settings(**production_settings, CORS_ALLOWED_ORIGINS=[])

    assert settings.CORS_ALLOWED_ORIGINS == []


def test_production_rejects_wildcard_cors_origin(
    production_settings: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="must not contain a wildcard"):
        Settings(**production_settings, CORS_ALLOWED_ORIGINS=["*"])


def test_cors_origins_accepts_a_single_plain_origin(
    production_settings: dict[str, object],
) -> None:
    settings = Settings(
        **production_settings,
        CORS_ALLOWED_ORIGINS="https://ai-native-erp-rho.vercel.app",
    )

    assert settings.CORS_ALLOWED_ORIGINS == ["https://ai-native-erp-rho.vercel.app"]


def test_cors_origins_accepts_json_and_comma_separated_lists(
    production_settings: dict[str, object],
) -> None:
    json_settings = Settings(
        **production_settings,
        CORS_ALLOWED_ORIGINS='["https://erp.example.com/", "https://admin.example.com"]',
    )
    comma_settings = Settings(
        **production_settings,
        CORS_ALLOWED_ORIGINS="https://erp.example.com, https://admin.example.com",
    )

    assert json_settings.CORS_ALLOWED_ORIGINS == [
        "https://erp.example.com",
        "https://admin.example.com",
    ]
    assert comma_settings.CORS_ALLOWED_ORIGINS == [
        "https://erp.example.com",
        "https://admin.example.com",
    ]
