# app/modules/ai_analysis/models.py
"""Modelos Pydantic para o Módulo de IA de Análise de Manchetes e Auditoria Criptográfica"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional


CATEGORIAS_VALIDAS = {"Ações", "Câmbio", "Renda Fixa", "Agronegócio", "Infraestrutura"}
HORIZONTES_VALIDOS = {24, 48, 72, 168}  # horas permitidas
AUDIT_ID_MAX_LEN = 64


class AnalysisRequest(BaseModel):
    """Solicitação de análise de manchetes da IA para produto fechado de mercado"""
    categoria: str = Field(
        "Ações",
        description=f"Categorias aceitas: {', '.join(sorted(CATEGORIAS_VALIDAS))}",
        min_length=3,
        max_length=30,
    )
    horizonte_horas: int = Field(
        72,
        description="Janela preditiva em horas (24, 48, 72 ou 168)",
        ge=1,
        le=168,
    )

    @field_validator("categoria")
    @classmethod
    def valida_categoria(cls, v: str) -> str:
        """Normaliza e valida a categoria contra a lista permitida"""
        v_stripped = v.strip()
        for cat in CATEGORIAS_VALIDAS:
            if cat.lower() == v_stripped.lower():
                return cat
        raise ValueError(
            f"Categoria inválida: '{v_stripped}'. "
            f"Valores aceitos: {', '.join(sorted(CATEGORIAS_VALIDAS))}"
        )

    @field_validator("horizonte_horas")
    @classmethod
    def valida_horizonte(cls, v: int) -> int:
        """Valida que o horizonte é um dos valores permitidos"""
        if v not in HORIZONTES_VALIDOS:
            raise ValueError(
                f"Horizonte inválido: {v}h. "
                f"Valores aceitos: {sorted(HORIZONTES_VALIDOS)}"
            )
        return v


class PredictionResult(BaseModel):
    """Resultado da predição fechada gerada pela IA a partir das manchetes e indicadores"""
    audit_id: str
    categoria: str
    tendencia: str  # Alta, Baixa, Estável
    direcao_seta: str  # ⬆️, ⬇️, ➡️
    precisao_pct: float  # Precisão histórica calibrada ex.: 92.4%
    horizonte_horas: int
    manchetes_analisadas: List[str]  # Headlines oficiais validadas
    opcoes_interessantes: List[str]  # Opções/ativos recomendados a partir das manchetes
    fatores_chave: List[str]
    nivel_risco: str  # Baixo, Médio, Alto
    explicacao_metodologia: str
    modelo_ia: str
    tempo_execucao_ms: float
    checksum_sha256: str
    timestamp: str


class AuditVerifyResponse(BaseModel):
    """Resposta da verificação de auditabilidade SHA-256"""
    audit_id: str
    valido: bool
    status: str
    checksum_registrado: str
    checksum_recalculado: str
    modelo: str
    precisao_pct: float
    timestamp: str
    detalhes_tecnicos: Dict[str, Any]
