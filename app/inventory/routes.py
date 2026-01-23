from flask import render_template
from app.inventory import inventory_bp

@inventory_bp.route('/')
def index():
    return render_template('index.html')