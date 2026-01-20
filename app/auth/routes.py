from flask import render_template, request, redirect, url_for, Response
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models import User


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(code=username).first()
        
        # Comparación de contraseña (en texto plano según la base de datos actual)
        # TODO: Implementar hashing de contraseñas con werkzeug.security o bcrypt
        if user and user.user_password == password:
            print(f"DEBUG LOGIN - Exitoso: {username}")
            login_user(user)
            
            # Respuesta para HTMX: Header de redirección
            response = Response()
            response.headers['HX-Redirect'] = url_for('dashboard.dashboard')
            return response
        
        print(f"DEBUG LOGIN - Fallido para: {username}")
        return "<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>Usuario o contraseña incorrectos</div>"
        
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

