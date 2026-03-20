import sqlite3
import os
from werkzeug.security import generate_password_hash

# Caminhos Oficiais Cagece [Pág 1]
DB_UNC = r"\\int.cagece.com.br\den\spe\Gproj\4.0RC\09.DIVERSOS\DB_PARAMETRIZACAO\database.db"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_LOCAL = os.path.join(BASE_DIR, "database.db")

def get_db():
    # Prioriza rede, se falhar usa local. Timeout de 20s conforme solicitado.
    path = DB_UNC if os.path.exists(os.path.dirname(DB_UNC)) else DB_LOCAL
    conn = sqlite3.connect(path, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL") # Estabilidade em rede
    return conn

def init_db():
    with get_db() as conn:
        # Tabela de Usuários
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            username TEXT UNIQUE,
            password TEXT,
            nivel TEXT DEFAULT 'usuario')''')
        
        # Admin padrão com Hash de Segurança [Pág 1]
        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
            conn.commit()