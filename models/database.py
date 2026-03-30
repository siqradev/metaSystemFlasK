import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash
import dotenv

# --- AJUSTE PARA O EXECUTÁVEL ACHAR O .ENV ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Carrega o .env explicitamente da pasta do programa
dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))

# Pega o caminho oficial da rede do seu .env
DB_UNC = os.getenv("DATABASE_URL")

def get_db():
    # Se o .env não for lido, DB_UNC será None. Avisamos aqui:
    if not DB_UNC:
        print("\n[ERRO] DATABASE_URL não encontrada no arquivo .env!")
        print(f"Procurei o arquivo .env em: {BASE_DIR}")
        sys.exit(1)

    # Validação original sua: Verifica se a pasta existe
    if not os.path.exists(os.path.dirname(DB_UNC)):
        print(f"\n[CAGECE] Servidor inacessível: {os.path.dirname(DB_UNC)}")
        sys.exit(1)

    # Conecta diretamente no caminho da rede
    conn = sqlite3.connect(DB_UNC, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Estabilidade em rede: evita "Database is locked"
    conn.execute("PRAGMA journal_mode=WAL")
    
    conn.db_path = DB_UNC
    return conn

def init_db():
    try:
        conn = get_db()
        
        # Suas tabelas originais
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            username TEXT UNIQUE,
            password TEXT,
            nivel TEXT DEFAULT 'usuario')''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_exibicao TEXT UNIQUE)''')

        nomes_padrao = ['CASA_DE_OPERADOR', 'CX_MON_JUS', 'REDE_DE_DISTRIBUICAO', 'ESTACAO_ELEVATORIA']
        for nome in nomes_padrao:
            conn.execute("INSERT OR IGNORE INTO catalogo_tabelas (nome_exibicao) VALUES (?)", (nome,))
        
        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
        
        conn.commit()
        print(f"Banco conectado com sucesso em: {DB_UNC}")
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")

if __name__ == "__main__":
    init_db()
    print("Verificação de Banco de Dados concluída.")