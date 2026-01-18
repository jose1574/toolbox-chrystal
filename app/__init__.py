import os
from flask_sqlalchemy import SQLAlchemy
from flask import Flask


db = SQLAlchemy()
def create_app():
    app = Flask(__name__)







    # 2. Configuración de parámetros recomendados
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')


    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 10,          # Máximo de conexiones simultáneas abiertas
        "pool_recycle": 3600,     # Reinicia conexiones cada hora para evitar cortes
        "pool_pre_ping": True     # Verifica si la conexión está viva antes de usarla
    }

    db.init_app(app)


    from app.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/')

    return app



