from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import pandas as pd
from io import BytesIO
import os
import sys
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'cagece_meta_key_final'

# --- CONFIGURAÇÃO DE CAMINHOS DINÂMICOS (PARA REDE/EXECUTÁVEL) ---
if getattr(sys, 'frozen', False):
    # Se rodando como .exe, baseia-se no local do executável
    basedir = os.path.dirname(sys.executable)
else:
    # Se rodando como .py, baseia-se no local do script
    basedir = os.path.abspath(os.path.dirname(__file__))

# O banco e o log ficarão na mesma pasta do executável no servidor
DB_NAME = os.path.join(basedir, 'database.db')
LOG_FILE = os.path.join(basedir, 'erro_sistema.log')

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def log_error(mensagem):
    """Registra erros silenciosamente no arquivo para diagnóstico posterior."""
    logging.error(mensagem)

def get_db():
    # Aumentamos o timeout para 20s para mitigar lentidão de rede e travas do SQLite
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT UNIQUE,
                username TEXT UNIQUE,
                password TEXT,
                nivel TEXT DEFAULT 'usuario')''')
            if not conn.execute("SELECT * FROM usuarios_sistema WHERE username = 'admin'").fetchone():
                conn.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?, ?, ?, ?)", 
                             ('0000', 'admin', 'admin', 'admin'))
                conn.commit()
    except Exception as e:
        log_error(f"Falha na inicialização do Banco: {e}")

@app.before_request
def auth_check():
    public = ['login', 'register', 'static']
    if 'user' not in session and request.endpoint not in public:
        return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/')
def index():
    try:
        conn = get_db()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        total_users = conn.execute("SELECT COUNT(*) as total FROM usuarios_sistema").fetchone()['total']
        return render_template('index.html', tables=tables, total_tables=len(tables), total_users=total_users)
    except Exception as e:
        log_error(f"Erro ao carregar Dashboard: {e}")
        return "Erro ao acessar o banco de dados na rede. Verifique sua conexão com o servidor."

# --- GESTÃO DE EQUIPE ---
@app.route('/usuarios')
def usuarios():
    if session.get('nivel') != 'admin':
        flash("Acesso restrito ao administrador.")
        return redirect(url_for('index'))
    conn = get_db()
    lista = conn.execute("SELECT id, matricula, username, nivel FROM usuarios_sistema").fetchall()
    return render_template('usuarios.html', usuarios=lista)

# --- EXPORTAÇÃO EXCEL ---
@app.route('/exportar/<table_name>')
def exportar_excel(table_name):
    try:
        conn = get_db()
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"relatorio_{table_name}.xlsx")
    except Exception as e:
        log_error(f"Erro ao exportar Excel ({table_name}): {e}")
        flash("Erro ao gerar o arquivo Excel.")
        return redirect(url_for('crud', table_name=table_name))

# --- CRUD DINÂMICO ---
@app.route('/crud/<table_name>')
def crud(table_name):
    conn = get_db()
    info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
    all_cols = [c['name'] for c in info]
    data = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    return render_template('crud.html', table_name=table_name, cols=cols, all_cols=all_cols, data=data)

@app.route('/insert/<table_name>', methods=['POST'])
def insert(table_name):
    try:
        conn = get_db()
        info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        values = [request.form.get(c) for c in cols] + [f"{session['user']} ({session['matricula']})"]
        placeholders = ", ".join(["?" for _ in values])
        conn.execute(f"INSERT INTO {table_name} ({', '.join(cols)}, criado_por) VALUES ({placeholders})", values)
        conn.commit()
    except Exception as e:
        log_error(f"Erro ao inserir dados em {table_name}: {e}")
        flash("Erro ao salvar registro. Verifique se o banco está ocupado.")
    return redirect(url_for('crud', table_name=table_name))

@app.route('/edit/<table_name>/<int:id>', methods=['GET', 'POST'])
def edit(table_name, id):
    conn = get_db()
    info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
    if request.method == 'POST':
        try:
            updates = ", ".join([f"{c} = ?" for c in cols])
            conn.execute(f"UPDATE {table_name} SET {updates} WHERE id = ?", [request.form.get(c) for c in cols] + [id])
            conn.commit()
            return redirect(url_for('crud', table_name=table_name))
        except Exception as e:
            log_error(f"Erro ao editar ID {id} em {table_name}: {e}")
            flash("Erro ao atualizar.")
    
    row = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)).fetchone()
    return render_template('edit.html', table_name=table_name, row=row, cols=cols)

@app.route('/delete_row/<table_name>/<int:id>')
def delete_row(table_name, id):
    try:
        conn = get_db()
        conn.execute(f"DELETE FROM {table_name} WHERE id=?", (id,))
        conn.commit()
    except Exception as e:
        log_error(f"Erro ao deletar linha em {table_name}: {e}")
    return redirect(url_for('crud', table_name=table_name))

# --- CONFIGURAÇÃO ---
@app.route('/config', methods=['GET', 'POST'])
def config():
    if session.get('nivel') != 'admin': return redirect(url_for('index'))
    conn = get_db()
    
    if request.method == 'POST':
        try:
            name = request.form['table_name'].replace(" ", "_").lower()
            cols, types = request.form.getlist('col_name'), request.form.getlist('col_type')
            
            reserved = ['id', 'criado_por', 'data_criacao']
            cleaned_cols = []
            for c in cols:
                c_clean = c.strip().replace(" ", "_").lower()
                if c_clean in reserved or c_clean in cleaned_cols:
                    flash(f"Erro: O nome '{c}' é reservado ou está duplicado.")
                    return redirect(url_for('config'))
                cleaned_cols.append(c_clean)

            col_def = ", ".join([f"{n} {t}" for n, t in zip(cleaned_cols, types)])
            
            query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_def}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            conn.execute(query)
            conn.commit()
            flash(f"Tabela '{name}' criada!")
            return redirect(url_for('index'))
            
        except Exception as e:
            log_error(f"Erro ao criar tabela: {e}")
            flash(f"Erro técnico: {e}")
            
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
    return render_template('config.html', tables=tables)

@app.route('/drop_table/<name>')
def drop_table(name):
    if session.get('nivel') == 'admin':
        try:
            conn = get_db()
            conn.execute(f"DROP TABLE IF EXISTS {name}")
            conn.commit()
        except Exception as e:
            log_error(f"Erro ao dropar tabela {name}: {e}")
    return redirect(url_for('index'))

# --- LOGIN / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form['username'], request.form['password']
        try:
            with get_db() as db:
                res = db.execute("SELECT * FROM usuarios_sistema WHERE username=? AND password=?", (user, pwd)).fetchone()
                if res:
                    session['user'], session['nivel'], session['matricula'] = res['username'], res['nivel'], res['matricula']
                    return redirect(url_for('index'))
            flash("Credenciais inválidas.")
        except Exception as e:
            log_error(f"Erro no login: {e}")
            flash("Erro de conexão com o banco de dados.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- RELATÓRIOS E BI ---
@app.route('/relatorios')
def relatorios():
    conn = get_db()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
    selected = request.args.get('table')
    search = request.args.get('search', '')
    data, cols = [], []
    chart_data = {"labels": [], "valores_lista": []}
    if selected:
        info = conn.execute(f"PRAGMA table_info({selected})").fetchall()
        cols = [c['name'] for c in info]
        query = f"SELECT * FROM {selected} WHERE 1=1"
        params = []
        if search and len(cols) > 1:
            query += f" AND {cols[1]} LIKE ?"
            params.append(f"%{search}%")
        data = conn.execute(query, params).fetchall()
        for r in data:
            label = str(r[cols[1]]) if len(cols) > 1 else "Item"
            try: val = float(r[cols[2]]) if len(cols) > 2 else 1
            except: val = 1
            chart_data["labels"].append(label)
            chart_data["valores_lista"].append(val)
    return render_template('relatorios.html', tables=tables, data=data, cols=cols, selected_table=selected, chart_data=chart_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        matricula = request.form['matricula']
        username = request.form['username']
        password = request.form['password']
        try:
            with get_db() as db:
                db.execute("INSERT INTO usuarios_sistema (matricula, username, password) VALUES (?, ?, ?)", 
                           (matricula, username, password))
                db.commit()
            flash("Cadastro realizado! Faça login.")
            return redirect(url_for('login'))
        except Exception as e:
            log_error(f"Erro no registro de usuário: {e}")
            flash("Matrícula ou Usuário já existem.")
    return render_template('register.html')

if __name__ == '__main__':
    init_db()
    # Host 0.0.0.0 permite acesso pelo seu IP na rede local
    app.run(host='0.0.0.0', port=8080)