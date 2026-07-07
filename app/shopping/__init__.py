from flask import Blueprint


shopping_bp = Blueprint('shopping', __name__, template_folder='templates', url_prefix='/shopping')


from app.shopping import routes