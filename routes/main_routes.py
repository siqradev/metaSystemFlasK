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
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('usuarios_sistema', 'catalogo_tabelas')").fetchall()
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
                if not raw_name:
                    flash("Selecione um nome válido no catálogo.")
                    return redirect(url_for('config'))
                
                name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii').replace(" ", "_").lower()
                name = re.sub(r'[^a-z0-9_]', '', name)
                
                # Colunas Padrão da Imagem
                default_cols = [
                    "contrato TEXT", "ano TEXT", "nome_da_obra TEXT", 
                    "licitado TEXT", "data_base TEXT", "referencia TEXT"
                ]
                
                cols_raw = request.form.getlist('col_name')
                types_raw = request.form.getlist('col_type')
                extra_cols = []
                for c, t in zip(cols_raw, types_raw):
                    if c.strip():
                        c_clean = re.sub(r'[^a-z0-9_]', '', unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('ascii').replace(" ", "_").lower())
                        extra_cols.append(f"{c_clean} {t}")
                
                all_cols = default_cols + extra_cols
                query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(all_cols)}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                db.execute(query)
                db.commit()
                flash(f"Tabela '{raw_name.upper()}' criada com sucesso!")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f"Erro ao criar tabela: {e}")

        opcoes = db.execute("SELECT * FROM catalogo_tabelas ORDER BY nome_exibicao").fetchall()
        # Filtramos as tabelas para o seu bloco de "Tabelas Ativas" no config.html
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('usuarios_sistema', 'catalogo_tabelas')").fetchall()
        return render_template('config.html', opcoes_catalogo=opcoes, tables=tables)

    @app.route('/add_catalogo', methods=['POST'])
    @login_required
    def add_catalogo():
        if session.get('nivel') == 'admin':
            novo_nome = request.form.get('novo_nome', '').strip().upper()
            if novo_nome:
                db = get_db()
                try:
                    db.execute("INSERT INTO catalogo_tabelas (nome_exibicao) VALUES (?)", (novo_nome,))
                    db.commit()
                    flash(f"'{novo_nome}' adicionado ao catálogo!")
                except: flash("Nome já existe.")
        return redirect(url_for('config'))

    @app.route('/crud/<table_name>')
    @login_required
    def crud(table_name):
        db = get_db()
        search = request.args.get('search', '')
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        if search and len(cols) > 0:
            data = db.execute(f"SELECT * FROM {table_name} WHERE {cols[0]} LIKE ? OR {cols[2]} LIKE ? ORDER BY id DESC", (f'%{search}%', f'%{search}%')).fetchall()
        else:
            data = db.execute(f"SELECT * FROM {table_name} ORDER BY id DESC").fetchall()
        return render_template('crud.html', table_name=table_name, cols=cols, data=data, now_date=datetime.now().strftime('%d/%m/%Y'))

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

    @app.route('/drop_table/<name>')
    @login_required
    def drop_table(name):
        if session.get('nivel') == 'admin':
            db = get_db()
            if name not in ['usuarios_sistema', 'catalogo_tabelas']:
                db.execute(f"DROP TABLE IF EXISTS {name}")
                db.commit()
                flash(f"Tabela {name} excluída.")
        return redirect(url_for('index'))

    # ROTA DE RELATÓRIOS (ESSENCIAL PARA NÃO DAR BUILDERROR)
    @app.route('/relatorios')
    @login_required
    def relatorios():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('usuarios_sistema', 'catalogo_tabelas')").fetchall()
        
        table_name = request.args.get('table')
        report_data, cols = [], []
        
        # ESSENCIAL: Inicializa o chart_data para evitar o erro de 'Undefined'
        chart_data = {'labels': [], 'valores_lista': []}

        if table_name:
            try:
                info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
                cols = [c['name'] for c in info]
                report_data = db.execute(f"SELECT * FROM {table_name} ORDER BY id DESC").fetchall()
                
                # Opcional: Lógica simples para preencher o gráfico (ex: contagem por item)
                if report_data:
                    # Exemplo: pega os 5 primeiros registros para o gráfico
                    for row in report_data[:5]:
                        # Usa a 3ª coluna (Nome da Obra) como label, se existir
                        label = str(row[cols[2]]) if len(cols) > 2 else f"ID {row['id']}"
                        chart_data['labels'].append(label)
                        chart_data['valores_lista'].append(1) # Valor fixo para teste
            except Exception as e:
                flash(f"Erro ao carregar dados: {e}")

        # Agora passamos o chart_data explicitamente
        return render_template('relatorios.html', 
                               tables=tables, 
                               data=report_data, 
                               cols=cols, 
                               selected_table=table_name,
                               chart_data=chart_data)

    @app.route('/usuarios')
    @login_required
    def usuarios():
        if session.get('nivel') != 'admin': return redirect(url_for('index'))
        db = get_db()
        lista = db.execute("SELECT id, matricula, username, nivel FROM usuarios_sistema").fetchall()
        return render_template('usuarios.html', usuarios=lista)

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

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            user, pwd = request.form['username'], request.form['password']
            db = get_db()
            res = db.execute("SELECT * FROM usuarios_sistema WHERE username=?", (user,)).fetchone()
            if res and check_password_hash(res['password'], pwd):
                session.update({'user': res['username'], 'nivel': res['nivel'], 'matricula': res['matricula']})
                return redirect(url_for('index'))
            flash("Credenciais inválidas.")
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))