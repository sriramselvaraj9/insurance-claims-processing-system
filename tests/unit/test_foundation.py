from app import __version__
from app.core.config import settings
from app.main import app, health_check, root


def test_app_health_check_endpoint():
    """Verify health check logic returns healthy status and metadata."""
    payload = health_check()
    assert payload["status"] == "healthy"
    assert payload["service"] == settings.PROJECT_NAME
    assert payload["version"] == __version__
    assert payload["environment"] == settings.ENVIRONMENT


def test_app_root_endpoint():
    """Verify root endpoint returns correct documentation URLs."""
    payload = root()
    assert "docs_url" in payload
    assert "health_url" in payload
    assert payload["docs_url"] == f"{settings.API_V1_STR}/docs"


def test_app_openapi_metadata():
    """Verify FastAPI application instance metadata and configuration."""
    assert app.title == settings.PROJECT_NAME
    assert app.version == __version__
    assert app.docs_url == f"{settings.API_V1_STR}/docs"
    assert app.openapi_url == f"{settings.API_V1_STR}/openapi.json"


def test_config_settings_defaults():
    """Verify core configuration parameters and business rule thresholds."""
    assert settings.TIMELY_FILING_DAYS_LIMIT == 30
    assert settings.AUTO_APPROVAL_THRESHOLD == 2500.00
    assert settings.HIGH_VALUE_CLAIM_THRESHOLD == 50000.00
    assert settings.DEFAULT_EXPENSE_RATIO == 0.12
    assert settings.SYNTHETIC_DATA_RANDOM_SEED == 42
