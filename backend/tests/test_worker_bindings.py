import pytest
from starlette.requests import Request

from app.main import health


@pytest.mark.asyncio
async def test_health_does_not_coerce_worker_bindings_to_boolean(monkeypatch):
    class D1Binding:
        def __bool__(self):
            raise TypeError("Worker bindings cannot be coerced to bool")

    class WorkerEnv:
        CONVERSATIONS_DB = D1Binding()

    monkeypatch.delenv("HISTORY_DB_PATH", raising=False)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/health",
            "headers": [],
            "env": WorkerEnv(),
        }
    )
    response = await health(request)
    assert response["history_configured"] is True
