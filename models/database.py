import sqlite3
import os
import sys 
from werkzeug.security import generate_password_hash
import dotenv

# 1. Localiza a pasta do executável (Windows) ou do script (Linux)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Carrega o .env obrigatoriamente da pasta onde o programa está
dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))

# 3. Pega o caminho do banco do ambiente
DB_PATH = os.getenv("DATABASE_URL")

def get_db():
    if not DB_PATH:
        print("\n[ERRO] DATABASE_URL não encontrada no .env!")
        sys.exit(1)

    try:
        # O segredo: 'mode=rw' proíbe a criação de novos arquivos .db
        # Se o arquivo não existir no servidor, ele dará ERRO em vez de criar um local
        db_uri = f"file:{DB_PATH}?mode=rw"
        conn = sqlite3.connect(db_uri, uri=True, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        print("\n" + "!"*60)
        print("ERRO CRÍTICO: BANCO DE DADOS NÃO ENCONTRADO NA REDE!")
        print(f"Caminho tentado: {DB_PATH}")
        print(f"Mensagem: {e}")
        print("!"*60 + "\n")
        # Força o erro para o Flask não rodar com banco vazio
        raise RuntimeError(f"Acesso negado ou arquivo inexistente: {DB_PATH}")

def init_db():
    """Verifica tabelas. Se o banco não existir, o get_db() já trava o processo aqui."""
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

        # Admin padrão
        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Falha na inicialização: {e}")

if __name__ == "__main__":
    init_db()