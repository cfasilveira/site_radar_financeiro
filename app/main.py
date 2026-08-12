# app/main.py
"""Entry point da aplicação Radar de Finanças"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from app.core.core import get_logger, settings
from app.shared.middleware import Middleware
from app.shared.database import db
from app.modules.auth import router as auth_router
from app.modules.realtime import router as realtime_router
from app.modules.indicators import router as indicators_router
from app.modules.noticias import router as noticias_router
from app.modules.plano import router as plano_router
from app.modules.ads import router as ads_router
from app.modules.ai_analysis import router as ai_analysis_router

logger = get_logger("app")

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida"""
    logger.info("Iniciando aplicação...")

    try:
        await db.init()
        logger.info("Banco de dados inicializado")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise

    yield

    logger.info("Desligando aplicação...")

# Cria app
app = FastAPI(
    title="Radar de Finanças API",
    version="1.0.0",
    description="Portal e API do Radar Financeiro MVP com SSE em tempo real e autenticação JWT",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# CORS (origens configuradas em ALLOWED_ORIGINS, separadas por vírgula)
_allowed = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True if "*" not in _allowed else False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(Middleware)

# Templates estáticos
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Rotas
app.include_router(auth_router)
app.include_router(realtime_router)
app.include_router(indicators_router)
app.include_router(noticias_router)
app.include_router(plano_router)
app.include_router(ads_router)
app.include_router(ai_analysis_router)

@app.get("/")
async def index(request: Request):
    """Portal principal"""
    return templates.TemplateResponse(request, "index.html")

@app.get("/health")
async def healthcheck():
    """Endpoint de saúde para monitoramento"""
    import platform
    return {
        "status": "ok",
        "env": settings.ENV,
        "version": "1.0.0",
        "database": "sqlite",
        "python": platform.python_version()
    }

# Handlers de erro
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handler para exceções HTTP"""
    logger.warning(
        f"HTTP {exc.status_code}",
        {"path": request.url.path, "detail": exc.detail}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handler para exceções genéricas (fallback)"""
    logger.error(
        "Exceção não tratada",
        {"path": request.url.path, "error": str(exc)}
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erro interno do servidor",
            "message": "Tente novamente mais tarde" if not settings.DEBUG else str(exc)
        }
    )