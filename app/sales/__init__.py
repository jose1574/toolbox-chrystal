from flask import Blueprint

sales_bp = Blueprint("sales", __name__, template_folder="templates", url_prefix="/sales")

from app.sales import routes
