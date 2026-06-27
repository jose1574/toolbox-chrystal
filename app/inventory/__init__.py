from flask import Blueprint

# Initialize inventory blueprint with explicit template_folder and url_prefix
inventory_bp = Blueprint('inventory', __name__, template_folder='templates', url_prefix='/inventory')

from app.inventory import routes
