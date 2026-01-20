from flask import render_template, request
from app.main import main_bp
from app.models import User
from sqlalchemy import or_


@main_bp.route('/search/users/partial')
def search_users_partial():
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return ""
        
    users = User.query.filter(
        or_(
            User.code.ilike(f'%{query}%'),
            User.description.ilike(f'%{query}%'),
            User.email.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    return render_template('common/partials/user_rows.html', users=users)


@main_bp.route('/')
def index():
    return render_template('/dashboard/dashboard.html')