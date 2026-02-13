from flask import Blueprint

document_manager_bp = Blueprint('document_manager', __name__, template_folder='templates')

from app.document_manager import routes