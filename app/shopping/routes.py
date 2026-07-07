from flask import render_template
from flask_login import login_required

from app.shopping import shopping_bp
from app.shopping.services import shopping_service


@shopping_bp.route('/')
@login_required
def index():
    page_data = shopping_service.get_shopping_overview()
    return render_template('shopping/index.html', page_data=page_data)

# @shopping_bp.route('/shopping_orders')
# @login_required 
# def shopping_orders():
#     return render_template('shopping/manual_shopping_orders.html')