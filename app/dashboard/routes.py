from flask import render_template
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.dashboard.service import get_dashboard_data


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template(
        'dashboard/dashboard.html',
        user=current_user,
        dashboard=get_dashboard_data(),
    )