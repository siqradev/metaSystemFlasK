import sqlite3
import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash
import dotenv

# 1. Localização inteligente do .env
if getattr(sys, 'frozen', False):
    # Se for o .exe gerado pelo GitHub Actions, o .env deve estar na pasta do .exe
    CWD = os.path.dirname(sys.executable)
else:
    CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_PATH = os.path.join(CWD, '.env')
dotenv.load_dotenv(ENV_PATH)

def get_db():
    # Buscamos a URL do banco SEMPRE de dentro da função para evitar travamento no boot
    db_path = os.getenv("DATABASE_URL")
    
    if not db_path:
        raise ConnectionError("DATABASE_URL não configurada no arquivo .env")

    # Tenta resolver caminhos UNC (\\int.cagece...) de forma robusta
    try:
        # check_same_thread=False é vital para Flask + SQLite
        # timeout=30 evita o erro 'database is locked' quando dois colegas salvam ao mesmo tempo
        conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # O MODO WAL é obrigatório para rede (permite leitura e escrita simultânea)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        return conn
    except sqlite3.OperationalError as e:
        print(f"Erro de acesso à rede: {e}")
        # Retorna None ou levanta erro tratado para a interface
        return None

def init_db():
    """Cria as tabelas apenas se o banco central não as tiver"""
    conn = get_db()
    if conn:
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT UNIQUE,
                username TEXT UNIQUE,
                password TEXT,
                nivel TEXT DEFAULT 'usuario')''')
            
            conn.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_exibicao TEXT UNIQUE)''')

            # Admin Padrão
            if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
                hash_pwd = generate_password_hash('admin123')
                conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                             ('0000', 'admin', hash_pwd, 'admin'))
            conn.commit()
        finally:
            conn.close()