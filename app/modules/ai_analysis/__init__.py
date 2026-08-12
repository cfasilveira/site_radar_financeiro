# app/modules/ai_analysis/__init__.py
"""Módulo de Inteligência Artificial para análise preditiva auditável"""
from .routes import router
from .service import AiAnalysisService, service
from .models import AnalysisRequest, PredictionResult, AuditVerifyResponse

__all__ = [
    "router",
    "AiAnalysisService",
    "service",
    "AnalysisRequest",
    "PredictionResult",
    "AuditVerifyResponse",
]
