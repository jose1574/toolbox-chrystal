from flask import render_template, request, flash
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.models import TxMenu, TxProfile, TxMenuActive, TxProfile
from app import db






@admin_bp.route('/users')
@login_required
def manage_users():
    user = current_user
    return render_template('admin/manage_users.html', user=user)


@admin_bp.route('/menus')
@login_required
def manage_menus():
    search_menu = request.form.get('menu_code')
    user = current_user
    menus = TxMenu.query.all()
    return render_template('admin/manage_menus.html', user=user, menus=menus)


@admin_bp.route('/menus/create', methods=['POST'])
@login_required
def create_menu():
    code = request.form.get('menu_code').upper()
    description = request.form.get('menu_description').strip()

    if not code or not description:
        return "<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>Código y descripción son obligatorios.</div>"
    
    try:

        menu = TxMenu.query.get(code)

        if menu:
            
            menu.description = description
            message = "Menú actualizado exitosamente."
            color = "yellow"

        else:

            new_menu = TxMenu(code=code, description=description)
            db.session.add(new_menu)
            message = "Menú creado exitosamente."
            color = "green"
        db.session.commit()
        return f"<div class='p-4 mb-4 text-sm text-{color}-800 rounded-lg bg-{color}-50' role='alert'>{message}</div>"
    except Exception as e:
        db.session.rollback()
        return f"<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>Error al crear/actualizar menú: {e}</div>"


@admin_bp.route('/menus/delete', methods=['POST'])
@login_required
def delete_menu():
    code = request.form.get('menu_code').upper()

    try:
        menu = TxMenu.query.get(code)
        if menu:
            message = "Menú eliminado exitosamente."
            color = "red"
            db.session.delete(menu)
            db.session.commit()
            return f"<div class='p-4 mb-4 text-sm text-{color}-800 rounded-lg bg-{color}-50' role='alert'>{message}</div>"
        else:
            return f"<div class='p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50' role='alert'>Menú no encontrado.</div>"
    except Exception as e:
        db.session.rollback()
        return f"<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>Error al eliminar menú: {e}</div>"






@admin_bp.route('/profile')
@login_required
def user_profile():
    search_profile = request.args.get('profile_code')
    profile = TxProfile.query.filter_by(code=search_profile).first() if search_profile else None
    return render_template('admin/user_profile.html', profile=profile)


@admin_bp.route('/profile/search')
@login_required
def user_profile_search():
    code = request.args.get('profile_code', '').upper()
    profile = TxProfile.query.get(code)
    error_msg = None
    
    if code and not profile:
        error_msg = f'El perfil con código <span class="font-bold">{code}</span> no existe. Puede crearlo ingresando una descripción.'
    
    return render_template('admin/user_profile.html', 
                          profile=profile, 
                          error_msg=error_msg, 
                          search_code=code)


@admin_bp.route('/profile/modal/profile_user')
@login_required
def profile_user_modal():
    profiles = TxProfile.query.all()
    return render_template('common/modal_profile_search.html', profiles=profiles)

@admin_bp.route('/profile/create', methods=['POST'])
@login_required
def create_user_profile():
    code = request.form.get('profile_code', '').upper().strip()
    description = request.form.get('profile_description', '').strip()

    if not code or not description:
        return render_template('admin/user_profile.html', error_msg='Error: Código y descripción son obligatorios.')
    
    try:
        profile = TxProfile.query.get(code)
        if profile:
            profile.description = description
            msg = f'Perfil "{code}" actualizado exitosamente.'
        else:
            new_profile = TxProfile(code=code, description=description)
            db.session.add(new_profile)
            msg = f'Perfil "{code}" creado exitosamente.'
        
        db.session.commit()
        return render_template('admin/user_profile.html', success_msg=msg)
    except Exception as e:
        db.session.rollback()
        return render_template('admin/user_profile.html', error_msg=f'Error al guardar perfil: {str(e)}')
