# app/modules/plano/service.py
"""Serviço de assinatura mensal premium (checkout simulado)"""
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import HTTPException
from app.core.core import get_logger, settings
from app.shared.database import db
from app.shared.security import security

logger = get_logger("auth")

# Preço do plano mensal (custo zero MVP — plugue Stripe/Mercado Pago depois)
PLANO_MENSAL = {
    "nome": "Premium Mensal",
    "preco": 19.90,
    "periodo": "mensal",
    "descricao": "Análises completas da IA, gráficos interativos, relatórios PDF e stream em tempo real",
}


class PlanoService:
    """Gerencia assinaturas (checkout simulado)"""

    # Duração da semana de demonstração (trial)
    TRIAL_DIAS = 7

    @staticmethod
    async def info() -> Dict[str, Any]:
        """Retorna informações do plano para a vitrine de venda"""
        return {
            **PLANO_MENSAL,
            "moeda": "BRL",
            "checkout": "simulado",
            "trial": {
                "dias": PlanoService.TRIAL_DIAS,
                "descricao": f"{PlanoService.TRIAL_DIAS} dias grátis de Premium, sem cartão de crédito",
            },
        }

    @staticmethod
    async def trial(token: str) -> Dict[str, Any]:
        """Ativa a semana de demonstração gratuita (uma única vez por usuário)"""
        payload = security.verify_token(token)
        user_id = int(payload["sub"])

        async with db.connect() as conn:
            user = await conn.fetch_one(
                "SELECT id, email, nome, plano, trial_usado FROM usuarios WHERE id = ?",
                (user_id,),
            )
            if not user:
                raise HTTPException(404, "Usuário não encontrado")

            trial_em_andamento = (
                user["plano"] == "premium"
                and bool(user["trial_usado"])
                and (await PlanoService._tem_premium_ativo(conn, user_id))
            )
            if trial_em_andamento:
                raise HTTPException(409, "Você já está na semana de demonstração")

            if user["trial_usado"]:
                raise HTTPException(409, "Você já utilizou sua semana de demonstração")

            trial_ate = (
                datetime.now() + timedelta(days=PlanoService.TRIAL_DIAS)
            ).isoformat(timespec="seconds")

            await conn.execute(
                """
                UPDATE usuarios
                SET plano = 'premium', assinatura_ate = ?, trial_usado = 1
                WHERE id = ?
                """,
                (trial_ate, user_id),
            )

        logger.info("Trial premium ativado (7 dias)",
                    {"user_id": user_id, "ate": trial_ate})

        return {
            "ok": True,
            "mensagem": f"Semana de demonstração ativada! Você é Premium até {trial_ate.replace('T', ' ')[:16]}.",
            "plano": "premium",
            "trial": True,
            "dias": PlanoService.TRIAL_DIAS,
            "assinatura_ate": trial_ate,
        }

    @staticmethod
    async def _tem_premium_ativo(conn, user_id: int) -> bool:
        """Checa se o premium do usuário ainda está vigente"""
        user = await conn.fetch_one(
            "SELECT assinatura_ate FROM usuarios WHERE id = ?", (user_id,)
        )
        if not user or not user["assinatura_ate"]:
            return False
        return user["assinatura_ate"] > datetime.now().isoformat(timespec="seconds")

    @staticmethod
    async def assinar(token: str) -> Dict[str, Any]:
        """Simula a compra e ativa o plano premium do usuário (mensal pago)"""
        payload = security.verify_token(token)
        user_id = int(payload["sub"])

        async with db.connect() as conn:
            user = await conn.fetch_one(
                "SELECT id, email, nome FROM usuarios WHERE id = ?", (user_id,)
            )
            if not user:
                raise HTTPException(404, "Usuário não encontrado")

            assinatura_ate = (
                datetime.now() + timedelta(days=30)
            ).isoformat(timespec="seconds")

            await conn.execute(
                """
                UPDATE usuarios
                SET plano = 'premium', assinatura_ate = ?, stripe_subscription_id = ?
                WHERE id = ?
                """,
                (assinatura_ate, f"sub_sim_{user_id}_{int(datetime.now().timestamp())}", user_id),
            )

        logger.info("Assinatura premium ativada (simulada)",
                    {"user_id": user_id, "ate": assinatura_ate})

        return {
            "ok": True,
            "mensagem": f"Assinatura Premium ativada com sucesso até {assinatura_ate.replace('T', ' ')[:16]}",
            "plano": "premium",
            "assinatura_ate": assinatura_ate,
            "checkout": "simulado",  # Troque por redirect para Stripe/Mercado Pago
        }

    @staticmethod
    async def status(token: str) -> Dict[str, Any]:
        """Retorna status da assinatura do usuário"""
        payload = security.verify_token(token)
        user_id = int(payload["sub"])

        async with db.connect() as conn:
            user = await conn.fetch_one(
                "SELECT plano, assinatura_ate, trial_usado FROM usuarios WHERE id = ?", (user_id,)
            )
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        premium_ativo = user["plano"] == "premium" and (
            not user["assinatura_ate"]
            or user["assinatura_ate"] > datetime.now().isoformat(timespec="seconds")
        )

        return {
            "plano": user["plano"],
            "assinatura_ate": user["assinatura_ate"],
            "premium_ativo": premium_ativo,
            "em_trial": bool(user["trial_usado"]) and premium_ativo,
        }

    @staticmethod
    async def relatorio_pdf(token: str) -> bytes:
        """Gera relatório em PDF se o usuário for Premium ativo, senão lança 403"""
        from app.modules.plano.pdf import build_pdf_bytes
        from app.modules.indicators.service import service as indicators_service

        payload = security.verify_token(token)
        user_id = int(payload["sub"])

        async with db.connect() as conn:
            user = await conn.fetch_one(
                "SELECT nome, plano, assinatura_ate FROM usuarios WHERE id = ?", (user_id,)
            )

        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        premium_ativo = user["plano"] == "premium" and (
            not user["assinatura_ate"]
            or user["assinatura_ate"] > datetime.now().isoformat(timespec="seconds")
        )

        if not premium_ativo:
            raise HTTPException(
                403, "O download de relatórios em PDF é exclusivo para assinantes Premium"
            )

        indicadores = await indicators_service.resumo()
        return build_pdf_bytes(user["nome"], indicadores)


def get_service() -> PlanoService:
    return PlanoService()


service = get_service()