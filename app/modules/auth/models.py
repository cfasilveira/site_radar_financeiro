# app/modules/auth/models.py
"""Modelos Pydantic para autenticação"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import re

try:
    from pydantic import field_validator, ConfigDict
    
    class UserCreate(BaseModel):
        """Dados para criação de usuário"""
        email: EmailStr
        senha: str = Field(..., min_length=8)
        nome: str = Field(..., min_length=2, max_length=100)
        canal: str = Field("email", description="email ou whatsapp")
        whatsapp: Optional[str] = None
        
        @field_validator('canal')
        @classmethod
        def valida_canal(cls, v: str) -> str:
            if v not in ("email", "whatsapp"):
                raise ValueError("Canal deve ser 'email' ou 'whatsapp'")
            return v
        
        @field_validator('whatsapp')
        @classmethod
        def valida_whatsapp(cls, v: Optional[str]) -> Optional[str]:
            if v is None:
                return v
            digits = re.sub(r'\D', '', v)
            if len(digits) < 10:
                raise ValueError("WhatsApp deve ter DDD + número (ex.: 5511999999999)")
            return v
        
        @field_validator('senha')
        @classmethod
        def valida_senha(cls, v: str) -> str:
            """Valida força da senha"""
            if len(v) < 8:
                raise ValueError("Senha deve ter no mínimo 8 caracteres")
            if not re.search(r'[A-Z]', v):
                raise ValueError("Senha deve ter pelo menos uma maiúscula")
            if not re.search(r'[0-9]', v):
                raise ValueError("Senha deve ter pelo menos um número")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError("Senha deve ter pelo menos um caractere especial")
            return v
        
        @field_validator('nome')
        @classmethod
        def valida_nome(cls, v: str) -> str:
            """Valida nome (apenas letras e espaços)"""
            if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', v):
                raise ValueError("Nome deve conter apenas letras e espaços")
            return v.strip()

except ImportError:
    from pydantic import validator
    
    class UserCreate(BaseModel):
        """Dados para criação de usuário (Pydantic v1)"""
        email: EmailStr
        senha: str = Field(..., min_length=8)
        nome: str = Field(..., min_length=2, max_length=100)
        
        @validator('senha')
        def valida_senha(cls, v: str) -> str:
            if len(v) < 8:
                raise ValueError("Senha deve ter no mínimo 8 caracteres")
            if not re.search(r'[A-Z]', v):
                raise ValueError("Senha deve ter pelo menos uma maiúscula")
            if not re.search(r'[0-9]', v):
                raise ValueError("Senha deve ter pelo menos um número")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError("Senha deve ter pelo menos um caractere especial")
            return v
        
        @validator('nome')
        def valida_nome(cls, v: str) -> str:
            if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', v):
                raise ValueError("Nome deve conter apenas letras e espaços")
            return v.strip()

class UserLogin(BaseModel):
    """Dados para login"""
    email: EmailStr
    senha: str

class UserConfirm(BaseModel):
    """Confirmação de cadastro com código recebido"""
    email: EmailStr
    codigo: str = Field(..., min_length=4, max_length=8)

class UserResponse(BaseModel):
    """Resposta com dados do usuário"""
    id: int
    email: str
    nome: str
    plano: str
    confirmado: bool = False
    canal: str = "email"
    token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ConfirmResponse(BaseModel):
    """Resposta da etapa de confirmação"""
    ok: bool
    mensagem: str
    codigo_demo: Optional[str] = None

class PendingConfirmationResponse(BaseModel):
    """
    Retornado quando o usuário tenta logar mas ainda não confirmou o cadastro.
    Carrega os dados necessários para o frontend guiar o usuário ao passo correto
    sem deixá-lo no 'escuro' — padrão Fail Gracefully.
    """
    require_confirmation: bool = True
    email: str
    canal: str          # 'email' ou 'whatsapp'
    destino: str        # endereço para onde o código foi enviado (mascarado)
    codigo_demo: Optional[str] = None  # só presente em ambiente de demonstração
    mensagem: str = "Seu cadastro ainda não foi confirmado."
    proximos_passos: str = "Verifique seu e-mail/WhatsApp e insira o código de 6 dígitos abaixo."
