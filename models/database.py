import sqlite3
import os
import sys
import platform # NOVO: Para detectar Windows ou Linux
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
    
    # --- AJUSTE PARA EVITAR ERRO NO GITHUB/LINUX ---
    if platform.system() == "Windows":
        # Caminho oficial da rede/local Windows
        backup_dir = r"C:\Banco de Dados SystemDataCagece"
    else:
        # Se for Linux (GitHub ou seu PC), cria na pasta do usuário (~/)
        # Isso evita erro de "Pasta C:\ não encontrada"
        backup_dir = os.path.join(os.path.expanduser("~"), "SystemDataCagece_Linux")
    
    backup_path = os.path.join(backup_dir, "database.db")
    # -----------------------------------------------

    if db_path:
        db_path = db_path.strip().replace('"', '').replace("'", "")

    conn = None
    
    # TENTATIVA 1: REDE (W:\)
    if db_path:
        try:
            folder_rede = os.path.dirname(db_path)
            # Só tenta criar a pasta se o drive (ex: W:) existir
            if os.path.exists(os.path.splitdrive(db_path)[0] or folder_rede):
                if folder_rede and not os.path.exists(folder_rede):
                    os.makedirs(folder_rede, exist_ok=True)
                
                conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False, isolation_level=None)
                print(f"[*] Conectado via REDE: {db_path}")
        except:
            pass # Falha silenciosa para ir para o backup local

    # TENTATIVA 2: BACKUP (C:\ no Windows ou ~/ no Linux)
    if conn is None:
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)
            
            conn = sqlite3.connect(backup_path, timeout=60, check_same_thread=False, isolation_level=None)
            print(f"[*] Conectado LOCALMENTE: {backup_path}")
        except Exception as e:
            # Fallback de emergência (Cria na pasta do projeto se o C: falhar)
            print(f"[!] Falha no backup fixo: {e}. Criando na pasta raiz.")
            conn = sqlite3.connect("database.db", timeout=60, check_same_thread=False, isolation_level=None)

    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except:
        pass 
        
    return conn

# A função init_db() continua exatamente igual...

def init_db():
    """Cria as tabelas apenas se o banco central não as tiver"""
    db = get_db()
    if db:
        try:
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
            db.close()