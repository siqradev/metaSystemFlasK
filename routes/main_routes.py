from flask import render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
from io import BytesIO
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
import unicodedata

# Decorator de Proteção de Rota (Fora da função register_routes)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app, get_db):
    """
    IMPORTANTE: Todas as rotas abaixo DEVEM estar recuadas (indentadas) 
    para estarem dentro desta função.
    """

    @app.route('/')
    @login_required
    def index():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        total_users = db.execute("SELECT COUNT(*) as total FROM usuarios_sistema").fetchone()['total']
        return render_template('index.html', tables=tables, total_tables=len(tables), total_users=total_users)

    @app.route('/drop_table/<name>')
    @login_required
    def drop_table(name):
        if session.get('nivel') == 'admin':
            db = get_db()
            if name != 'usuarios_sistema':
                db.execute(f"DROP TABLE IF EXISTS {name}")
                db.commit()
                flash(f"Tabela {name} excluída!")
        return redirect(url_for('index'))

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
                col_def = [f"{re.sub(r'[^a-z0-9_]', '', unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('ascii').replace(' ', '_').lower())} {t}" for c, t in zip(cols_raw, types_raw) if c.strip()]
                query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(col_def)}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                db.execute(query); db.commit()
                flash(f"Tabela '{name}' criada!")
                return redirect(url_for('index'))
            except Exception as e: flash(f"Erro: {e}")
        return render_template('config.html')

    @app.route('/crud/<table_name>')
    @login_required
    def crud(table_name):
        db = get_db()
        search = request.args.get('search', '')
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        all_cols = [c['name'] for c in info]
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
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        if request.method == 'POST':
            set_query = ", ".join([f"{c} = ?" for c in cols])
            values = [request.form.get(c) for c in cols] + [id]
            db.execute(f"UPDATE {table_name} SET {set_query} WHERE id = ?", values)
            db.commit()
            return redirect(url_for('crud', table_name=table_name))
        row = db.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)).fetchone()
        return render_template('edit.html', table_name=table_name, row=row, cols=cols)

    @app.route('/delete_row/<table_name>/<int:id>')
    @login_required
    def delete_row(table_name, id):
        db = get_db()
        db.execute(f"DELETE FROM {table_name} WHERE id = ?", (id,))
        db.commit()
        return redirect(url_for('crud', table_name=table_name))

    @app.route('/relatorios')
    @login_required
    def relatorios():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'usuarios_sistema'").fetchall()
        table_name = request.args.get('table')
        search = request.args.get('search', '')
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        
        report_data, cols = [], []
        chart_data = {'labels': [], 'valores_lista': []}

        if table_name:
            info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
            cols = [c['name'] for c in info]
            query = f"SELECT * FROM {table_name} WHERE 1=1"
            params = []
            if search and len(cols) > 1:
                query += f" AND {cols[1]} LIKE ?"; params.append(f'%{search}%')
            if data_inicio:
                query += " AND data_criacao >= ?"; params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                query += " AND data_criacao <= ?"; params.append(f"{data_fim} 23:59:59")
            
            query += " ORDER BY id DESC"
            report_data = db.execute(query, params).fetchall()

            if len(report_data) > 0 and len(cols) >= 3:
                for row in report_data[:10]:
                    chart_data['labels'].append(str(row[cols[1]]))
                    try:
                        valor = float(str(row[cols[2]]).replace(',', '.'))
                        chart_data['valores_lista'].append(valor)
                    except: chart_data['valores_lista'].append(1)

        return render_template('relatorios.html', tables=tables, data=report_data, cols=cols, selected_table=table_name, chart_data=chart_data)

    @app.route('/exportar/<table_name>')
    @login_required
    def exportar_excel(table_name):
        db = get_db()
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", db)
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        out.seek(0)
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"Relatorio_{table_name}.xlsx")

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

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            m, u, p = request.form['matricula'], request.form['username'], request.form['password']
            db = get_db()
            db.execute("INSERT INTO usuarios_sistema (matricula, username, password, nivel) VALUES (?,?,?,?)", (m, u, generate_password_hash(p), 'user'))
            db.commit()
            return redirect(url_for('login'))
        return render_template('register.html')