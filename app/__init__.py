import os
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user


db = SQLAlchemy()
def create_app():
    app = Flask(__name__)

    # 2. Configuración de parámetros recomendados
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'una_clave_secreta_muy_segura_dev_123')

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor inicia sesión para acceder a esta página."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        # Importación tardía para evitar ciclos, si models importa db de aquí
        from app.models import User
        return User.query.get(user_id)

    @app.before_request
    def enforce_authentication():
        """Redirige a login cuando un usuario anónimo accede a rutas protegidas."""
        # Permitir rutas públicas (login, assets) sin autenticación previa
        public_endpoints = {"auth.login", "static"}

        if request.endpoint is None:
            return

        if request.endpoint in public_endpoints or request.blueprint == "auth":
            return

        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))


    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 10,          # Máximo de conexiones simultáneas abiertas
        "pool_recycle": 3600,     # Reinicia conexiones cada hora para evitar cortes
        "pool_pre_ping": True     # Verifica si la conexión está viva antes de usarla
    }

    db.init_app(app)

    with app.app_context():
        # Importar modelos para que SQLAlchemy los reconozca al crear tablas
        try:
            from app import models
            db.create_all()
            print("Tablas satélites creadas en el esquema toolbox.")
        except Exception as e:
            print(f"Error creando tablas: {e}")


    from app.main import main_bp
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.common import common_bp
    from app.admin import admin_bp
    from app.inventory import inventory_bp
    from app.reports import reports_bp
    from app.document_manager import document_manager_bp

    app.register_blueprint(main_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(common_bp, url_prefix='/common')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(document_manager_bp, url_prefix='/documents')

    return app



