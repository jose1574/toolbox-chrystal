from flask import Blueprint

common_bp = Blueprint('common', __name__)

from app.common import routes