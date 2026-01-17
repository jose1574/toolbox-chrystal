from flask import Flask

def create_app():
    app = Flask(__name__)

    from app.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/')



    return app



