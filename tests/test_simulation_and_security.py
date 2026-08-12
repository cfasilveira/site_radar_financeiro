# tests/test_simulation_and_security.py
"""
Suíte completa de simulação de concorrência/comportamento e testes de intrusão/segurança.

Cenários Cobertos:
1. Simulação de 5 Usuários (2 Premium, 2 Free, 1 Não confirmado)
2. Lógica de Pagamentos e Assinaturas (Checkout + Trial + Repetição)
3. Emissão de Relatório PDF (Autorização por Nível de Plano)
4. Falhas de Autenticação e Erros de Acesso
5. Testes de Invasão (SQL Injection, XSS, Path Traversal, JWT Tampering)
"""
import pytest
from httpx import AsyncClient
from app.shared.database import db
from app.shared.security import security


# ====================================================================
# 1. SETUP DE SIMULAÇÃO DOS 5 USUÁRIOS
# ====================================================================
USERS_SIMULATION = {
    "u1_admin": {
        "email": "u1_admin@radar.com",
        "senha": "SenhaAdmin@123",
        "nome": "Usuario Um Admin Premium",
        "plano": "premium",
        "confirmado": True,
    },
    "u2_subscriber": {
        "email": "u2_subscriber@radar.com",
        "senha": "SenhaSub@123",
        "nome": "Usuario Dois Assinante",
        "plano": "free",  # Começa free e assina via API
        "confirmado": True,
    },
    "u3_trial": {
        "email": "u3_trial@radar.com",
        "senha": "SenhaTrial@123",
        "nome": "Usuario Tres Demonstracao",
        "plano": "free",  # Começa free e ativa trial
        "confirmado": True,
    },
    "u4_free": {
        "email": "u4_free@radar.com",
        "senha": "SenhaFree@123",
        "nome": "Usuario Quatro Free",
        "plano": "free",
        "confirmado": True,
    },
    "u5_unconfirmed": {
        "email": "u5_unconfirmed@radar.com",
        "senha": "SenhaUnconfirmed@123",
        "nome": "Usuario Cinco Pendente",
        "plano": "free",
        "confirmado": False,
    },
}


@pytest.fixture
async def setup_5_usuarios():
    """Cadastra os 5 usuários diretamente no banco de teste (idempotente)"""
    tokens = {}
    async with db.connect() as conn:
        for key, u in USERS_SIMULATION.items():
            hashed = security.hash_password(u["senha"])
            conf = 1 if u["confirmado"] else 0
            await conn.execute(
                """
                INSERT OR REPLACE INTO usuarios (email, senha_hash, nome, plano, confirmado, codigo_confirmacao)
                VALUES (?, ?, ?, ?, ?, '123456')
                """,
                (u["email"], hashed, u["nome"], u["plano"], conf),
            )
            row = await conn.fetch_one(
                "SELECT id FROM usuarios WHERE email = ?", (u["email"],)
            )
            u["id"] = row["id"]
            if u["confirmado"]:
                tokens[key] = security.create_token(row["id"], u["email"], u["plano"])

    return tokens


# ====================================================================
# 2. TESTES DE PAGAMENTOS E ASSINATURAS
# ====================================================================
@pytest.mark.asyncio
async def test_simulacao_pagamentos_e_planos(client: AsyncClient, setup_5_usuarios):
    tokens = setup_5_usuarios
    token_u2 = tokens["u2_subscriber"]
    token_u3 = tokens["u3_trial"]
    token_u4 = tokens["u4_free"]

    # Usuário 2 faz checkout pago simulado
    res_sub = await client.post(
        "/plano/assinar", headers={"Authorization": f"Bearer {token_u2}"}
    )
    assert res_sub.status_code == 200
    assert res_sub.json()["plano"] == "premium"

    # Usuário 3 ativa 7 dias de demonstração (trial)
    res_trial = await client.post(
        "/plano/trial", headers={"Authorization": f"Bearer {token_u3}"}
    )
    assert res_trial.status_code == 200
    assert res_trial.json()["trial"] is True
    assert res_trial.json()["plano"] == "premium"

    # Usuário 3 tenta ativar trial novamente -> Bloqueado com 409
    res_trial_dup = await client.post(
        "/plano/trial", headers={"Authorization": f"Bearer {token_u3}"}
    )
    assert res_trial_dup.status_code == 409

    # Usuário 4 permanece FREE
    res_st4 = await client.get(
        "/plano/meu", headers={"Authorization": f"Bearer {token_u4}"}
    )
    assert res_st4.status_code == 200
    assert res_st4.json()["plano"] == "free"
    assert res_st4.json()["premium_ativo"] is False


