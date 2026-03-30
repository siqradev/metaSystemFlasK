import os
import sys
import dotenv
from flask import Flask

# --- BLOCO PARA CORREÇÃO DO EXECUTÁVEL (Mantido seu padrão) ---
if getattr(sys, 'frozen', False):
    # Se rodando como .exe, busca as pastas dentro do pacote temporário
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    
    # AJUSTE 1: Garante que o .env seja lido da pasta onde o .exe está, não da temporária
    base_path = os.path.dirname(sys.executable)
else:
    # Se rodando local no VS Code
    app = Flask(__name__)
    base_path = os.path.dirname(os.path.abspath(__file__))

# Carrega o .env apontando para o caminho físico real
dotenv.load_dotenv(os.path.join(base_path, '.env'))
# --------------------------------------------------------------

from models.database import init_db, get_db 
from routers.main_routes import register_routes 

app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Registro de todas as rotas (Mantido)
register_routes(app, get_db)

if __name__ == '__main__':
    # AJUSTE 2: Mover o init_db para dentro do main.
    # Isso evita que o Windows "mate" o processo se a rede demorar a responder no boot.
    try:
        init_db()
    except Exception as e:
        print(f"Erro ao iniciar banco na rede: {e}")
        # Se der erro, o app ainda tenta subir para você ver o log no terminal
    
    # Porta 8080 conforme seu padrão
    app.run(host='0.0.0.0', port=8080, debug=False)