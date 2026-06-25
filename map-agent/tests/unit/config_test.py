"""Configuration helper tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.config as config


def test_maps_api_key_uses_regional_secret_when_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(config, "_cached_maps_api_key", None)
    monkeypatch.setattr(config, "GOOGLE_CLOUD_PROJECT", "project-id")
    monkeypatch.setattr(config, "_MAPS_SECRET_NAME", "google_map_api_key")
    monkeypatch.setattr(config, "_MAPS_SECRET_LOCATION", "us-central1")
    monkeypatch.setattr(config, "_MAPS_SECRET_RESOURCE", "")

    client = MagicMock()
    client.access_secret_version.return_value = SimpleNamespace(
        payload=SimpleNamespace(data=b"maps-test-key")
    )

    with patch(
        "google.cloud.secretmanager.SecretManagerServiceClient",
        return_value=client,
    ):
        assert config.get_google_maps_api_key() == "maps-test-key"

    client.access_secret_version.assert_called_once_with(
        request={
            "name": (
                "projects/project-id/locations/us-central1/"
                "secrets/google_map_api_key/versions/latest"
            )
        }
    )


def test_maps_api_key_prefers_direct_environment_value(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "direct-key")
    monkeypatch.setattr(config, "_cached_maps_api_key", None)

    assert config.get_google_maps_api_key() == "direct-key"
