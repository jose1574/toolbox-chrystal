from flask import render_template
from app.main import main_bp
from app.models import User

@main_bp.route('/')
def index():
    users = User.query.all()

    return render_template('/dashboard/dashboard.html', users=users)