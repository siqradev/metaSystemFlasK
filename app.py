from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'cagece_meta_key_final'
DB_NAME = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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

@app.before_request
def auth_check():
    public = ['login', 'register', 'static']
    if 'user' not in session and request.endpoint not in public:
        return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/')
def index():
    conn = get_db()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
    total_users = conn.execute("SELECT COUNT(*) as total FROM usuarios_sistema").fetchone()['total']
    return render_template('index.html', tables=tables, total_tables=len(tables), total_users=total_users)

# --- GESTÃO DE EQUIPE (CORRIGE O BUILDERROR) ---
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
    conn = get_db()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"relatorio_{table_name}.xlsx")

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
    conn = get_db()
    info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
    values = [request.form.get(c) for c in cols] + [f"{session['user']} ({session['matricula']})"]
    placeholders = ", ".join(["?" for _ in values])
    conn.execute(f"INSERT INTO {table_name} ({', '.join(cols)}, criado_por) VALUES ({placeholders})", values)
    conn.commit()
    return redirect(url_for('crud', table_name=table_name))

@app.route('/edit/<table_name>/<int:id>', methods=['GET', 'POST'])
def edit(table_name, id):
    conn = get_db()
    info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
    if request.method == 'POST':
        updates = ", ".join([f"{c} = ?" for c in cols])
        conn.execute(f"UPDATE {table_name} SET {updates} WHERE id = ?", [request.form.get(c) for c in cols] + [id])
        conn.commit()
        return redirect(url_for('crud', table_name=table_name))
    row = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)).fetchone()
    return render_template('edit.html', table_name=table_name, row=row, cols=cols)

@app.route('/delete_row/<table_name>/<int:id>')
def delete_row(table_name, id):
    conn = get_db()
    conn.execute(f"DELETE FROM {table_name} WHERE id=?", (id,))
    conn.commit()
    return redirect(url_for('crud', table_name=table_name))

# --- CONFIGURAÇÃO ---
@app.route('/config', methods=['GET', 'POST'])
def config():
    if session.get('nivel') != 'admin': return redirect(url_for('index'))
    conn = get_db()
    if request.method == 'POST':
        name = request.form['table_name'].replace(" ", "_")
        cols, types = request.form.getlist('col_name'), request.form.getlist('col_type')
        col_def = ", ".join([f"{n} {t}" for n, t in zip(cols, types)])
        conn.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_def}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        return redirect(url_for('index'))
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
    return render_template('config.html', tables=tables)

@app.route('/drop_table/<name>')
def drop_table(name):
    if session.get('nivel') == 'admin':
        conn = get_db()
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.commit()
    return redirect(url_for('index'))

# --- LOGIN / LOGOUT ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form['username'], request.form['password']
        with get_db() as db:
            res = db.execute("SELECT * FROM usuarios_sistema WHERE username=? AND password=?", (user, pwd)).fetchone()
            if res:
                session['user'], session['nivel'], session['matricula'] = res['username'], res['nivel'], res['matricula']
                return redirect(url_for('index'))
        flash("Credenciais inválidas.")
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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)