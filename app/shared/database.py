# app/shared/database.py
"""Database simplificado com retry automático e helpers aiosqlite"""
import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
from typing import AsyncGenerator, Optional, List, Any, Dict
from app.core.core import settings

class Database:
    """Database enxuto e eficiente"""
    
    def __init__(self):
        self.path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._max_retries = 3
    
    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Conexão com retry automático em caso de lock e helpers fetch_one/fetch_all"""
        for attempt in range(self._max_retries):
            try:
                conn = await aiosqlite.connect(
                    str(self.path),
                    timeout=10,
                    isolation_level=None  # Auto-commit
                )
                
                # Configurações de performance
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.execute("PRAGMA cache_size = -10000")
                await conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = aiosqlite.Row
                
                # Anexa helpers fetch_one e fetch_all na própria conexão
                async def fetch_one(query: str, params: tuple = ()):
                    cursor = await conn.execute(query, params)
                    return await cursor.fetchone()
                
                async def fetch_all(query: str, params: tuple = ()):
                    cursor = await conn.execute(query, params)
                    return await cursor.fetchall()
                
                setattr(conn, "fetch_one", fetch_one)
                setattr(conn, "fetch_all", fetch_all)
                
                yield conn
                await conn.close()
                return
                
            except aiosqlite.OperationalError as e:
                if "locked" in str(e).lower() and attempt < self._max_retries - 1:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Backoff
                    continue
                raise
    
    async def init(self):
        """Inicializa schema do banco"""
        async with self.connect() as conn:
            # Usuários
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    senha_hash TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    plano TEXT DEFAULT 'free',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ultimo_login TIMESTAMP
                )
            """)

            # Migração idempotente: colunas de confirmação e WhatsApp
            await self._migrate_column(conn, "usuarios", "codigo_confirmacao", "TEXT")
            await self._migrate_column(conn, "usuarios", "confirmado", "INTEGER DEFAULT 0")
            await self._migrate_column(conn, "usuarios", "canal", "TEXT DEFAULT 'email'")
            await self._migrate_column(conn, "usuarios", "whatsapp", "TEXT")
            await self._migrate_column(conn, "usuarios", "assinatura_ate", "TEXT")
            await self._migrate_column(conn, "usuarios", "trial_usado", "INTEGER DEFAULT 0")

            # Contato para negociação de publicidade
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS contatos_anuncio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT NOT NULL,
                    whatsapp TEXT,
                    espaco TEXT NOT NULL,
                    mensagem TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dados para gráficos
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dados_metricas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL,
                    categoria TEXT NOT NULL,
                    valor REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
                )
            """)
            
            # Tabela de Auditoria do Módulo de IA Preditiva
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ia_auditoria (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    categoria TEXT NOT NULL,
                    modelo TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    precisao_pct REAL NOT NULL,
                    tempo_ms REAL NOT NULL,
                    checksum_sha256 TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
                )
            """)

            # Índices para performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ia_auditoria_user 
                ON ia_auditoria(usuario_id, timestamp DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_user_time 
                ON dados_metricas(usuario_id, timestamp DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usuarios_email 
                ON usuarios(email)
            """)
    
    async def _migrate_column(self, conn, table: str, column: str, definition: str):
        """Adiciona coluna se não existir (migração idempotente para SQLite)"""
        cols = await conn.fetch_all(f"PRAGMA table_info({table})")
        names = {c["name"] for c in cols}
        if column not in names:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def execute(self, query: str, params: tuple = ()):
        """Helper para executar queries"""
        async with self.connect() as conn:
            return await conn.execute(query, params)

    async def fetch_one(self, query: str, params: tuple = ()):
        """Helper para buscar um registro"""
        async with self.connect() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: tuple = ()):
        """Helper para buscar múltiplos registros"""
        async with self.connect() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()

# Instância global
db = Database()
