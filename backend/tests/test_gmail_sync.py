from unittest.mock import patch, MagicMock
from services.gmail_sync import GmailSync


@patch('services.gmail_sync.build')
@patch('services.gmail_sync.Credentials')
def test_fetch_messages_returns_list(mock_creds_cls, mock_build):
    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds_cls.return_value = mock_creds

    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.users().messages().list().execute.return_value = {
        'messages': [{'id': 'msg-1'}]
    }
    mock_service.users().messages().get().execute.return_value = {
        'snippet': 'Hello world',
        'payload': {'headers': [
            {'name': 'Subject', 'value': 'Test subject'},
            {'name': 'From', 'value': 'sender@example.com'},
            {'name': 'Date', 'value': 'Mon, 1 Jan 2025'},
        ]}
    }

    sync = GmailSync()
    messages = sync.fetch_messages('token', 'refresh')
    assert len(messages) == 1
    assert messages[0]['subject'] == 'Test subject'
    assert messages[0]['snippet'] == 'Hello world'
