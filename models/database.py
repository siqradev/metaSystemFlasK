import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash
import dotenv

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))
DB_PATH = os.getenv("DATABASE_URL")

def get_db():
    if not DB_PATH:
        print("\n[ERRO] DATABASE_URL nao definida no .env!")
        sys.exit(1)

    try:
        # Tentamos conectar. Se o W: nao estiver mapeado ou o arquivo sumir,
        # o SQLite vai dar erro e o programa fecha, sem criar nada local.
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception as e:
        print(f"\n[CAGECE] Erro ao acessar o banco: {e}")
        print(f"Caminho tentado: {DB_PATH}")
        sys.exit(1)

def init_db():
    try:
        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            username TEXT UNIQUE,
            password TEXT,
            nivel TEXT DEFAULT 'usuario')''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_exibicao TEXT UNIQUE)''')

        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro na inicializacao: {e}")

if __name__ == "__main__":
    init_db()
    print("Conexao com servidor Cagece verificada!")