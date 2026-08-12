# app/modules/realtime/routes.py
"""Rotas de tempo real (SSE)"""
from fastapi import APIRouter, Request, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from typing import Optional
from app.shared.database import db
from app.shared.security import security
from app.modules.realtime.manager import realtime

router = APIRouter(prefix="/realtime", tags=["realtime"])

@router.get("/stream")
async def stream_dados(request: Request, token: Optional[str] = Query(None)):
    """Stream de dados em tempo real para assinantes"""
    # Valida token via Header ou Query parameter
    auth_header = request.headers.get("Authorization", "")
    token_str = ""
    if auth_header.startswith("Bearer "):
        token_str = auth_header.split(" ")[1]
    elif token:
        token_str = token
    else:
        raise HTTPException(401, "Token necessário")
    
    payload = security.verify_token(token_str)
    user_id = int(payload["sub"])
    
    # Verifica plano (aceita pro, premium, ou admin)
    if payload.get("plano") not in ["pro", "premium", "admin"]:
        raise HTTPException(403, "Plano não permite tempo real")
    
    # Cria fila para o usuário
    queue = asyncio.Queue()
    await realtime.add(user_id, queue)
    
    async def event_generator():
        """Gera eventos SSE"""
        try:
            while True:
                # Verifica desconexão
                if await request.is_disconnected():
                    break
                
                # Busca dados mais recentes do usuário
                async with db.connect() as conn:
                    rows = await conn.fetch_all(
                        """
                        SELECT categoria, valor, timestamp 
                        FROM dados_metricas 
                        WHERE usuario_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT 10
                        """,
                        (user_id,)
                    )
                
                metrics = [dict(row) for row in rows]
                
                # Envia evento SSE em formato JSON
                yield {
                    "event": "dados",
                    "data": json.dumps(metrics)
                }
                
                await asyncio.sleep(2)  # Atualização a cada 2s
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": "Erro no stream"})}
        finally:
            # Garante remoção da conexão para evitar vazamento de memória
            await realtime.remove(user_id, queue)
    
    return EventSourceResponse(event_generator())

@router.get("/status")
async def status():
    """Retorna status do sistema de tempo real"""
    return {
        "conexoes_ativas": realtime.get_active_count(),
        "status": "online"
    }
