from flask import Blueprint

settings_app_bp = Blueprint(
    "settings_app",
    __name__,
    template_folder="templates",
    url_prefix="/settings-app",
)

from app.settings_app import routes
