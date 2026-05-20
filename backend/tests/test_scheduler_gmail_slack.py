import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_scheduler_registers_gmail_and_slack_jobs():
    from services.scheduler import BackgroundScheduler
    from services.data_ingestion import DataIngestionService

    di = MagicMock(spec=DataIngestionService)
    s = BackgroundScheduler(di)
    s.start()
    try:
        ids = {j.id for j in s.scheduler.get_jobs()}
        assert "sync_gmail" in ids
        assert "sync_slack" in ids
    finally:
        s.stop()
