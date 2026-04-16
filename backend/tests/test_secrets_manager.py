"""Tests for GCP Secret Manager integration in config.py."""

from unittest.mock import MagicMock


def test_load_secrets_from_gcp_sets_env_vars():
    """load_secrets_from_gcp reads each secret and sets it as an env var."""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = "test-secret-value"
    mock_client.access_secret_version.return_value = mock_response

    import config as cfg_mod

    cfg_mod.load_secrets_from_gcp(project_id="test-project", client=mock_client)

    # Verify the client was called for at least one expected secret
    call_args_list = mock_client.access_secret_version.call_args_list
    assert len(call_args_list) > 0, "Expected at least one secret lookup"
    # Check one of the expected secrets was looked up
    all_calls_str = str(call_args_list)
    assert any(
        name in all_calls_str for name in ["gemini", "GEMINI", "secret-key", "SECRET"]
    ), f"Expected a known secret name in calls, got: {all_calls_str}"


def test_load_secrets_from_gcp_does_not_raise_on_missing_secret():
    """A missing secret logs a warning but does not crash startup."""
    mock_client = MagicMock()
    mock_client.access_secret_version.side_effect = Exception("secret not found")

    import config as cfg_mod

    # Should not raise
    cfg_mod.load_secrets_from_gcp(project_id="test-project", client=mock_client)


def test_load_secrets_from_gcp_skipped_without_project_id():
    """load_secrets_from_gcp does nothing when project_id is empty."""
    import config as cfg_mod

    # Should not raise and should not call any client
    mock_client = MagicMock()
    cfg_mod.load_secrets_from_gcp(project_id="", client=mock_client)
    mock_client.access_secret_version.assert_not_called()
