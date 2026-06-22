"""
Unit tests for app.core.tasks — no real Redis/arq worker needed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks

from app.core.tasks import enqueue_email, send_email_task


class TestEnqueueEmail:
    @pytest.mark.asyncio
    async def test_falls_back_to_background_tasks_when_redis_disabled(self):
        bg = BackgroundTasks()
        with patch("app.core.tasks.settings") as mock_settings:
            mock_settings.REDIS_ENABLED = False
            await enqueue_email(bg, to="a@b.com", subject="Hi", body_html="<p>hi</p>")

        assert len(bg.tasks) == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_background_tasks_when_redis_unreachable(self):
        """Even with REDIS_ENABLED=True, a connection failure at enqueue
        time must fail open to BackgroundTasks rather than losing the
        email entirely."""
        bg = BackgroundTasks()
        with patch("app.core.tasks.settings") as mock_settings:
            mock_settings.REDIS_ENABLED = True
            mock_settings.REDIS_URL = "redis://nonexistent-host-for-test:6379/0"
            await enqueue_email(bg, to="a@b.com", subject="Hi", body_html="<p>hi</p>")

        assert len(bg.tasks) == 1

    @pytest.mark.asyncio
    async def test_uses_arq_pool_when_redis_enabled_and_reachable(self):
        """Confirms the arq path is actually taken (and BackgroundTasks is
        NOT used) when enqueueing succeeds — mocking the pool rather than
        requiring a real Redis instance in the test environment."""
        bg = BackgroundTasks()
        mock_pool = AsyncMock()

        with patch("app.core.tasks.settings") as mock_settings, \
                patch("arq.create_pool", new=AsyncMock(return_value=mock_pool)):
            mock_settings.REDIS_ENABLED = True
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            await enqueue_email(bg, to="a@b.com", subject="Hi", body_html="<p>hi</p>")

        mock_pool.enqueue_job.assert_called_once_with(
            "send_email_task", "a@b.com", "Hi", "<p>hi</p>",
        )
        mock_pool.aclose.assert_called_once()
        assert len(bg.tasks) == 0  # arq path succeeded — no fallback needed


class TestSendEmailTask:
    @pytest.mark.asyncio
    async def test_calls_send_email_and_returns_its_result(self):
        with patch("app.core.tasks.send_email", new=AsyncMock(return_value=True)) as mock_send:
            result = await send_email_task({}, "a@b.com", "Subject", "<p>body</p>")

        assert result is True
        mock_send.assert_called_once_with(to="a@b.com", subject="Subject", body_html="<p>body</p>")
