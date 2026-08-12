# app/modules/auth/routes.py
"""Rotas de autenticação"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.modules.auth.service import AuthService
from app.modules.auth.models import (
    UserCreate, UserLogin, UserResponse, UserConfirm, ConfirmResponse
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=ConfirmResponse)
async def register(data: UserCreate):
    """Registra usuário e envia código de confirmação (email/WhatsApp)"""
    return await AuthService.register(data)

@router.post("/confirm", response_model=UserResponse)
async def confirm(data: UserConfirm):
    """Confirma cadastro com código enviado"""
    return await AuthService.confirmar(data)

@router.post("/login")  # response_model omitido: retorno pode ser UserResponse ou JSONResponse(202)
async def login(data: UserLogin):
    """Faz login do usuário. Retorna UserResponse em sucesso ou HTTP 202 (Fail Gracefully) quando o cadastro ainda não foi confirmado."""
    return await AuthService.login(data)

@router.post("/logout")
async def logout():
    """Logout (cliente deve descartar token)"""
    return {"message": "Logout realizado com sucesso"}
