# app/modules/noticias/service.py
"""Agregador de headlines diárias de fontes RSS (headlines = títulos + fonte)"""
import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import httpx
from app.core.core import get_logger, settings

logger = get_logger("noticias")

# Fontes oficiais/principais do dia — 5 melhores (nacionais + internacionais)
FEEDS: List[Dict[str, str]] = [
    {
        "nome": "Valor Econômico",
        "sitio": "Valor Econômico",
        "url": "https://valor.globo.com/rss/valor/",
        "pais": "🇧🇷 Nacional",
    },
    {
        "nome": "InfoMoney",
        "sitio": "InfoMoney",
        "url": "https://www.infomoney.com.br/feed/",
        "pais": "🇧🇷 Nacional",
    },
    {
        "nome": "Exame",
        "sitio": "Exame",
        "url": "https://exame.com/feed/",
        "pais": "🇧🇷 Nacional",
    },
    {
        "nome": "Bloomberg",
        "sitio": "Bloomberg",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "pais": "🌍 Internacional",
    },
    {
        "nome": "Financial Times",
        "sitio": "Financial Times",
        "url": "https://www.ft.com/rss/home/international",
        "pais": "🌍 Internacional",
    },
]

# TTL do cache
CACHE_TTL = settings.ENV == "test" and 0 or 300  # 5 minutos


# ================================================================
# Parser de RSS com tolerância a falhas
# ================================================================
def _parse_rss(xml_text: str, fonte: str, sitio: str) -> List[Dict[str, Any]]:
    """Extrai as headlines (título + link + fonte) de um feed RSS"""
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for item in root.iter("item"):
        title = None
        link = None
        pubdate = None
        for child in item:
            tag = child.tag.lower().split("}")[-1]
            if tag == "title" and not title:
                title = (child.text or "").strip()
            elif tag == "link" and not link:
                link = (child.text or "").strip()
            elif tag == "pubdate":
                pubdate = (child.text or "").strip()
        if not title:
            continue
        items.append({
            "titulo": title,
            "fonte": fonte,
            "sitio": sitio,
            "link": link,
            "publicado_em": pubdate,
        })
        if len(items) >= 8:
            break
    return items


async def _fetch_feed(client: httpx.AsyncClient, feed: Dict[str, str]) -> List[Dict[str, Any]]:
    """Busca um feed individual com timeout"""
    try:
        resp = await client.get(
            feed["url"],
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RadarFinancas/1.0"},
        )
        resp.raise_for_status()
        items = _parse_rss(resp.text, feed["nome"], feed["sitio"])
        pais = feed.get("pais", "")
        for it in items:
            it["pais"] = pais
        return items
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.error("Falha ao buscar feed",
                     {"fonte": feed["nome"], "error": str(e)})
        return []


class NoticiasService:
    """Agrega headlines das principais fontes do dia com cache"""

    def __init__(self):
        self._cache: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()

    async def manchetes(self, refresh: bool = False) -> Dict[str, Any]:
        """Retorna headlines do dia agrupadas por fonte"""
        now = time.time()
        cached = self._cache.get("manchetes")
        if cached and not refresh:
            data, ts = cached
            if (now - ts) < CACHE_TTL:
                return data

        async with self._lock:
            # Re-verifica cache (evita dupla fetch em concorrência)
            cached = self._cache.get("manchetes")
            if cached and not refresh:
                data, ts = cached
                if (now - ts) < CACHE_TTL:
                    return data

            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                results = await asyncio.gather(
                    *[_fetch_feed(client, f) for f in FEEDS]
                )

            por_fonte: Dict[str, List[Dict[str, Any]]] = {}
            for feed, items in zip(FEEDS, results):
                por_fonte[feed["nome"]] = items

            total = sum(len(items) for items in results)
            nacionais = sum(
                len(items) for feed, items in zip(FEEDS, results)
                if feed.get("pais", "").startswith("🇧")
            )
            internacionais = sum(
                len(items) for feed, items in zip(FEEDS, results)
                if feed.get("pais", "").startswith("🌍")
            )
            data = {
                "fonte": "RSS (Valor, InfoMoney, Exame, Bloomberg, FT)",
                "data_referencia": datetime.now().date().isoformat(),
                "total_headlines": total,
                "nacionais": nacionais,
                "internacionais": internacionais,
                "por_fonte": por_fonte,
                "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            }
            self._cache["manchetes"] = (data, now)
            return data

    async def buscarFeed(self):  # pragma: no cover - utilidade de manutenção
        return await self.manchetes(refresh=True)


def get_service() -> NoticiasService:
    return NoticiasService()


service = get_service()