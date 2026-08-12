# app/modules/realtime/manager.py
"""Gerenciador de conexões SSE simplificado"""
import asyncio
from typing import Dict, Set
from app.core.core import get_logger

logger = get_logger("realtime")

class RealtimeManager:
    """Gerencia conexões SSE com cleanup automático"""
    
    def __init__(self):
        self._connections: Dict[int, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    async def add(self, user_id: int, queue: asyncio.Queue):
        """Adiciona uma conexão para um usuário"""
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(queue)
        
        # Inicia cleanup se necessário
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.debug(f"Conexão adicionada", {"user_id": user_id})
    
    async def remove(self, user_id: int, queue: asyncio.Queue):
        """Remove uma conexão de um usuário (chamado no disconnect)"""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(queue)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.debug("Conexão removida", {"user_id": user_id})
    
    async def broadcast(self, user_id: int, data: dict):
        """Envia dados para todas as conexões de um usuário"""
        if user_id not in self._connections:
            return
        
        async with self._lock:
            dead = set()
            for queue in self._connections[user_id]:
                try:
                    await asyncio.wait_for(queue.put(data), timeout=0.5)
                except (asyncio.CancelledError, asyncio.TimeoutError, RuntimeError):
                    dead.add(queue)
                except Exception as e:
                    logger.error("Erro no broadcast", {"error": str(e)})
                    dead.add(queue)
            
            # Remove conexões mortas
            for queue in dead:
                self._connections[user_id].discard(queue)
            
            # Remove usuário se não tiver conexões
            if not self._connections[user_id]:
                del self._connections[user_id]
    
    async def _cleanup_loop(self):
        """Loop de limpeza periódica"""
        while True:
            await asyncio.sleep(60)  # A cada minuto
            
            async with self._lock:
                for user_id in list(self._connections.keys()):
                    # Remove queues fechadas (tratamento seguro)
                    self._connections[user_id] = {
                        q for q in self._connections[user_id]
                        if not getattr(q, '_closed', False)
                    }
                    
                    if not self._connections[user_id]:
                        del self._connections[user_id]
            
            logger.debug("Cleanup executado", {
                "conexoes_ativas": sum(len(q) for q in self._connections.values())
            })
    
    def get_active_count(self) -> int:
        """Retorna número total de conexões ativas"""
        return sum(len(q) for q in self._connections.values())

# Instância global
realtime = RealtimeManager()
