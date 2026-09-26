from flask import Blueprint

printer_config_bp = Blueprint(
    "printer_config", __name__, template_folder="templates", url_prefix="/printer-config"
)

from app.printer_config import routes
