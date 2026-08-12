# app/modules/ai_analysis/routes.py
"""Rotas do Módulo de IA Preditiva Independente e Auditável"""
import re
from fastapi import APIRouter, Request, HTTPException
from typing import List, Dict, Any

from app.shared.security import security
from app.shared.database import db
from app.modules.ai_analysis.service import service
from app.modules.ai_analysis.models import (
    AnalysisRequest,
    PredictionResult,
    AuditVerifyResponse,
    AUDIT_ID_MAX_LEN,
)

router = APIRouter(prefix="/ai", tags=["ai_analysis"])

# Padrão permitido para audit_id (alfanumérico + underscore, produzido pelo serviço)
_AUDIT_ID_RE = re.compile(r"^[a-z0-9_]{8,64}$")


def _exigir_token(request: Request) -> str:
    """Extrai token Bearer do header Authorization.
    
    SEGURANÇA: Tokens via query string foram removidos — eles aparecem em logs
    de servidor, proxies reversos e histório do navegador.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        return auth_header.split(" ", 1)[1]
    raise HTTPException(401, "Token de autenticação necessário (header Authorization: Bearer <token>)")


def _exige_premium(token: str) -> Dict[str, Any]:
    """Valida token JWT e garante que o plano é Premium"""
    payload = security.verify_token(token)
    if payload.get("plano") != "premium":
        raise HTTPException(
            403,
            "As análises preditivas com IA e auditoria são exclusivas para assinantes Premium"
        )
    return payload


@router.post("/analisar", response_model=PredictionResult)
async def analisar(request: Request, body: AnalysisRequest):
    """Gera uma nova análise preditiva de mercado com auditoria SHA-256.
    
    - **Exclusivo Premium**: Requer assinatura ativa.
    - **Rate limit**: 10 requisições por minuto por usuário.
    - **Auditável**: Cada análise gera um hash SHA-256 imutável verificável publicamente.
    """
    token = _exigir_token(request)
    payload = _exige_premium(token)
    user_id = int(payload["sub"])
    request_id = getattr(request.state, "request_id", "req_manual")
    return await service.analisar(user_id=user_id, req=body, request_id=request_id)


@router.get("/predicoes", response_model=List[PredictionResult])
async def obter_predicoes(request: Request):
    """Retorna a síntese preditiva atual para a página inicial do assinante.
    
    - Dados são cacheados por 10 minutos para proteger o banco de dados.
    - **Exclusivo Premium**.
    """
    token = _exigir_token(request)
    payload = _exige_premium(token)
    user_id = int(payload["sub"])
    return await service.obter_sintese_preditiva(user_id)


@router.get("/auditoria/{audit_id}", response_model=AuditVerifyResponse)
async def verificar_auditoria(audit_id: str):
    """Valida criptograficamente se uma análise foi alterada ou violada.
    
    - **Endpoint público**: Não requer autenticação.
    - Qualquer pessoa pode verificar a integridade de uma análise pelo seu audit_id.
    """
    # Defesa em profundidade: validação do formato antes de tocar o banco
    if not _AUDIT_ID_RE.match(audit_id):
        raise HTTPException(
            400,
            f"Formato de audit_id inválido. Deve conter apenas letras minúsculas, "
            f"números e underscore (máx. {AUDIT_ID_MAX_LEN} caracteres)."
        )
    return await service.verificar_auditoria(audit_id)


@router.get("/auditoria", response_model=List[Dict[str, Any]])
async def listar_auditorias(request: Request):
    """Lista histórico de logs de auditoria do usuário autenticado (até 20 registros).
    
    - **Exclusivo Premium**.
    """
    token = _exigir_token(request)
    payload = _exige_premium(token)
    user_id = int(payload["sub"])

    async with db.connect() as conn:
        rows = await conn.fetch_all(
            """
            SELECT id, categoria, modelo, precisao_pct, tempo_ms, checksum_sha256, timestamp
            FROM ia_auditoria
            WHERE usuario_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (user_id,),
        )
    return [dict(row) for row in rows]
