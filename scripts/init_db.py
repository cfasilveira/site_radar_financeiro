# scripts/init_db.py
"""Script para popular banco com dados iniciais (admin + métricas de exemplo)"""
import asyncio
import random
from datetime import datetime, timedelta
from app.shared.database import db
from app.shared.security import security


async def main():
    """Popula dados de exemplo"""
    print("Semeando banco de dados...")
    await db.init()

    # Cria usuário admin (plano premium, acesso ao stream SSE)
    async with db.connect() as conn:
        admin = await conn.fetch_one(
            "SELECT id, confirmado FROM usuarios WHERE email = 'admin@exemplo.com'"
        )

        if not admin:
            hashed = security.hash_password("Admin@123")
            await conn.execute(
                """
                INSERT INTO usuarios (email, senha_hash, nome, plano, confirmado)
                VALUES (?, ?, ?, ?, 1)
                """,
                ("admin@exemplo.com", hashed, "Administrador", "premium"),
            )
            admin_id = (await conn.fetch_one(
                "SELECT id FROM usuarios WHERE email = 'admin@exemplo.com'"
            ))["id"]
            print(f"Admin criado: ID {admin_id} (email: admin@exemplo.com / senha: Admin@123)")
        else:
            admin_id = admin["id"]
            # Garante que usuários antigos tenham a coluna confirmado preenchida
            if not admin["confirmado"]:
                await conn.execute(
                    "UPDATE usuarios SET confirmado = 1 WHERE id = ?", (admin_id,)
                )
            print(f"Admin já existente: ID {admin_id}")

    # Cria dados de exemplo para os gráficos
    async with db.connect() as conn:
        count = await conn.fetch_one(
            "SELECT COUNT(*) as total FROM dados_metricas"
        )
        if count["total"] > 0:
            print("Métricas já existem, pulando...")
            return

        categorias = ["Receita", "Visitas", "Conversões", "Volume"]
        now = datetime.now()
        rows = []
        for i in range(120):
            ts = now - timedelta(minutes=5 * i)
            categoria = random.choice(categorias)
            valor = round(random.uniform(500, 9000), 2)
            rows.append((admin_id, categoria, valor, ts.strftime("%Y-%m-%d %H:%M:%S")))

        await conn.executemany(
            """
            INSERT INTO dados_metricas (usuario_id, categoria, valor, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        print(f"Registradas {len(rows)} métricas de exemplo para o admin")


if __name__ == "__main__":
    asyncio.run(main())