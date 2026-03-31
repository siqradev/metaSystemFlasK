import sqlite3
import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash
import dotenv

# 1. Localização inteligente do .env (Mantido original)
if getattr(sys, 'frozen', False):
    CWD = os.path.dirname(sys.executable)
else:
    CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_PATH = os.path.join(CWD, '.env')
dotenv.load_dotenv(ENV_PATH)

def get_db():
    db_path = os.getenv("DATABASE_URL")
    
    if not db_path:
        print("ERRO: DATABASE_URL não encontrada no .env")
        return None

    # AJUSTE EXTRA: Limpa aspas e espaços que podem vir do .env e bugar o Windows
    db_path = db_path.strip().replace('"', '').replace("'", "")

    try:
        # AJUSTE 1: isolation_level=None impede que o Windows 11 bloqueie o arquivo na rede
        conn = sqlite3.connect(
            db_path, 
            timeout=60, 
            check_same_thread=False, 
            isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        
        # AJUSTE 2: Tenta o modo WAL, mas não morre se a rede for restrita
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except:
            pass # Segue no modo padrão se a rede não deixar criar arquivos de log
            
        return conn
    except Exception as e:
        print(f"Erro de conexão física ao banco: {e}")
        return None

def init_db():
    """Cria as tabelas apenas se o banco central não as tiver"""
    db = get_db()
    if db:
        try:
            # Iniciamos uma transação manual já que usamos isolation_level=None
            db.execute("BEGIN")
            
            db.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT UNIQUE,
                username TEXT UNIQUE,
                password TEXT,
                nivel TEXT DEFAULT 'usuario')''')
            
            db.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_exibicao TEXT UNIQUE)''')

            if not db.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
                hash_pwd = generate_password_hash('admin123')
                db.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                             ('0000', 'admin', hash_pwd, 'admin'))
            
            db.execute("COMMIT")
        except Exception as e:
            db.execute("ROLLBACK")
            print(f"Erro ao criar tabelas: {e}")
        finally:
            db.close()# Versao Final de Rede 2026
