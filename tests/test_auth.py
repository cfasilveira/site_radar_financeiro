# tests/test_auth.py
"""Testes de autenticação com confirmação de cadastro"""
import pytest
from httpx import AsyncClient
from app.shared.security import security
from app.shared.database import db

USER = {
    "email": "teste@email.com",
    "senha": "Senha@123",
    "nome": "Usuário Teste",
}


def _confirma_usuario(email: str, codigo: str) -> str:
    """Força confirmação direto no banco e retorna token (helper de teste)"""
    return security.create_token(999, email, "free")


@pytest.mark.asyncio
async def test_register_retorna_confirmacao(client: AsyncClient):
    res = await client.post("/auth/register", json=USER)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "codigo" in data["mensagem"].lower() or "confirmação" in data["mensagem"].lower()
    assert data["codigo_demo"]  # modo demo devolve o código


@pytest.mark.asyncio
async def test_register_email_duplicado(client: AsyncClient):
    res = await client.post("/auth/register", json=USER)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_senha_fraca(client: AsyncClient):
    payload = {**USER, "email": "fraco@email.com", "senha": "abc"}
    res = await client.post("/auth/register", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_whatsapp_invalido(client: AsyncClient):
    payload = {**USER, "email": "whats@email.com", "canal": "whatsapp", "whatsapp": "123"}
    res = await client.post("/auth/register", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_bloqueado_sem_confirmacao(client: AsyncClient):
    """
    Antes de confirmar, o login deve retornar HTTP 202 (Fail Gracefully)
    com um payload estruturado que guia o usuário para a tela de confirmação.
    """
    unconfirmed_user = {
        "email": "pendente_test@email.com",
        "senha": "Senha@123",
        "nome": "Usuário Pendente",
    }
    await client.post("/auth/register", json=unconfirmed_user)

    res = await client.post(
        "/auth/login", json={"email": unconfirmed_user["email"], "senha": unconfirmed_user["senha"]}
    )
    # HTTP 202: aceito, mas ação pendente — não é erro, é orientação
    assert res.status_code == 202
    data = res.json()
    assert data["require_confirmation"] is True
    assert data["email"] == unconfirmed_user["email"]
    assert "destino" in data                 # destino mascarado para privacidade
    assert "mensagem" in data
    assert "proximos_passos" in data
    assert data["codigo_demo"] is not None   # ambiente de dev expõe o código


@pytest.mark.asyncio
async def test_confirm_codigo_errado(client: AsyncClient):
    res = await client.post(
        "/auth/confirm", json={"email": USER["email"], "codigo": "000000"}
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_confirm_sucesso_e_login(client: AsyncClient):
    # Busca o código gerado no cadastro (modo demo escreve no banco)
    async with db.connect() as conn:
        row = await conn.fetch_one(
            "SELECT codigo_confirmacao FROM usuarios WHERE email = ?", (USER["email"],)
        )
        codigo = row["codigo_confirmacao"]

    res = await client.post(
        "/auth/confirm", json={"email": USER["email"], "codigo": codigo}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["confirmado"] is True
    assert data["plano"] == "free"
    assert data["token"]

    # Depois de confirmado, login funciona
    res = await client.post(
        "/auth/login", json={"email": USER["email"], "senha": USER["senha"]}
    )
    assert res.status_code == 200
    assert res.json()["confirmado"] is True


@pytest.mark.asyncio
async def test_login_senha_errada(client: AsyncClient):
    res = await client.post(
        "/auth/login", json={"email": USER["email"], "senha": "Errada@1"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_usuario_inexistente(client: AsyncClient):
    res = await client.post(
        "/auth/login", json={"email": "nada@email.com", "senha": "Qualquer@1"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    res = await client.post("/auth/logout")
    assert res.status_code == 200