# ====================================================================
# 3. TESTES DE EMISSÃO DE RELATÓRIO PDF
# ====================================================================
@pytest.mark.asyncio
async def test_simulacao_download_pdf(client: AsyncClient, setup_5_usuarios):
    tokens = setup_5_usuarios
    token_u1 = tokens["u1_admin"]  # Premium Admin
    token_u4 = tokens["u4_free"]   # Free User

    # 1. Usuário Premium baixa PDF -> Sucesso (200 OK + PDF binary)
    res_pdf_admin = await client.get(
        "/plano/relatorio-pdf", headers={"Authorization": f"Bearer {token_u1}"}
    )
    assert res_pdf_admin.status_code == 200
    assert res_pdf_admin.headers["content-type"] == "application/pdf"
    assert res_pdf_admin.content.startswith(b"%PDF-1.4")
    assert b"RADAR DE FINANCAS" in res_pdf_admin.content

    # 2. Usuário Free tenta baixar PDF -> Negado (403 Forbidden)
    res_pdf_free = await client.get(
        "/plano/relatorio-pdf", headers={"Authorization": f"Bearer {token_u4}"}
    )
    assert res_pdf_free.status_code == 403
    err_msg = res_pdf_free.json().get("error") or res_pdf_free.json().get("detail", "")
    assert "exclusivo" in err_msg.lower()

    # 3. Usuário não autenticado tenta baixar PDF -> Negado (401 Unauthorized)
    res_pdf_anon = await client.get("/plano/relatorio-pdf")
    assert res_pdf_anon.status_code == 401


# ====================================================================
# 4. TESTES DE ERROS DE ACESSO E AUTENTICAÇÃO
# ====================================================================
@pytest.mark.asyncio
async def test_falhas_de_acesso_e_login(client: AsyncClient, setup_5_usuarios):
    u5 = USERS_SIMULATION["u5_unconfirmed"]
    u4 = USERS_SIMULATION["u4_free"]

    # 1. Tentativa de login por usuário NÃO confirmado -> Redirecionamento Gracioso (HTTP 202)
    res_u5 = await client.post(
        "/auth/login", json={"email": u5["email"], "senha": u5["senha"]}
    )
    assert res_u5.status_code == 202
    data_u5 = res_u5.json()
    assert data_u5["require_confirmation"] is True
    assert "destino" in data_u5

    # 2. Tentativa de login com senha incorreta -> Bloqueado (401)
    res_bad_pw = await client.post(
        "/auth/login", json={"email": u4["email"], "senha": "SenhaErrada@99"}
    )
    assert res_bad_pw.status_code == 401
    err_pw = res_bad_pw.json().get("error") or res_bad_pw.json().get("detail", "")
    assert "incorretos" in err_pw.lower() or "inválidos" in err_pw.lower()

    # 3. Tentativa de login com e-mail inexistente -> Bloqueado (401)
    res_bad_email = await client.post(
        "/auth/login", json={"email": "fantasma@radar.com", "senha": "QualquerCoisa123!"}
    )
    assert res_bad_email.status_code == 401

    # 4. Confirmação com código errado -> Bloqueado (400)
    res_bad_code = await client.post(
        "/auth/confirm", json={"email": u5["email"], "codigo": "000000"}
    )
    assert res_bad_code.status_code == 400


# ====================================================================
# 5. TESTES DE SEGURANÇA E TENTATIVAS DE INVASÃO
# ====================================================================
@pytest.mark.asyncio
async def test_seguranca_sqli_xss_traversal(client: AsyncClient):

    # A. SQL Injection em Login
    sqli_payloads = [
        "' OR '1'='1",
        "admin'--",
        "' UNION SELECT NULL, NULL, NULL--",
    ]
    for sqli in sqli_payloads:
        res = await client.post("/auth/login", json={"email": sqli, "senha": sqli})
        # Deve recusar com 401 ou 422 sem vazar erro do SQLite / 500
        assert res.status_code in (401, 422)

    # B. SQL Injection em Confirmação
    res_sqli_conf = await client.post(
        "/auth/confirm", json={"email": "teste@email.com", "codigo": "' OR '1'='1"}
    )
    assert res_sqli_conf.status_code in (400, 422)

    # C. XSS Injection em Cadastro -> Deve ser REJEITADO pela validação de entrada (422)
    xss_nome = "<script>alert('XSS_EVIL')</script>"
    res_reg = await client.post(
        "/auth/register",
        json={"email": "xss_user@radar.com", "senha": "Senha@1234", "nome": xss_nome},
    )
    assert res_reg.status_code == 422  # Validação de nome bloqueia caracteres especiais/HTML

    # D. Path Traversal em rotas públicas
    traversal_paths = [
        "/anuncio/../../../../etc/passwd",
        "/anuncio/..%2f..%2fapp%2fmain.py",
        "/anuncio/..\\..\\windows\\system32",
    ]
    for path in traversal_paths:
        res_trav = await client.get(path)
        assert res_trav.status_code in (400, 404)

    # E. Adulteração de Token JWT (JWT Tampering)
    valid_token = security.create_token(1, "admin@exemplo.com", "premium")
    tampered_token = valid_token[:-5] + "XXXXX"
    res_tampered = await client.get(
        "/plano/meu", headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert res_tampered.status_code == 401
