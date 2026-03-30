import sqlite3
import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash
import dotenv

# 1. Localização inteligente do .env (Mantido exatamente como o seu)
if getattr(sys, 'frozen', False):
    CWD = os.path.dirname(sys.executable)
else:
    CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_PATH = os.path.join(CWD, '.env')
dotenv.load_dotenv(ENV_PATH)

def get_db():
    db_path = os.getenv("DATABASE_URL")
    
    if not db_path:
        # Importante para você ver no terminal se o .env carregou
        print("ERRO: DATABASE_URL não encontrada no .env")
        return None

    try:
        # AJUSTE 1: Aumentamos para 60s o timeout para dar tempo da rede responder
        conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # AJUSTE 2: Fallback do WAL. Se a rede da Cagece não permitir WAL, 
        # ele usa o modo padrão sem derrubar o sistema (Erro 500).
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.OperationalError:
            # Se cair aqui, é porque a pasta de rede é restrita. 
            # O sistema continuará funcionando no modo estável.
            pass
            
        return conn
    except Exception as e:
        print(f"Erro de conexão física ao banco: {e}")
        return None

def init_db():
    """Cria as tabelas apenas se o banco central não as tiver"""
    db = get_db()
    if db:
        try:
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
            db.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")
        finally:
            db.close()