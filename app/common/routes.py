from flask import render_template
from app.common import common_bp
from app.models import User

@common_bp.route('/search-users-modal')
def search_users_modal():
    users = User.query.all()
    return render_template('common/modal_user_search.html', users=users)