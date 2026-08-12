# app/modules/plano/routes.py
"""Rotas da assinatura do plano mensal premium"""
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from typing import Dict, Any, Optional
from app.modules.plano.service import service

router = APIRouter(prefix="/plano", tags=["plano"])


def _token(request: Request) -> str:
    """Extrai o token Bearer do request"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    token = request.query_params.get("token")
    if token:
        return token
    raise HTTPException(401, "Login necessário")

@router.get("/premium")
async def info_plano():
    """Vitrine do plano premium mensal"""
    return await service.info()

@router.post("/trial")
async def ativar_trial(request: Request):
    """Ativa a semana de demonstração gratuita (uma vez por usuário)"""
    return await service.trial(_token(request))

@router.post("/assinar")
async def assinar_plano(request: Request):
    """Compra (simulada) do plano mensal premium"""
    return await service.assinar(_token(request))

@router.get("/meu")
async def minha_assinatura(request: Request):
    """Status da assinatura do usuário logado"""
    return await service.status(_token(request))

@router.get("/relatorio-pdf")
async def relatorio_pdf(request: Request):
    """Gera e baixa o relatório quinzenal/diário em PDF (exclusivo Premium)"""
    from fastapi.responses import Response
    pdf_bytes = await service.relatorio_pdf(_token(request))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="relatorio_radar_financeiro.pdf"'},
    )