# tests/test_ai_analysis.py
"""
Testes automatizados do Módulo Independente e Auditável de IA de Análise de Manchetes (Produto Fechado).
"""
import pytest
from httpx import AsyncClient
from app.shared.database import db
from app.shared.security import security


@pytest.fixture
async def usuarios_ia():
    """Cria usuário Premium e Free para os testes de IA"""
    tokens = {}
    async with db.connect() as conn:
        # Usuário Premium
        hash_p = security.hash_password("SenhaPremium@123")
        await conn.execute(
            """
            INSERT OR REPLACE INTO usuarios (email, senha_hash, nome, plano, confirmado)
            VALUES (?, ?, ?, ?, 1)
            """,
            ("ia_premium@radar.com", hash_p, "Usuario IA Premium", "premium"),
        )
        u_p = await conn.fetch_one(
            "SELECT id FROM usuarios WHERE email = 'ia_premium@radar.com'"
        )
        tokens["premium"] = security.create_token(u_p["id"], "ia_premium@radar.com", "premium")

        # Usuário Free
        hash_f = security.hash_password("SenhaFree@123")
        await conn.execute(
            """
            INSERT OR REPLACE INTO usuarios (email, senha_hash, nome, plano, confirmado)
            VALUES (?, ?, ?, ?, 1)
            """,
            ("ia_free@radar.com", hash_f, "Usuario IA Free", "free"),
        )
        u_f = await conn.fetch_one(
            "SELECT id FROM usuarios WHERE email = 'ia_free@radar.com'"
        )
        tokens["free"] = security.create_token(u_f["id"], "ia_free@radar.com", "free")

    return tokens


# ====================================================================
# 1. PREDIÇÕES DE MANCHETES: Acesso e Autorização
# ====================================================================

@pytest.mark.asyncio
async def test_predicoes_premium_sucesso(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["premium"]
    res = await client.get("/ai/predicoes", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    first = data[0]
    assert "audit_id" in first
    assert "checksum_sha256" in first
    assert "manchetes_analisadas" in first
    assert "opcoes_interessantes" in first
    assert len(first["opcoes_interessantes"]) > 0
    assert first["precisao_pct"] > 80.0
    assert first["modelo_ia"].startswith("RadarPredict")


@pytest.mark.asyncio
async def test_predicoes_free_bloqueado(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["free"]
    res = await client.get("/ai/predicoes", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    msg = res.json().get("error") or res.json().get("detail")
    assert "exclusivas" in msg.lower()


@pytest.mark.asyncio
async def test_predicoes_sem_token(client: AsyncClient):
    res = await client.get("/ai/predicoes")
    assert res.status_code == 401


# ====================================================================
# 2. ANÁLISE FECHADA DE MANCHETES POR CATEGORIA
# ====================================================================

@pytest.mark.asyncio
async def test_analisar_manchetes_categoria(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["premium"]
    payload = {
        "categoria": "Agronegócio",
        "horizonte_horas": 48,
    }
    res = await client.post(
        "/ai/analisar",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["categoria"] == "Agronegócio"
    assert data["tendencia"] in ("Alta", "Baixa", "Estável")
    assert len(data["manchetes_analisadas"]) > 0
    assert len(data["opcoes_interessantes"]) > 0
    assert len(data["checksum_sha256"]) == 64


@pytest.mark.asyncio
async def test_analisar_categoria_invalida(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["premium"]
    res = await client.post(
        "/ai/analisar",
        json={"categoria": "Invalida", "horizonte_horas": 72},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_analisar_horizonte_invalido(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["premium"]
    res = await client.post(
        "/ai/analisar",
        json={"categoria": "Ações", "horizonte_horas": 999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


# ====================================================================
# 3. AUDITORIA: Integridade e Adulteração
# ====================================================================

@pytest.mark.asyncio
async def test_verificar_auditoria_integra_e_adulterada(client: AsyncClient, usuarios_ia):
    token = usuarios_ia["premium"]

    # 1. Gera uma análise de manchetes
    res_analise = await client.post(
        "/ai/analisar",
        json={"categoria": "Ações", "horizonte_horas": 72},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_analise.status_code == 200
    audit_id = res_analise.json()["audit_id"]
    checksum_original = res_analise.json()["checksum_sha256"]

    # 2. Verifica integridade -> deve estar íntegro
    res_aud = await client.get(f"/ai/auditoria/{audit_id}")
    assert res_aud.status_code == 200
    data_aud = res_aud.json()
    assert data_aud["valido"] is True
    assert data_aud["status"] == "INTEGRO_E_VERIFICADO"

    # 3. Adultera no banco
    async with db.connect() as conn:
        await conn.execute(
            "UPDATE ia_auditoria SET output_json = '{\"adulterado\": true}' WHERE id = ?",
            (audit_id,),
        )

    # 4. Deve detectar adulteração
    res_aud_tampered = await client.get(f"/ai/auditoria/{audit_id}")
    assert res_aud_tampered.status_code == 200
    data_tampered = res_aud_tampered.json()
    assert data_tampered["valido"] is False
    assert data_tampered["status"] == "ADULTERACAO_DETECTADA"
