from flask import render_template, request
from app.main import main_bp
from app.models import User
from sqlalchemy import or_


@main_bp.route('/search/users/partial')
def search_users_partial():
    query = request.args.get('q', '').strip()
    
    if not query:
        return """
        <tr>
            <td colspan="4" class="px-6 py-10 text-center">
                <div class="flex flex-col items-center justify-center opacity-40">
                    <svg class="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <p class="text-sm font-medium text-gray-900 dark:text-gray-100">Comienza a escribir para ver resultados</p>
                </div>
            </td>
        </tr>
        """
        
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