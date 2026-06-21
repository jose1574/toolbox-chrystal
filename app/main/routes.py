from flask import render_template
from app.main import main_bp
from app.dashboard.service import get_dashboard_data



@main_bp.route('/')
def index():
    return render_template('dashboard/dashboard.html', dashboard=get_dashboard_data())