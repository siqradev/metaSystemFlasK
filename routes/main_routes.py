from flask import render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
from io import BytesIO
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
import unicodedata

# Decorator de Proteção de Rota
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app, get_db):

    @app.route('/')
    @login_required
    def index():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        total_users = db.execute("SELECT COUNT(*) as total FROM usuarios_sistema").fetchone()['total']
        return render_template('index.html', tables=tables, total_tables=len(tables), total_users=total_users)

    @app.route('/config', methods=['GET', 'POST'])
    @login_required
    def config():
        if session.get('nivel') != 'admin':
            flash("Acesso restrito.")
            return redirect(url_for('index'))
        db = get_db()
        if request.method == 'POST':
            try:
                raw_name = request.form.get('table_name', '').strip()
                name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii').replace(" ", "_").lower()
                name = re.sub(r'[^a-z0-9_]', '', name)
                
                cols_raw = request.form.getlist('col_name')
                types_raw = request.form.getlist('col_type')
                col_def = []
                for c, t in zip(cols_raw, types_raw):
                    if c.strip():
                        c_clean = unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('ascii').replace(" ", "_").lower()
                        c_clean = re.sub(r'[^a-z0-9_]', '', c_clean)
                        col_def.append(f"{c_clean} {t}")
                
                query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(col_def)}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                db.execute(query)
                db.commit()
                flash(f"Tabela '{name}' criada!")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f"Erro: {e}")
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        return render_template('config.html', tables=tables)

    @app.route('/crud/<table_name>')
    @login_required
    def crud(table_name):
        db = get_db()
        search = request.args.get('search', '')
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        
        # all_cols: Para o cabeçalho e corpo da tabela
        all_cols = [c['name'] for c in info]
        # cols: Apenas campos para o formulário de inserção
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        
        if search and cols:
            data = db.execute(f"SELECT * FROM {table_name} WHERE {cols[0]} LIKE ? ORDER BY id DESC", (f'%{search}%',)).fetchall()
        else:
            data = db.execute(f"SELECT * FROM {table_name} ORDER BY id DESC").fetchall()
            
        return render_template('crud.html', table_name=table_name, cols=cols, all_cols=all_cols, data=data, now_date=datetime.now().strftime('%d/%m/%Y'))

    @app.route('/insert/<table_name>', methods=['POST'])
    @login_required
    def insert(table_name):
        db = get_db()
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        
        values = [request.form.get(c) for c in cols]
        values.append(f"{session.get('user')} ({session.get('matricula', 'N/A')})")
        
        placeholders = ", ".join(["?" for _ in values])
        db.execute(f"INSERT INTO {table_name} ({', '.join(cols)}, criado_por) VALUES ({placeholders})", values)
        db.commit()
        return redirect(url_for('crud', table_name=table_name))

    @app.route('/edit/<table_name>/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit(table_name, id):
        db = get_db()
        if request.method == 'POST':
            info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
            cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
            set_query = ", ".join([f"{c} = ?" for c in cols])
            values = [request.form.get(c) for c in cols] + [id]
            db.execute(f"UPDATE {table_name} SET {set_query} WHERE id = ?", values)
            db.commit()
            return redirect(url_for('crud', table_name=table_name))
        
        row = db.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)).fetchone()
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        return render_template('edit.html', table_name=table_name, row=row, cols=cols)

    @app.route('/delete_row/<table_name>/<int:id>')
    @login_required
    def delete_row(table_name, id):
        db = get_db()
        db.execute(f"DELETE FROM {table_name} WHERE id = ?", (id,))
        db.commit()
        return redirect(url_for('crud', table_name=table_name))

    @app.route('/drop_table/<name>')
    @login_required
    def drop_table(name):
        if session.get('nivel') == 'admin':
            db = get_db()
            db.execute(f"DROP TABLE IF EXISTS {name}")
            db.commit()
        return redirect(url_for('index'))

    @app.route('/relatorios')
    @login_required
    def relatorios():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        table_selected = request.args.get('table')
        report_data, cols = [], []
        if table_selected:
            info = db.execute(f"PRAGMA table_info({table_selected})").fetchall()
            cols = [c['name'] for c in info]
            report_data = db.execute(f"SELECT * FROM {table_selected} ORDER BY id DESC").fetchall()
        return render_template('relatorios.html', tables=tables, data=report_data, cols=cols, selected=table_selected)

    @app.route('/usuarios')
    @login_required
    def usuarios():
        if session.get('nivel') != 'admin': return redirect(url_for('index'))
        db = get_db()
        lista = db.execute("SELECT id, matricula, username, nivel FROM usuarios_sistema").fetchall()
        return render_template('usuarios.html', usuarios=lista)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            user, pwd = request.form['username'], request.form['password']
            db = get_db()
            res = db.execute("SELECT * FROM usuarios_sistema WHERE username=?", (user,)).fetchone()
            if res and check_password_hash(res['password'], pwd):
                session['user'], session['nivel'], session['matricula'] = res['username'], res['nivel'], res['matricula']
                return redirect(url_for('index'))
            flash("Credenciais inválidas.")
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))