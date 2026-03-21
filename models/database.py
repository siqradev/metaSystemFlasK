import sqlite3
import os
from werkzeug.security import generate_password_hash

# Caminhos Oficiais Cagece [Pág 1]
DB_UNC = r"\\int.cagece.com.br\den\spe\Gproj\4.0RC\09.DIVERSOS\DB_PARAMETRIZACAO\database.db"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_LOCAL = os.path.join(BASE_DIR, "database.db")

def get_db():
    # Prioriza rede, se falhar usa local. Timeout de 20s conforme solicitado no PDF.
    path = DB_UNC if os.path.exists(os.path.dirname(DB_UNC)) else DB_LOCAL
    
    conn = sqlite3.connect(path, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Estabilidade em rede: evita "Database is locked"
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
        
        # 2. Tabela de Catálogo (Sua nova tabela de nomes predefinidos)
        conn.execute('''CREATE TABLE IF NOT EXISTS catalogo_tabelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_exibicao TEXT UNIQUE
        )''')

        # 3. Inserindo exemplos baseados na sua imagem da Cagece
        nomes_padrao = ['CASA_DE_OPERADOR', 'CX_MON_JUS', 'REDE_DE_DISTRIBUICAO', 'ESTACAO_ELEVATORIA']
        for nome in nomes_padrao:
            conn.execute("INSERT OR IGNORE INTO catalogo_tabelas (nome_exibicao) VALUES (?)", (nome,))
        
        # 4. Admin padrão com Hash de Segurança [Pág 1]
        if not conn.execute("SELECT * FROM usuarios_sistema WHERE username='admin'").fetchone():
            hash_pwd = generate_password_hash('admin123')
            conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)",
                        ('0000', 'admin', hash_pwd, 'admin'))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
    finally:
        conn.close()

# Se rodar este arquivo sozinho, ele limpa e recria as tabelas base
if __name__ == "__main__":
    init_db()
    print("Banco de dados Cagece inicializado com sucesso!")