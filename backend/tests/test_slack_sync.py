from unittest.mock import patch, MagicMock
from services.slack_sync import SlackSync


@patch("services.slack_sync.httpx.post")
def test_exchange_code_success(mock_post):
    mock_post.return_value = MagicMock(
        json=lambda: {
            "ok": True,
            "access_token": "xoxb-token",
            "team": {"name": "Test Team"},
        },
        raise_for_status=lambda: None,
    )
    sync = SlackSync()
    tokens = sync.exchange_code_for_tokens("auth_code")
    assert tokens["access_token"] == "xoxb-token"


@patch("services.slack_sync.httpx.get")
def test_fetch_messages_returns_list(mock_get):
    channels_response = MagicMock(
        json=lambda: {"ok": True, "channels": [{"id": "C123", "name": "general"}]},
        raise_for_status=lambda: None,
    )
    history_response = MagicMock(
        json=lambda: {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "text": "Hello team!",
                    "ts": "1234567890.000",
                    "user": "U123",
                }
            ],
        },
        raise_for_status=lambda: None,
    )
    mock_get.side_effect = [channels_response, history_response]

    sync = SlackSync()
    msgs = sync.fetch_messages("xoxb-token", max_channels=1, max_messages_per_channel=5)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "Hello team!"
    assert msgs[0]["channel"] == "general"
