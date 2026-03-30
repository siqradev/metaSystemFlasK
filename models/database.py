import sqlite3
import os
import sys 
from werkzeug.security import generate_password_hash
import dotenv
dotenv.load_dotenv() 

# --- AJUSTE PARA EXECUTÁVEL (Caminho Dinâmico) ---
if getattr(sys, 'frozen', False):
    # Se for o .EXE rodando, a pasta base é onde o .exe está
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Se for no Linux/VS Code, mantém o comportamento original
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_UNC = os.getenv("DATABASE_URL")
DB_LOCAL = os.path.join(BASE_DIR, "database.db")
# ------------------------------------------------

def get_db():
    # Tenta o caminho do W: primeiro (se estiver no .env)
    if DB_UNC:
        try:
            # Conecta direto. Se a rede estiver offline ou o caminho errado, ele pula para o except
            conn = sqlite3.connect(DB_UNC, timeout=20, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL") 
            return conn
        except Exception as e:
            print(f"Aviso: Servidor W: inacessível. Erro: {e}")

    # Se não houver .env ou o W: falhar, usa o banco local na pasta do .exe
    conn = sqlite3.connect(DB_LOCAL, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL") 
    return conn

def init_db():
    conn = get_db()
    try:
        # 1. Tabela de Usuários
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            username TEXT UNIQUE,
            password TEXT,
            nivel TEXT DEFAULT 'usuario')''')
        
        # 2. Tabela de Catálogo
        conn.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_exibicao TEXT UNIQUE
        )''')

        # 3. Inserindo exemplos
        nomes_padrao = ['CASA_DE_OPERADOR', 'CX_MON_JUS', 'REDE_DE_DISTRIBUICAO', 'ESTACAO_ELEVATORIA']
        for nome in nomes_padrao:
            conn.execute("INSERT OR IGNORE INTO catalogo_tabelas (nome_exibicao) VALUES (?)", (nome,))
        
        # 4. Admin padrão
        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Banco de dados Cagece inicializado com sucesso!")