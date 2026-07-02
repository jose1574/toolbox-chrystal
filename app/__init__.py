import os
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable


db = SQLAlchemy()


def create_toolbox_schema_tables():
    toolbox_tables = [
        table for table in db.metadata.sorted_tables if table.schema == "toolbox"
    ]

    if not toolbox_tables:
        print("No tables registered for the toolbox schema.")
        return

    inspector = inspect(db.engine)
    if not inspector.has_schema("toolbox"):
        db.session.execute(text("CREATE SCHEMA toolbox"))
        db.session.commit()

    existing_table_names = set(inspector.get_table_names(schema="toolbox"))
    missing_tables = [
        table for table in toolbox_tables if table.name not in existing_table_names
    ]

    if not missing_tables:
        print(f"Toolbox schema tables verified: {len(toolbox_tables)}.")
        return

    with db.engine.begin() as connection:
        connection.execute(text("SET statement_timeout = 15000"))
        for table in missing_tables:
            toolbox_foreign_keys = [
                constraint
                for constraint in table.foreign_key_constraints
                if constraint.referred_table.schema == "toolbox"
            ]
            connection.execute(
                CreateTable(
                    table,
                    include_foreign_key_constraints=toolbox_foreign_keys,
                )
            )
            for index in table.indexes:
                connection.execute(CreateIndex(index))

    print(f"Toolbox schema tables created: {len(missing_tables)}.")


def create_app():
    load_dotenv()

    app = Flask(__name__)

    # 2. Configuración de parámetros recomendados
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured in the environment.")

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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
        # Import models to register metadata before creating local application tables.
        from app import models
        create_toolbox_schema_tables()


    from app.main import main_bp
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.common import common_bp
    from app.admin import admin_bp
    from app.inventory import inventory_bp
    from app.reports import reports_bp
    from app.document_manager import document_manager_bp
    from app.products_label import label_bp

    app.register_blueprint(main_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(common_bp, url_prefix='/common')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(document_manager_bp, url_prefix='/documents')
    app.register_blueprint(label_bp, url_prefix='/etiquetas')

    return app



