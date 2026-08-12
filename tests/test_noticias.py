# tests/test_noticias.py
"""Testes do módulo de manchetes (exige login) e plano premium"""
import pytest
from httpx import AsyncClient
from app.shared.security import security
from app.modules.noticias import service as noticias_service


def _token(user_id: int = 1, plano: str = "free") -> str:
    return security.create_token(user_id, "userteste@email.com", plano)


@pytest.mark.asyncio
async def test_manchetes_sem_login(client: AsyncClient):
    """Sem token o acesso às manchetes deve ser negado"""
    res = await client.get("/noticias/manchetes")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_manchetes_token_invalido(client: AsyncClient):
    res = await client.get("/noticias/manchetes?token=invalido")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_manchetes_com_login_mock(client: AsyncClient, monkeypatch):
    """Com login, retorna headlines estruturadas por fonte"""
    fake = {
        "fonte": "RSS",
        "data_referencia": "2026-08-12",
        "total_headlines": 2,
        "por_fonte": {
            "Valor Econômico": [{"titulo": "Headline Valor", "fonte": "Valor Econômico", "link": "https://valor.globo.com", "publicado_em": ""}],
            "Bloomberg": [{"titulo": "Headline Bloomberg", "fonte": "Bloomberg", "link": "https://bloomberg.com", "publicado_em": ""}],
        },
        "atualizado_em": "2026-08-12T00:00:00",
    }
    async def _fake_manchetes(refresh=False):
        return fake

    monkeypatch.setattr(noticias_service.service, "manchetes", _fake_manchetes)
    token = _token()
    res = await client.get(
        "/noticias/manchetes", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_headlines"] == 2
    assert "Valor Econômico" in data["por_fonte"]
    assert data["por_fonte"]["Valor Econômico"][0]["titulo"] == "Headline Valor"


@pytest.mark.asyncio
async def test_servico_manchetes_mock(monkeypatch):
    """Testa o parser RSS com XML de exemplo"""
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
        <item><title>Notícia 1</title><link>https://exemplo.com/1</link><pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate></item>
        <item><title>Notícia 2</title><link>https://exemplo.com/2</link></item>
    </channel></rss>"""
    items = noticias_service._parse_rss(xml, "Teste", "Teste")
    assert len(items) == 2
    assert items[0]["titulo"] == "Notícia 1"
    assert items[0]["link"] == "https://exemplo.com/1"
    assert items[0]["fonte"] == "Teste"


@pytest.mark.asyncio
async def test_plano_premium_info(client: AsyncClient):
    """Vitrine do plano deve ser pública e trazer a semana de demonstração"""
    res = await client.get("/plano/premium")
    assert res.status_code == 200
    data = res.json()
    assert data["nome"] == "Premium Mensal"
    assert data["preco"] == 19.90
    assert data["trial"]["dias"] == 7


@pytest.mark.asyncio
async def test_plano_trial_ativa_premium(client: AsyncClient):
    """Trial de 7 dias deve ativar premium uma única vez por usuário"""
    reg = await client.post("/auth/register", json={
        "email": "trial@email.com", "senha": "Senha@123", "nome": "Trial"
    })
    confirm = await client.post("/auth/confirm", json={
        "email": "trial@email.com", "codigo": reg.json()["codigo_demo"]
    })
    token = confirm.json()["token"]

    res = await client.post(
        "/plano/trial", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["plano"] == "premium"
    assert data["trial"] is True
    assert data["dias"] == 7

    # Segunda tentativa deve ser bloqueada (trial já usado)
    res = await client.post(
        "/plano/trial", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_plano_assinar_sem_login(client: AsyncClient):
    """Assinar sem token → 401"""
    res = await client.post("/plano/assinar")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_plano_assinar_e_meu_status(client: AsyncClient):
    """Assinatura (simulada) ativa o premium e atualiza status"""
    # Cria e confirma um usuário real no banco isolado de teste
    reg = await client.post("/auth/register", json={
        "email": "premiado@email.com", "senha": "Senha@123", "nome": "Assinante"
    })
    codigo = reg.json()["codigo_demo"]
    confirm = await client.post("/auth/confirm", json={
        "email": "premiado@email.com", "codigo": codigo
    })
    token = confirm.json()["token"]

    res = await client.post(
        "/plano/assinar", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["plano"] == "premium"

    res = await client.get(
        "/plano/meu", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    status = res.json()
    assert status["plano"] == "premium"
    assert status["premium_ativo"] is True