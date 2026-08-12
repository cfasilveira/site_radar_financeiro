# scripts/backup_db.py
"""Script para realizar backup seguro do banco de dados SQLite (compatível com modo WAL)"""
import os
import shutil
import sqlite3
from datetime import datetime
from app.core.core import settings


def main():
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"Erro: Banco de dados não encontrado em {db_path}")
        return

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "..", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"app_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    print(f"Iniciando backup de {db_path} -> {backup_path}...")

    # Usa a API de backup online do sqlite3 para garantir consistência mesmo com WAL
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        size_kb = round(os.path.getsize(backup_path) / 1024, 2)
        print(f"✅ Backup concluído com sucesso! Arquivo: {backup_path} ({size_kb} KB)")
    except Exception as e:
        print(f"❌ Falha ao realizar backup: {e}")


if __name__ == "__main__":
    main()
