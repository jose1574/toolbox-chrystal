from flask import render_template
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp 

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/dashboard.html', user=current_user)