# tests/test_indicators.py
"""Testes do módulo de indicadores econômicos"""
import pytest
from app.modules.indicators import service as indicators_service

pytestmark = pytest.mark.asyncio

FAKE_RESUMO = {
    "selic": {"valor": 14.0, "unidade": "% a.a.", "fonte": "Banco Central"},
    "ipca_12m": {"valor": 4.44, "unidade": "%", "fonte": "Banco Central"},
    "ipca_mensal": {"valor": 0.07, "unidade": "%", "fonte": "Banco Central"},
    "dolar": {"valor": 5.13, "unidade": "R$/US$", "fonte": "Banco Central"},
    "ibovespa": {
        "atual": 167874.64,
        "anterior": 177895.0,
        "variacao_pct": -5.63,
        "serie": [
            {"data": "2026-08-10", "valor": 172180.0},
            {"data": "2026-08-11", "valor": 167875.0},
        ],
        "fonte": "Yahoo Finance (B3)",
        "atualizado_em": "2026-08-12T00:00:00",
    },
    "atualizado_em": "2026-08-12T00:00:00",
}


async def _fake_bcb_serie(codigo: int, ultimos: int = 15):
    valores = {
        indicators_service.SGS_SELIC_META: 14.0,
        indicators_service.SGS_IPCA_12M: 4.44,
        indicators_service.SGS_IPCA_MENSAL: 0.07,
        indicators_service.SGS_DOLAR: 5.13,
    }
    valor = valores.get(codigo, 14.0)
    return [
        {"data": "2026-08-11", "valor": valor},
        {"data": "2026-08-12", "valor": valor},
    ]


async def _fake_bovespa():
    return FAKE_RESUMO["ibovespa"]


async def test_resumo_sem_autenticacao(client, monkeypatch):
    """Endpoint /indicadores/resumo deve funcionar sem token"""
    monkeypatch.setattr(indicators_service, "_bcb_serie", _fake_bcb_serie)
    monkeypatch.setattr(indicators_service, "_bovespa_quote", _fake_bovespa)
    indicators_service._cache = indicators_service.IndicatorsCache(ttl=0)

    resp = await client.get("/indicadores/resumo")
    assert resp.status_code == 200
    data = resp.json()

    assert data["selic"]["valor"] == 14.0
    assert data["dolar"]["valor"] == 5.13
    assert data["ibovespa"]["variacao_pct"] == -5.63
    assert data["atualizado_em"]


async def test_serie_selic(client, monkeypatch):
    """Endpoint de série histórica retorna listas ordenadas"""
    monkeypatch.setattr(indicators_service, "_bcb_serie", _fake_bcb_serie)
    indicators_service._cache = indicators_service.IndicatorsCache(ttl=0)

    resp = await client.get("/indicadores/serie/selic")
    assert resp.status_code == 200
    data = resp.json()

    assert data["indicador"] == "selic"
    assert len(data["serie"]) == 2
    assert data["serie"][0]["valor"] == 14.0
    assert data["serie"][0]["data"]


async def test_serie_indicador_invalido(client):
    """Indicador desconhecido retorna 404"""
    resp = await client.get("/indicadores/serie/ouro")
    assert resp.status_code == 404


async def test_serie_sem_autenticacao(client, monkeypatch):
    """Série deve ser pública (sem token)"""
    monkeypatch.setattr(indicators_service, "_bcb_serie", _fake_bcb_serie)
    indicators_service._cache = indicators_service.IndicatorsCache(ttl=0)

    resp = await client.get("/indicadores/serie/dolar?ultimos=10")
    assert resp.status_code == 200