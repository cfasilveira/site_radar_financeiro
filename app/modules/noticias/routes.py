# app/modules/noticias/routes.py
"""Rotas de manchetes diárias (exigem login)"""
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from typing import Dict, Any, Optional
from app.shared.security import security
from app.modules.noticias.service import service

router = APIRouter(prefix="/noticias", tags=["noticias"])


def _autenticar(request: Request) -> int:
    """Extrai e valida o token do usuário"""
    # SEGURANÇA: Tokens via query string foram removidos — aparecem em logs e histórico
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or len(auth_header) <= 7:
        raise HTTPException(401, "Login necessário para acessar as manchetes")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = security.verify_token(token)
    except HTTPException:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    return int(payload["sub"])


@router.get("/manchetes")
async def manchetes_do_dia(
    request: Request,
    refresh: bool = Query(False, description="Força atualização dos feeds"),
):
    """Headlines do dia (títulos + fonte). Exige usuário logado."""
    _autenticar(request)
    return await service.manchetes(refresh=refresh)