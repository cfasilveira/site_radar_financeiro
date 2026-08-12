# app/shared/security.py
"""Security unificado: Crypto + JWT + Validações"""
import bcrypt
import jwt
import secrets
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException
from app.core.core import settings

class Security:
    """Serviço de segurança unificado e otimizado"""
    
    # Configurações
    _secret = settings.JWT_SECRET_KEY
    _algorithm = "HS256"
    _expire_minutes = settings.JWT_EXPIRE_MINUTES
    
    # Regex compilada uma vez (lazy)
    _email_regex = None
    
    # ============ CRYPTO ============
    @classmethod
    def hash_password(cls, password: str) -> str:
        """Gera hash com bcrypt usando salt seguro"""
        if not password:
            return ""
        
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')
    
    @classmethod
    def verify_password(cls, password: str, hashed: str) -> bool:
        """Verifica senha com fallback seguro"""
        # Fail Fast
        if not password or not hashed:
            return False
        
        # Valida formato do hash
        if not hashed.startswith('$2b$') and not hashed.startswith('$2a$'):
            return False
        
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed.encode('utf-8')
            )
        except (ValueError, TypeError):
            # Fallback: não expõe detalhes
            return False
    
    @classmethod
    def generate_token(cls, length: int = 32) -> str:
        """Gera token criptográfico seguro"""
        return secrets.token_urlsafe(length)
    
    # ============ JWT ============
    @classmethod
    def create_token(cls, user_id: int, email: str, plano: str) -> str:
        """Cria token JWT"""
        payload = {
            "sub": str(user_id),
            "email": email,
            "plano": plano,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=cls._expire_minutes)
        }
        return jwt.encode(payload, cls._secret, algorithm=cls._algorithm)
    
    @classmethod
    def verify_token(cls, token: str) -> Dict[str, Any]:
        """Verifica token com validação rigorosa"""
        if not token:
            raise HTTPException(401, "Token não fornecido")
        
        try:
            return jwt.decode(
                token,
                cls._secret,
                algorithms=[cls._algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "require": ["sub", "exp"]
                }
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expirado")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Token inválido")
    
    @classmethod
    def get_user_id_from_token(cls, token: str) -> int:
        """Extrai user_id do token (útil para middlewares)"""
        payload = cls.verify_token(token)
        return int(payload["sub"])
    
    # ============ VALIDAÇÕES ============
    @classmethod
    def validar_email(cls, email: str) -> bool:
        """Valida email com regex compilada uma vez"""
        if cls._email_regex is None:
            cls._email_regex = re.compile(
                r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            )
        return bool(cls._email_regex.match(email))
    
    @classmethod
    def validar_senha(cls, senha: str) -> Tuple[bool, Optional[str]]:
        """Valida força da senha - retorna (válido, mensagem_erro)"""
        if len(senha) < 8:
            return False, "Senha deve ter no mínimo 8 caracteres"
        if not re.search(r'[A-Z]', senha):
            return False, "Senha deve ter pelo menos uma maiúscula"
        if not re.search(r'[0-9]', senha):
            return False, "Senha deve ter pelo menos um número"
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', senha):
            return False, "Senha deve ter pelo menos um caractere especial"
        return True, None

# Instância global
security = Security()
