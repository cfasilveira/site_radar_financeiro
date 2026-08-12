# tests/test_ads.py
"""Testes dos espaços publicitários e negociação"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_lista_espacos(client: AsyncClient):
    res = await client.get("/espacos-publicidade")
    assert res.status_code == 200
    data = res.json()
    assert len(data["espacos"]) >= 4
    assert data["espacos"][0]["preco_mensal"] > 0


@pytest.mark.asyncio
async def test_pagina_negociacao(client: AsyncClient):
    res = await client.get("/anuncio/leaderboard-topo")
    assert res.status_code == 200
    assert "Leaderboard" in res.text
    assert "anuncio/leaderboard-topo/contato" in res.text or "contato" in res.text


@pytest.mark.asyncio
async def test_pagina_negociacao_inexistente(client: AsyncClient):
    res = await client.get("/anuncio/slug-inexistente")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_contato_anuncio(client: AsyncClient):
    res = await client.post("/anuncio/banner-hero/contato", json={
        "nome": "Empresa X",
        "email": "comercial@empresa.com",
        "whatsapp": "5511999999999",
        "mensagem": "Quero anunciar",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "contato" in data["mensagem"].lower()


@pytest.mark.asyncio
async def test_contato_anuncio_espaco_invalido(client: AsyncClient):
    res = await client.post("/anuncio/nao-existe/contato", json={
        "nome": "Empresa X",
        "email": "comercial@empresa.com",
    })
    assert res.status_code == 404