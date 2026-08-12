# app/core/core.py
"""Core unificado: Config + Logger"""
import os
import logging
import json
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
from pydantic_settings import BaseSettings, SettingsConfigDict

# ============ CONFIGURAÇÃO ============
class Settings(BaseSettings):
    """Configurações centralizadas"""
    ENV: str = "development"
    DEBUG: bool = True
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars-long"
    JWT_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///data/app.db"
    LOG_LEVEL: str = "INFO"
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    ALLOWED_ORIGINS: str = "*"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Singleton de configurações"""
    return Settings()

settings = get_settings()

# ============ LOGGER ============
class Logger:
    """Logger ultra-slim com JSON format"""
    _loggers: Dict[str, 'Logger'] = {}
    
    def __new__(cls, name: str) -> 'Logger':
        if name not in cls._loggers:
            cls._loggers[name] = super().__new__(cls)
        return cls._loggers[name]
    
    def __init__(self, name: str):
        if hasattr(self, '_initialized'):
            return
        
        self.name = name
        self.logger = logging.getLogger(f"app.{name}")
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
        self.logger.propagate = False
        
        # Cria diretório de logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Handler com rotação
        handler = RotatingFileHandler(
            log_dir / f"{name}.log",
            maxBytes=5_000_000,  # 5MB
            backupCount=3
        )
        handler.setFormatter(self._formatter())
        self.logger.addHandler(handler)
        
        self._initialized = True
    
    def _formatter(self):
        """Formatter JSON para facilitar parsing"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "ts": datetime.now().isoformat(timespec='seconds'),
                    "m": record.name.split('.')[-1],
                    "lvl": record.levelname,
                    "msg": record.getMessage(),
                    "ctx": getattr(record, 'extra', {})
                }
                return json.dumps(log_entry, separators=(',', ':'))
        return JSONFormatter()
    
    def _log(self, level: int, msg: str, extra: Optional[Dict] = None):
        if not self.logger.isEnabledFor(level):
            return
        self.logger.log(level, msg, extra={'extra': extra or {}})
    
    def debug(self, msg: str, extra: Optional[Dict] = None):
        self._log(logging.DEBUG, msg, extra)
    
    def info(self, msg: str, extra: Optional[Dict] = None):
        self._log(logging.INFO, msg, extra)
    
    def warning(self, msg: str, extra: Optional[Dict] = None):
        self._log(logging.WARNING, msg, extra)
    
    def error(self, msg: str, extra: Optional[Dict] = None):
        self._log(logging.ERROR, msg, extra)
    
    def critical(self, msg: str, extra: Optional[Dict] = None):
        self._log(logging.CRITICAL, msg, extra)

def get_logger(name: str) -> Logger:
    """Factory para logger"""
    return Logger(name)
