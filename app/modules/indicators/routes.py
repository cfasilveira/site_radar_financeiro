# app/modules/indicators/routes.py
"""Rotas de indicadores econômicos (Bacen, IBGE, B3)"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from app.modules.indicators.service import service

router = APIRouter(prefix="/indicadores", tags=["indicadores"])

# Nome canônico de cada indicador
NOMES = {
    "selic": "Meta SELIC",
    "ipca": "IPCA Mensal",
    "ipca_12m": "IPCA Acumulado 12 Meses",
    "dolar": "Dólar Comercial",
}


@router.get("/resumo")
async def resumo_indicadores() -> Dict[str, Any]:
    """Resumo dos principais indicadores econômicos em tempo real"""
    return await service.resumo()


@router.get("/serie/{indicador}")
async def serie_indicador(
    indicador: str,
    ultimos: int = Query(30, ge=1, le=180, description="Quantidade de pontos"),
) -> Dict[str, Any]:
    """Série histórica do indicador (selic, ipca, ipca_12m, dolar)"""
    try:
        return await service.serie(indicador.lower(), ultimos)
    except ValueError as e:
        raise HTTPException(404, str(e))