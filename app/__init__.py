import os
import logging
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, redirect, url_for, session, flash
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable
from logging.handlers import RotatingFileHandler


db = SQLAlchemy()


def configure_production_logging(app):
    if os.getenv("FLASK_ENV") != "production":
        return

    log_folder = os.path.abspath(os.path.join(app.root_path, "..", "log"))
    os.makedirs(log_folder, exist_ok=True)

    log_file = os.path.join(log_folder, "production.log")
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == log_file
        for handler in app.logger.handlers
    )

    if has_file_handler:
        return

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s "
            "[in %(pathname)s:%(lineno)d]"
        )
    )

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)


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
        ensure_toolbox_schema_columns(inspector)
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

    ensure_toolbox_schema_columns(inspect(db.engine))
    print(f"Toolbox schema tables created: {len(missing_tables)}.")


def ensure_toolbox_schema_columns(inspector):
    table_names = inspector.get_table_names(schema="toolbox")
    table_columns_sql = {}

    if "inventory_operation_reception_differences" in table_names:
        table_columns_sql["inventory_operation_reception_differences"] = {
            "resolution_status": "ALTER TABLE toolbox.inventory_operation_reception_differences ADD COLUMN resolution_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'",
            "resolution_note": "ALTER TABLE toolbox.inventory_operation_reception_differences ADD COLUMN resolution_note TEXT",
            "resolved_user_code": "ALTER TABLE toolbox.inventory_operation_reception_differences ADD COLUMN resolved_user_code VARCHAR(50)",
            "resolved_at": "ALTER TABLE toolbox.inventory_operation_reception_differences ADD COLUMN resolved_at TIMESTAMP",
        }

    if "shopping_products_params" in table_names:
        table_columns_sql["shopping_products_params"] = {
            "update_at": "ALTER TABLE toolbox.shopping_products_params ADD COLUMN update_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        }

    if "provider_registrations" in table_names:
        table_columns_sql["provider_registrations"] = {
            "username": "ALTER TABLE toolbox.provider_registrations ADD COLUMN username VARCHAR(100) NOT NULL DEFAULT ''",
            "password": "ALTER TABLE toolbox.provider_registrations ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT ''",
            "registered_at": "ALTER TABLE toolbox.provider_registrations ADD COLUMN registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "status": "ALTER TABLE toolbox.provider_registrations ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'PENDING'",
        }

    if "purchase_review_new_product_items" in table_names:
        table_columns_sql["purchase_review_new_product_items"] = {
            "proposed_main_code": "ALTER TABLE toolbox.purchase_review_new_product_items ADD COLUMN proposed_main_code VARCHAR",
            "proposed_image": "ALTER TABLE toolbox.purchase_review_new_product_items ADD COLUMN proposed_image BYTEA",
            "proposed_image_type": "ALTER TABLE toolbox.purchase_review_new_product_items ADD COLUMN proposed_image_type VARCHAR",
        }

    added_columns = []
    with db.engine.begin() as connection:
        connection.execute(text("SET statement_timeout = 15000"))
        for table_name, column_sql in table_columns_sql.items():
            columns = {
                column["name"]
                for column in inspector.get_columns(table_name, schema="toolbox")
            }
            missing_columns = [name for name in column_sql if name not in columns]
            for column_name in missing_columns:
                connection.execute(text(column_sql[column_name]))
            if missing_columns:
                added_columns.append(f"{table_name} ({', '.join(missing_columns)})")

        connection.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'toolbox' AND table_name = 'provider_registrations'
                ) THEN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint c
                        JOIN pg_class t ON c.conrelid = t.oid
                        JOIN pg_namespace n ON n.oid = t.relnamespace
                        WHERE n.nspname = 'toolbox' AND t.relname = 'provider_registrations' AND c.conname = 'ck_provider_registrations_status'
                    ) THEN
                        ALTER TABLE toolbox.provider_registrations
                        DROP CONSTRAINT ck_provider_registrations_status;
                    END IF;

                    ALTER TABLE toolbox.provider_registrations
                    ADD CONSTRAINT ck_provider_registrations_status
                    CHECK (status IN ('PENDING', 'APPROVED', 'BLOCKED'));
                END IF;
            END $$;
        """))

        connection.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'toolbox'
                      AND table_name = 'purchase_review_lists'
                      AND column_name = 'created_by'
                      AND is_nullable = 'NO'
                ) THEN
                    ALTER TABLE toolbox.purchase_review_lists
                    ALTER COLUMN created_by DROP NOT NULL;
                END IF;
            END $$;
        """))

    if added_columns:
        print("Toolbox schema columns added: " f"{'; '.join(added_columns)}.")


def create_app():
    load_dotenv()

    app = Flask(__name__)
    configure_production_logging(app)

    # 2. Configuración de parámetros recomendados
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured in the environment.")

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'una_clave_secreta_muy_segura_dev_123')
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

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
        public_endpoints = {
            "auth.login",
            "static",
            "shopping.provider_login",
            "shopping.provider_register",
            "shopping.provider_register_status",
            "shopping.provider_username_availability",
            "shopping.provider_logout",
        }

        if request.endpoint is None:
            return

        if request.endpoint in public_endpoints or request.blueprint == "auth":
            return

        provider_routes = {
            "shopping.provider_panel",
            "shopping.provider_catalog_modal",
            "shopping.provider_new_product_modal",
            "shopping.provider_offer_lists_modal",
            "shopping.provider_offer_lists_content",
            "shopping.provider_offer_list_pdf_report",
            "shopping.provider_offer_list_excel_report",
            "shopping.provider_offer_items_add",
            "shopping.provider_offer_items_add_new_product",
            "shopping.provider_offer_temp_image",
            "shopping.provider_offer_items_submit_review",
            "shopping.provider_offer_items_unit",
            "shopping.provider_offer_items_remove",
            "shopping.provider_offer_items_clear",
            "shopping.provider_offer_drafts_hold",
            "shopping.provider_offer_drafts_modal",
            "shopping.provider_offer_draft_load",
            "shopping.provider_offer_draft_delete",
            "shopping.provider_offer_drafts_notes",
            "shopping.provider_purchases",
            "shopping.provider_inventory",
        }

        if request.endpoint in provider_routes:
            if session.get("provider_logged_in") and session.get("provider_username"):
                return
            flash("Debes iniciar sesión como proveedor para acceder a esta sección.", "warning")
            return redirect(url_for("shopping.provider_login"))

        if request.endpoint == "shopping.provider_new_product_image":
            if session.get("provider_logged_in") and session.get("provider_username"):
                return
            if current_user.is_authenticated:
                return
            return redirect(url_for("auth.login", next=request.url))

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
    from app.shopping import shopping_bp
    from app.reports import reports_bp
    from app.document_manager import document_manager_bp
    from app.products_label import label_bp
    from app.sales import sales_bp

    app.register_blueprint(main_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(common_bp, url_prefix='/common')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(shopping_bp, url_prefix='/shopping')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(document_manager_bp, url_prefix='/documents')
    app.register_blueprint(label_bp, url_prefix='/etiquetas')
    app.register_blueprint(sales_bp)

    return app



