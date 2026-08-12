# app/modules/ads/routes.py
"""Rotas de publicidade: listagem de espaços e página de negociação"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pathlib import Path
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.modules.ads.service import service

router = APIRouter(tags=["ads"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent.parent / "templates"))

class ContatoAnuncio(BaseModel):
    nome: str = Field(..., min_length=2)
    email: EmailStr
    whatsapp: Optional[str] = None
    mensagem: Optional[str] = None

@router.get("/espacos-publicidade")
async def listar_espacos():
    """Lista os espaços publicitários disponíveis no portal"""
    return {"espacos": service.listar()}

@router.get("/anuncio/{slug}")
async def pagina_negociacao(slug: str, request: Request):
    """Página de negociação de um espaço publicitário"""
    espaco = service.obter(slug)
    return templates.TemplateResponse(request, "anuncio.html", {"espaco": espaco})

@router.post("/anuncio/{slug}/contato")
async def interesse_publicidade(slug: str, contato: ContatoAnuncio):
    """Registra contato de quem quer anunciar no espaço"""
    return await service.registrar_interesse(slug, contato.model_dump())