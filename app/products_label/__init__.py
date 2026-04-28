from flask import Blueprint

label_bp = Blueprint('products_label', __name__, template_folder='templates')

from app.products_label import routes
