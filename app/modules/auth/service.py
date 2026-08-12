# app/modules/auth/service.py
"""Serviço de autenticação com confirmação via e-mail/WhatsApp (código simulado)"""
import secrets
from fastapi import HTTPException, status
from app.core.core import get_logger, settings
from app.shared.database import db
from app.shared.security import security
from fastapi.responses import JSONResponse
from app.modules.auth.models import (
    UserCreate, UserLogin, UserResponse, UserConfirm,
    ConfirmResponse, PendingConfirmationResponse
)

logger = get_logger("auth")

class AuthService:
    """Serviço de autenticação enxuto"""
    
    @staticmethod
    def _gerar_codigo() -> str:
        """Gera código de confirmação de 6 dígitos"""
        return f"{secrets.randbelow(1000000):06d}"
    
    @staticmethod
    def _enviar_codigo(canal: str, destino: str, codigo: str):
        """Simula envio do código. Em produção plugue SMTP/WhatsApp API aqui."""
        tipo = "e-mail" if canal == "email" else "WhatsApp"
        logger.info(
            "Código de confirmação enviado (simulado)",
            {"canal": tipo, "destino": destino, "codigo": codigo}
        )
        return settings.DEBUG
    
    @staticmethod
    async def register(data: UserCreate) -> ConfirmResponse:
        """Registra novo usuário e dispara confirmação (email/whatsapp)"""
        # Fail Fast: valida email
        if not security.validar_email(data.email):
            logger.warning("Email inválido", {"email": data.email})
            raise HTTPException(400, "Email inválido")
        
        destino = data.whatsapp if data.canal == "whatsapp" else data.email
        
        # Verifica duplicidade
        async with db.connect() as conn:
            exists = await conn.fetch_one(
                "SELECT id FROM usuarios WHERE email = ?", 
                (data.email,)
            )
            if exists:
                logger.warning("Email já cadastrado", {"email": data.email})
                raise HTTPException(409, "Email já cadastrado")
            
            # Insere usuário com código de confirmação
            hashed = security.hash_password(data.senha)
            codigo = AuthService._gerar_codigo()
            await conn.execute(
                """
                INSERT INTO usuarios (email, senha_hash, nome, canal, whatsapp, codigo_confirmacao, confirmado)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (data.email, hashed, data.nome, data.canal, data.whatsapp, codigo)
            )
        
        modo_demo = AuthService._enviar_codigo(data.canal, destino, codigo)
        
        logger.info("Cadastro pendente de confirmação", {"email": data.email})
        
        return ConfirmResponse(
            ok=True,
            mensagem=f"Confirmação enviada para o {destino}",
            codigo_demo=codigo if modo_demo else None
        )
    
    @staticmethod
    async def confirmar(data: UserConfirm) -> UserResponse:
        """Confirma o cadastro com o código recebido"""
        async with db.connect() as conn:
            user = await conn.fetch_one(
                """
                SELECT id, email, nome, plano, confirmado, codigo_confirmacao, canal
                FROM usuarios WHERE email = ?
                """,
                (data.email,)
            )
            if not user:
                raise HTTPException(404, "Cadastro não encontrado")
            
            if user["confirmado"]:
                raise HTTPException(400, "Cadastro já confirmado")
            
            if not user["codigo_confirmacao"] or user["codigo_confirmacao"] != data.codigo:
                logger.warning("Código inválido", {"email": data.email})
                raise HTTPException(400, "Código de confirmação inválido")
            
            await conn.execute(
                "UPDATE usuarios SET confirmado = 1, codigo_confirmacao = NULL WHERE id = ?",
                (user["id"],)
            )
            user = dict(user)
            user["confirmado"] = 1
        
        logger.info("Cadastro confirmado", {"user_id": user["id"]})
        return await AuthService._emit_token(user)
    
    @staticmethod
    async def _emit_token(user) -> UserResponse:
        """Gera token e monta resposta"""
        token = security.create_token(user["id"], user["email"], user["plano"])
        return UserResponse(
            id=user["id"],
            email=user["email"],
            nome=user["nome"],
            plano=user["plano"],
            confirmado=bool(user["confirmado"]),
            canal=user["canal"],
            token=token
        )
    
    @staticmethod
    def _mascarar_destino(canal: str, destino: str) -> str:
        """Mascara parcialmente o destino para privacidade na resposta de erro gracioso"""
        if canal == "whatsapp" or not destino:
            # Mantém últimos 4 dígitos
            digits = ''.join(filter(str.isdigit, destino))
            return f"****{digits[-4:]}" if len(digits) >= 4 else "****"
        # E-mail: mantém primeiros 2 chars + domínio
        parts = destino.split("@")
        if len(parts) == 2:
            local = parts[0]
            visible = local[:2] + "*" * max(0, len(local) - 2)
            return f"{visible}@{parts[1]}"
        return destino

    @staticmethod
    async def login(data: UserLogin) -> UserResponse:
        """Login de usuário (exige cadastro confirmado)"""
        async with db.connect() as conn:
            # Busca usuário
            user_row = await conn.fetch_one(
                """
                SELECT id, email, nome, senha_hash, plano, confirmado, canal, whatsapp, codigo_confirmacao 
                FROM usuarios 
                WHERE email = ?
                """,
                (data.email,)
            )
            
            # Early Return: usuário não existe
            if not user_row:
                logger.warning("Login - usuário não existe", {"email": data.email})
                raise HTTPException(401, "Email ou senha incorretos")
            
            user = dict(user_row)

            # Early Return: senha incorreta
            if not security.verify_password(data.senha, user["senha_hash"]):
                logger.warning("Login - senha incorreta", {"user_id": user["id"]})
                raise HTTPException(401, "Email ou senha incorretos")
            
            # Fail Gracefully: cadastro não confirmado
            # Em vez de bloquear com 403 seco, devolvemos HTTP 202 com um payload
            # estruturado que permite ao frontend mostrar diretamente a tela de confirmação.
            if not user["confirmado"]:
                logger.warning(
                    "Login - cadastro pendente de confirmação (redirecionando graciosamente)",
                    {"user_id": user["id"], "canal": user["canal"]}
                )
                canal = user.get("canal") or "email"
                destino_raw = data.email if canal == "email" else (
                    user.get("whatsapp") or data.email
                )
                destino_mascarado = AuthService._mascarar_destino(canal, destino_raw)

                # Reenvia o código se necessário (mantém o mesmo já gravado no banco)
                codigo_atual = user.get("codigo_confirmacao")
                modo_demo = settings.DEBUG

                payload = PendingConfirmationResponse(
                    require_confirmation=True,
                    email=data.email,
                    canal=canal,
                    destino=destino_mascarado,
                    codigo_demo=codigo_atual if modo_demo else None,
                    mensagem="Seu cadastro ainda não foi confirmado.",
                    proximos_passos=(
                        f"Verifique seu {'e-mail' if canal == 'email' else 'WhatsApp'} "
                        f"em {destino_mascarado} e insira o código de 6 dígitos para continuar."
                    ),
                )
                return JSONResponse(status_code=202, content=payload.model_dump())
            
            # Atualiza último login
            await conn.execute(
                "UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user["id"],)
            )
        
        # Gera token
        token = security.create_token(user["id"], user["email"], user["plano"])
        
        logger.info("Login bem-sucedido", {"user_id": user["id"]})
        
        return UserResponse(
            id=user["id"],
            email=user["email"],
            nome=user["nome"],
            plano=user["plano"],
            confirmado=bool(user["confirmado"]),
            canal=user["canal"],
            token=token
        )
