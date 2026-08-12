# app/shared/middleware.py
"""Middleware unificado e otimizado"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.core import get_logger, settings
import time
import uuid

logger = get_logger("http")

class Middleware(BaseHTTPMiddleware):
    """Middleware único com logging e segurança"""
    
    # Rotas excluídas de logging
    EXCLUDE_PATHS = {"/health", "/health/detailed", "/metrics", "/favicon.ico"}
    
    # Headers de segurança
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
    
    async def dispatch(self, request: Request, call_next):
        # Gera ID de correlação
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            
            # Adiciona headers de segurança
            for key, value in self.SECURITY_HEADERS.items():
                response.headers.setdefault(key, value)
            
            # Log apenas para rotas relevantes
            if request.url.path not in self.EXCLUDE_PATHS:
                duration = (time.perf_counter() - start_time) * 1000
                self._log_request(request, response, duration, request_id)
            
            return response
            
        except Exception as e:
            # Fallback: resposta amigável
            logger.error(
                "Erro não tratado",
                {
                    "rid": request_id,
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Erro interno do servidor",
                    "request_id": request_id,
                    "message": "Tente novamente mais tarde" if not settings.DEBUG else str(e)
                }
            )
    
    def _log_request(self, request: Request, response: Response, duration: float, request_id: str):
        """Log estruturado da requisição"""
        log_data = {
            "rid": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round(duration, 2)
        }
        
        # Nível baseado no status
        if response.status_code >= 500:
            logger.error(f"Erro servidor: {request.url.path}", log_data)
        elif response.status_code >= 400:
            logger.warning(f"Erro cliente: {request.url.path}", log_data)
        elif duration > 1000:  # > 1 segundo
            logger.warning(f"Requisição lenta: {request.url.path}", log_data)
        else:
            logger.info(f"Requisição OK: {request.url.path}", log_data)
