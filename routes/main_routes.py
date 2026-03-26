from flask import render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
from io import BytesIO
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
import unicodedata

# 1. PROTEÇÃO DE ROTA
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

    # 2. CONFIGURAÇÃO (Criação de Tabelas com colunas padrão Cagece)
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
                
                default_cols = [
                    "contrato TEXT", "ano TEXT", "nome_da_obra TEXT", 
                    "data_base TEXT", "referencia TEXT"
                ]
                
                cols_raw = request.form.getlist('col_name')
                types_raw = request.form.getlist('col_type')
                extra_cols = []
                for c, t in zip(cols_raw, types_raw):
                    if c.strip():
                        c_clean = re.sub(r'[^a-z0-9_]', '', unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('ascii').replace(" ", "_").lower())
                        extra_cols.append(f"{c_clean} {t}")
                
                all_cols_query = default_cols + extra_cols
                query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(all_cols_query)}, criado_por TEXT, data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                db.execute(query)
                db.commit()
                flash(f"Tabela '{raw_name.upper()}' criada com sucesso!")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f"Erro ao criar tabela: {e}")

        opcoes = db.execute("SELECT * FROM catalogo_tabelas ORDER BY nome_exibicao").fetchall()
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
                except: flash("Nome já existe.")
        return redirect(url_for('config'))

    # 3. CRUD (Listagem com FILTRO GLOBAL DINÂMICO)
    @app.route('/crud/<table_name>')
    @login_required
    def crud(table_name):
        db = get_db()
        search = request.args.get('search', "").strip()
    
        # Pega as informações de todas as colunas da tabela
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    
        # Colunas para o formulário (excluindo metadados)
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
    
        # Todas as colunas que serão exibidas na tabela
        all_cols = [c['name'] for c in info if c['name'] != 'id']

        if search:
            # CONSTRUÇÃO DO FILTRO GLOBAL:
            # Cria um "WHERE coluna LIKE ?" para CADA coluna existente na tabela
            where_clauses = [f"{c['name']} LIKE ?" for c in info if c['name'] != 'id']
            where_sql = " OR ".join(where_clauses)
        
            query = f"SELECT * FROM {table_name} WHERE {where_sql} ORDER BY id DESC"
        
            # Repete o termo de busca para cada interrogação (?) no SQL
            params = [f'%{search}%'] * len(where_clauses)
            data = db.execute(query, params).fetchall()
        else:
            data = db.execute(f"SELECT * FROM {table_name} ORDER BY id DESC").fetchall()

        return render_template('crud.html', 
                           table_name=table_name, 
                           cols=cols, 
                           all_cols=all_cols, 
                           data=data, 
                           now_date=datetime.now().strftime('%d/%m/%Y'))

    # 4. INSERIR DADOS
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

    # 5. EDITAR REGISTRO
    @app.route('/edit/<table_name>/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit(table_name, id):
        db = get_db()
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info if c['name'] not in ['id', 'criado_por', 'data_criacao']]
        
        if request.method == 'POST':
            values = [request.form.get(c) for c in cols]
            set_clause = ", ".join([f"{c} = ?" for c in cols])
            values.append(id)
            db.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = ?", values)
            db.commit()
            flash("Registro atualizado!")
            return redirect(url_for('crud', table_name=table_name))

        row = db.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,)).fetchone()
        return render_template('edit.html', table_name=table_name, row=row, cols=cols)

    # 6. EXCLUIR REGISTRO (Necessário para o 'X' do seu CRUD)
    @app.route('/delete_row/<table_name>/<int:id>')
    @login_required
    def delete_row(table_name, id):
        db = get_db()
        db.execute(f"DELETE FROM {table_name} WHERE id = ?", (id,))
        db.commit()
        return redirect(url_for('crud', table_name=table_name))

    # 7. EXCLUIR TABELA INTEIRA
    @app.route('/drop_table/<name>')
    @login_required
    def drop_table(name):
        if session.get('nivel') == 'admin' and name not in ['usuarios_sistema', 'catalogo_tabelas']:
            db = get_db()
            db.execute(f"DROP TABLE IF EXISTS {name}")
            db.commit()
        return redirect(url_for('index'))

 
    # 8. RELATÓRIOS E EXPORTAÇÃO (FILTRO GLOBAL INTELIGENTE)
    @app.route('/relatorios')
    @login_required
    def relatorios():
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('usuarios_sistema', 'catalogo_tabelas')").fetchall()
    
        table_name = request.args.get('table')
        search = request.args.get('search', "").strip()
    
        report_data, cols, chart_data = [], [], {'labels': [], 'valores_lista': []}
    
        if table_name:
            # Pega info das colunas
            info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
            cols = [c['name'] for c in info]
        
            if search:
                # Busca em TODAS as colunas (Resolve o problema do 10/2020)
                where_clauses = [f"{col} LIKE ?" for col in cols]
                where_sql = " OR ".join(where_clauses)
                query = f"SELECT * FROM {table_name} WHERE {where_sql} ORDER BY id DESC"
                params = [f'%{search}%'] * len(cols)
                report_data = db.execute(query, params).fetchall()
            else:
                report_data = db.execute(f"SELECT * FROM {table_name} ORDER BY id DESC").fetchall()

            # Alimenta o gráfico (limitado aos 5 primeiros para não poluir)
            for row in report_data[:5]:
                # Usa a 4ª coluna (Nome da Obra) para o label, se existir
                label = str(row[cols[3]]) if len(cols) > 3 else f"ID {row['id']}"
                chart_data['labels'].append(label)
                chart_data['valores_lista'].append(1) 
            
        return render_template('relatorios.html', tables=tables, data=report_data, cols=cols, selected_table=table_name, chart_data=chart_data)

    @app.route('/exportar/<table_name>')
    @login_required
    def exportar_excel(table_name):
        db = get_db()
        search = request.args.get('search', "").strip()
    
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        cols = [c['name'] for c in info]
    
        # Se houver busca na URL, exporta apenas os itens filtrados
        if search:
            where_clauses = [f"{col} LIKE ?" for col in cols]
            where_sql = " OR ".join(where_clauses)
            query = f"SELECT * FROM {table_name} WHERE {where_sql} ORDER BY id DESC"
            params = [f'%{search}%'] * len(cols)
            df = pd.read_sql_query(query, db, params=params)
            filename = f"Relatorio_FILTRADO_{table_name}.xlsx"
        else:
            # Caso contrário, exporta a planilha inteira
            query = f"SELECT * FROM {table_name} ORDER BY id DESC"
            df = pd.read_sql_query(query, db)
            filename = f"Relatorio_GERAL_{table_name}.xlsx"

        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        out.seek(0)
    
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=filename)

    # 9. USUÁRIOS E LOGIN
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
                session.update({'user': res['username'], 'nivel': res['nivel'], 'matricula': res['matricula']})
                return redirect(url_for('index'))
            flash("Credenciais inválidas.")
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            db = get_db()
            hashed_pw = generate_password_hash(request.form['password'])
            db.execute("INSERT INTO usuarios_sistema (username, password, matricula, nivel) VALUES (?, ?, ?, 'user')",
                       (request.form['username'], hashed_pw, request.form['matricula']))
            db.commit()
            return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))