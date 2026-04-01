import sqlite3
import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash
import dotenv

# 1. Localização inteligente do .env (Mantido original conforme seu pedido)
if getattr(sys, 'frozen', False):
    CWD = os.path.dirname(sys.executable)
else:
    # Se o arquivo está em /models/database.py, subimos um nível para achar o .env na raiz
    CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_PATH = os.path.join(CWD, '.env')
dotenv.load_dotenv(ENV_PATH)

def get_db():
    # Pega o caminho do .env
    db_path = os.getenv("DATABASE_URL")
    
    # Caminho de Backup Local (Requisito: C:\Banco de Dados SystemDataCagece)
    backup_dir = r"C:\Banco de Dados SystemDataCagece"
    backup_path = os.path.join(backup_dir, "database.db")

    # Limpeza básica de aspas
    if db_path:
        db_path = db_path.strip().replace('"', '').replace("'", "")

    # --- LÓGICA DE TENTATIVA DE CONEXÃO ---
    conn = None
    
    # TENTATIVA 1: Tentar o caminho do .env (W:\...)
    if db_path:
        try:
            # Tenta garantir que a pasta da rede existe (se o drive estiver mapeado)
            folder_rede = os.path.dirname(db_path)
            if folder_rede and not os.path.exists(folder_rede):
                os.makedirs(folder_rede, exist_ok=True)
            
            conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False, isolation_level=None)
            print(f"[*] Conectado via REDE: {db_path}")
        except Exception as e:
            print(f"[!] Erro na rede: {e}. Tentando fallback local no C:...")

    # TENTATIVA 2: Se a rede falhou ou não existe DATABASE_URL, usa o C:
    if conn is None:
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)
            
            conn = sqlite3.connect(backup_path, timeout=60, check_same_thread=False, isolation_level=None)
            print(f"[*] Conectado LOCALMENTE: {backup_path}")
        except Exception as e:
            print(f"[ERRO CRÍTICO] Falha total: {e}")
            return None

    # Configurações de performance mantidas do seu padrão original
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except:
        pass 
        
    return conn

# A função init_db() permanece EXATAMENTE igual à sua, 
# pois ela já usa o get_db() que agora está inteligente.
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