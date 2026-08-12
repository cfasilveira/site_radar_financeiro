# app/modules/ads/service.py
"""Serviço de espaços publicitários e negociação"""
from typing import Dict, List, Any
from fastapi import HTTPException
from app.core.core import get_logger
from app.shared.database import db

logger = get_logger("auth")

# Catálogo de espaços publicitários disponíveis no portal
ESPACOS: Dict[str, Dict[str, Any]] = {
    "leaderboard-topo": {
        "nome": "Leaderboard Topo",
        "posicao": "Topo do Portal (acima da pasta)",
        "formato": "728x90 (desktop) / 320x50 (mobile)",
        "preco_mensal": 499.90,
        "impressoes_est": "120 mil/mês",
        "descricao": "Primeiro banner visto pelo visitante. Visibilidade máxima em página cheia.",
        "disponibilidade": True,
    },
    "banner-hero": {
        "nome": "Banner Hero",
        "posicao": "Seção principal (abaixo da manchete)",
        "formato": "970x250 (desktop) / 300x100 (mobile)",
        "preco_mensal": 699.90,
        "impressoes_est": "180 mil/mês",
        "descricao": "Espaço premium em destaque, ao lado dos indicadores em tempo real.",
        "disponibilidade": True,
    },
    "sidebar-direita": {
        "nome": "Sidebar Direita",
        "posicao": "Barra lateral durante a leitura",
        "formato": "300x600 (desktop) / 300x250 (mobile)",
        "preco_mensal": 349.90,
        "impressoes_est": "90 mil/mês",
        "descricao": "Alta permanência, ideal para campanhas de conversão.",
        "disponibilidade": True,
    },
    "in-content": {
        "nome": "Produto In-Content",
        "posicao": "Entre as manchetes do dia",
        "formato": "728x90 / nativo",
        "preco_mensal": 249.90,
        "impressoes_est": "70 mil/mês",
        "descricao": "Conteúdo patrocinado leve integrado às headlines diárias.",
        "disponibilidade": True,
    },
    "premium-analise": {
        "nome": "Patrocínio Análise Premium",
        "posicao": "Bloco de análise premium com IA",
        "formato": "Patrocínio + logo",
        "preco_mensal": 999.90,
        "impressoes_est": "50 mil/mês",
        "descricao": "Associe sua marca às análises feitas por IA que assinantes veem.",
        "disponibilidade": True,
    },
    "rodape": {
        "nome": "Rodapé Página",
        "posicao": "Fim de página em todas as seções",
        "formato": "970x90 / 728x90",
        "preco_mensal": 199.90,
        "impressoes_est": "60 mil/mês",
        "descricao": "Custo-benefício para reforço contínuo de marca.",
        "disponibilidade": True,
    },
}


class AdsService:
    """Consulta e negociação de espaços publicitários"""

    @staticmethod
    def listar() -> List[Dict[str, Any]]:
        return [{"slug": k, **v} for k, v in ESPACOS.items()]

    @staticmethod
    def obter(slug: str) -> Dict[str, Any]:
        espaco = ESPACOS.get(slug)
        if not espaco:
            raise HTTPException(404, "Espaço publicitário não encontrado")
        return {"slug": slug, **espaco}

    @staticmethod
    async def registrar_interesse(slug: str, contato: Dict[str, str]) -> Dict[str, Any]:
        espaco = AdsService.obter(slug)
        try:
            async with db.connect() as conn:
                await conn.execute(
                    """
                    INSERT INTO contatos_anuncio (nome, email, whatsapp, espaco, mensagem)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        contato.get("nome", ""),
                        contato.get("email", ""),
                        contato.get("whatsapp"),
                        espaco["nome"],
                        contato.get("mensagem"),
                    ),
                )
        except Exception as e:
            logger.error("Erro ao registrar interesse publicitário", {"error": str(e)})
            raise HTTPException(500, "Não foi possível registrar seu contato")
        logger.info("Interesse publicitário registrado", {"espaco": espaco["nome"]})
        return {
            "ok": True,
            "mensagem": "Recebemos seu interesse! Nossa equipe comercial entrará em contato.",
        }


def get_service() -> AdsService:
    return AdsService()


service = get_service()