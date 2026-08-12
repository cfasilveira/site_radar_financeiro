# tests/test_realtime.py
"""Testes do stream em tempo real (SSE)"""
import asyncio
import pytest
from httpx import AsyncClient
from app.shared.security import security
from app.shared.database import db
from app.modules.realtime.manager import realtime


def _token(email: str, user_id: int, plano: str) -> str:
    return security.create_token(user_id, email, plano)


@pytest.mark.asyncio
async def test_stream_sem_token(client: AsyncClient):
    res = await client.get("/realtime/stream")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_stream_token_invalido(client: AsyncClient):
    res = await client.get("/realtime/stream?token=token-invalido")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_stream_plano_free_bloqueado(client: AsyncClient):
    token = _token("free@email.com", 999, "free")
    res = await client.get("/realtime/stream?token=" + token)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_stream_header_plano_premium(client: AsyncClient):
    """Stream SSE é infinito (não dá para ler o corpo via ASGITransport).
    Valida-se o registro/remoção da conexão no manager ao cancelar a tarefa."""
    token = _token("premium@email.com", 999, "premium")
    task = asyncio.create_task(
        client.get("/realtime/stream", headers={"Authorization": f"Bearer {token}"})
    )

    await asyncio.sleep(0.5)
    assert realtime.get_active_count() == 1

    task.cancel()
    for _ in range(100):
        await asyncio.sleep(0.05)
        if realtime.get_active_count() == 0:
            break
    assert realtime.get_active_count() == 0


@pytest.mark.asyncio
async def test_status(client: AsyncClient):
    res = await client.get("/realtime/status")
    assert res.status_code == 200
    assert res.json() == {"conexoes_ativas": 0, "status": "online"}


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["env"] == "test"


@pytest.mark.asyncio
async def test_index_serve_templates(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    assert "Radar de Finanças" in res.text
    assert "gate de login" in res.text or "metricsChart" in res.text