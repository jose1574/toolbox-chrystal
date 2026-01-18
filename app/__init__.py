import os
from flask_sqlalchemy import SQLAlchemy
from flask import Flask


db = SQLAlchemy()
def create_app():
    flask_app = Flask(__name__)

    # 2. Configuración de parámetros recomendados
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')


    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
    flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 10,          # Máximo de conexiones simultáneas abiertas
        "pool_recycle": 3600,     # Reinicia conexiones cada hora para evitar cortes
        "pool_pre_ping": True     # Verifica si la conexión está viva antes de usarla
    }

    db.init_app(flask_app)

    with flask_app.app_context():
        # Importar modelos para que SQLAlchemy los reconozca al crear tablas
        try:
            from app import models
            db.create_all()
            print("Tablas satélites creadas en el esquema toolbox.")
        except Exception as e:
            print(f"Error creando tablas: {e}")


    from app.main import main_bp
    from app.auth import auth_bp

    
    flask_app.register_blueprint(main_bp, url_prefix='/')
    flask_app.register_blueprint(auth_bp, url_prefix='/auth')

    return flask_app



