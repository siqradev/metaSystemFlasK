from flask import Flask
import dotenv
import os
import sys

# --- BLOCO PARA CORREÇÃO DO EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    # Se rodando como .exe, busca as pastas dentro do pacote temporário
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # Se rodando normal no Linux/VS Code, busca as pastas locais
    app = Flask(__name__)
# ------------------------------------------

dotenv.load_dotenv() 
import os # Import repetido, pode manter ou remover o de cima
from models.database import init_db, get_db 
from routers.main_routes import register_routes 

app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Inicialização
try:
    init_db()
except Exception as e:
    print(f"Erro ao iniciar banco: {e}")

# Registro de todas as rotas
register_routes(app, get_db)

if __name__ == '__main__':
    # No executável, o waitress ou o app.run precisam de uma porta fixa
    app.run(host='0.0.0.0', port=8080, debug=False)