from flask import Flask
import dotenv
dotenv.load_dotenv()  # Carrega variáveis de ambiente do arquivo .env
import os
import sys
from models.database import init_db, get_db 
from routers.main_routes import register_routes 

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')  # Use uma chave secreta do .env ou um valor padrão

# Inicialização
try:
    init_db()
except Exception as e:
    print(f"Erro ao iniciar banco: {e}")

# Registro de todas as rotas
register_routes(app, get_db)

if __name__ == '__main__':
    # host 0.0.0.0 permite que outros vejam na rede se o firewall permitir
    app.run(host='0.0.0.0', port=8080, debug=False)