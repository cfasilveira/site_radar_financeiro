# app/modules/indicators/service.py
"""Serviço de coleta de indicadores econômicos com cache em memória"""
import asyncio
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import httpx
from app.core.core import get_logger, settings

logger = get_logger("indicators")

# Séries oficiais do Banco Central (SGS)
# 432 = Meta SELIC, 10813 = Dólar comercial (venda, PTAX), 13522 = IPCA acumulado 12m,
# 433 = IPCA mensal, 1 = Dólar livre (venda)
SGS_SELIC_META = 432
SGS_DOLAR = 10813
SGS_IPCA_12M = 13522
SGS_IPCA_MENSAL = 433

# Código IBOVESPA no Yahoo Finance
BOVESPA_SYMBOL = "^BVSP"

# TTL do cache em segundos (10 minutos)
CACHE_TTL = settings.ENV == "test" and 0 or 600


class BCBApiError(Exception):
    """Erro na comunicação com o Banco Central"""


async def _bcb_serie(codigo: int, ultimos: int = 15) -> List[Dict[str, Any]]:
    """Busca série de dados na API do Banco Central (SGS)"""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{ultimos}?formato=json"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        rows = resp.json()
    result = []
    for row in rows:
        valor_raw = str(row.get("valor", "0")).replace(",", ".")
        try:
            valor = float(valor_raw)
        except ValueError:
            continue
        # "16/09/2026" -> "2026-09-16"
        try:
            data_iso = datetime.strptime(row["data"], "%d/%m/%Y").date().isoformat()
        except (ValueError, KeyError):
            data_iso = row.get("data", "")
        result.append({"data": data_iso, "valor": valor})
    return result


async def _bovespa_quote() -> Optional[Dict[str, Any]]:
    """Busca cotação atual do IBOVESPA no Yahoo Finance"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?range=5d&interval=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        prev_close = meta.get("chartPreviousClose")

        # Séries fechadas (timestamp + close)
        ts = result.get("timestamp", [])
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close", [])
        points = []
        for t, c in zip(ts, closes):
            if c is None:
                continue
            points.append({
                "data": datetime.fromtimestamp(t).date().isoformat(),
                "valor": round(float(c), 2),
            })

        variacao = None
        if price and prev_close:
            variacao = round(((price - prev_close) / prev_close) * 100, 2)

        return {
            "atual": round(float(price), 2) if price else None,
            "anterior": round(float(prev_close), 2) if prev_close else None,
            "variacao_pct": variacao,
            "serie": points[:30],
            "fonte": "Yahoo Finance (B3)",
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        }
    except (KeyError, TypeError, ValueError, httpx.HTTPError) as e:
        logger.error("Falha ao buscar IBOVESPA", {"error": str(e)})
        return None


class IndicatorsCache:
    """Cache simples em memória com TTL"""

    def __init__(self, ttl: int = CACHE_TTL):
        self._ttl = ttl
        self._store: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        data, ts = item
        if self._ttl and (time.time() - ts) > self._ttl:
            return None
        return data

    def set(self, key: str, data: Any):
        self._store[key] = (data, time.time())


_cache = IndicatorsCache()


class IndicatorsService:
    """Agrega indicadores econômicos com cache"""

    async def resumo(self) -> Dict[str, Any]:
        """Retorna resumo de indicadores principais (WebSocket-friendly, sem auth)"""
        cached = _cache.get("resumo")
        if cached:
            return cached

        selic = ipca_12m = ipca_mensal = dolar = None
        try:
            selic_rows = await _bcb_serie(SGS_SELIC_META, 3)
            selic = selic_rows[-1]["valor"] if selic_rows else None
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Falha ao buscar SELIC", {"error": str(e)})

        try:
            ipca_rows = await _bcb_serie(SGS_IPCA_12M, 3)
            ipca_12m_rows = ipca_rows or []
            ipca_12m = ipca_12m_rows[-1]["valor"] if ipca_12m_rows else None
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Falha ao buscar IPCA", {"error": str(e)})

        try:
            ipca_mensal_rows = await _bcb_serie(SGS_IPCA_MENSAL, 3)
            ipca_mensal = ipca_mensal_rows[-1]["valor"] if ipca_mensal_rows else None
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Falha ao buscar IPCA mensal", {"error": str(e)})

        try:
            dolar_rows = await _bcb_serie(SGS_DOLAR, 3)
            dolar = dolar_rows[-1]["valor"] if dolar_rows else None
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Falha ao buscar câmbio", {"error": str(e)})

        bovespa = await _bovespa_quote()

        data = {
            "selic": {"valor": selic, "unidade": "% a.a.", "fonte": "Banco Central"},
            "ipca_12m": {"valor": ipca_12m, "unidade": "%", "fonte": "Banco Central"},
            "ipca_mensal": {"valor": ipca_mensal, "unidade": "%", "fonte": "Banco Central"},
            "dolar": {"valor": dolar, "unidade": "R$/US$", "fonte": "Banco Central"},
            "ibovespa": bovespa,
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        }
        _cache.set("resumo", data)
        return data

    async def serie(self, indicador: str, ultimos: int = 30) -> Dict[str, Any]:
        """Retorna série histórica de um indicador (selic, ipca, ipca_12m, dolar)"""
        codigos = {
            "selic": SGS_SELIC_META,
            "ipca": SGS_IPCA_MENSAL,
            "ipca_12m": SGS_IPCA_12M,
            "dolar": SGS_DOLAR,
        }
        if indicador not in codigos:
            raise ValueError(f"Indicador '{indicador}' não suportado")

        cache_key = f"serie:{indicador}:{ultimos}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        rows = await _bcb_serie(codigos[indicador], ultimos)
        data = {"indicador": indicador, "serie": rows}
        _cache.set(cache_key, data)
        return data


def get_indicators() -> IndicatorsService:
    """Factory singleton"""
    return IndicatorsService()


service = get_indicators()