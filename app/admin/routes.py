from flask import render_template, request, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.admin import admin_bp
from app.models import TxMenu, TxProfile, User, UserProfile
from app import db


@admin_bp.route("/menus")
@login_required
def manage_menus():
    search_menu = request.form.get("menu_code")
    user = current_user
    menus = TxMenu.query.all()
    return render_template("admin/manage_menus.html", user=user, menus=menus)


@admin_bp.route("/menus/create", methods=["POST"])
@login_required
def create_menu():
    code = request.form.get("menu_code").upper()
    description = request.form.get("menu_description").strip()

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


@admin_bp.route("/menus/delete", methods=["POST"])
@login_required
def delete_menu():
    code = request.form.get("menu_code").upper()

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


@admin_bp.route("/profile")
@login_required
def user_profile():
    search_profile = request.args.get("profile_code")
    profile = (
        TxProfile.query.filter_by(code=search_profile).first()
        if search_profile
        else None
    )
    menus = TxMenu.query.all()
    return render_template("admin/profiles.html", profile=profile, menus=menus)


@admin_bp.route("/profile/search")
@login_required
def user_profile_search():
    code = request.args.get("profile_code", "").upper()
    profile = TxProfile.query.get(code)
    error_msg = None
    menus = TxMenu.query.all()

    if code and not profile:
        error_msg = f'El perfil con código <span class="font-bold">{code}</span> no existe. Puede crearlo ingresando una descripción.'

    return render_template(
        "admin/profiles.html",
        profile=profile,
        error_msg=error_msg,
        search_code=code,
        menus=menus,
    )


@admin_bp.route("/profile/search/profile")
@login_required
def profile_user_modal():
    profiles = TxProfile.query.all()
    return render_template("common/modal_profile_search.html", profiles=profiles)


@admin_bp.route("/profile/create", methods=["POST"])
@login_required
def create_user_profile():
    code = request.form.get("profile_code", "").upper().strip()
    description = request.form.get("profile_description", "").strip()
    active_menus = request.form.getlist("menus")
    print("Menus activos seleccionados: ", active_menus)

    if not code or not description:
        return render_template(
            "admin/profiles.html",
            error_msg="Error: Código y descripción son obligatorios.",
            menus=TxMenu.query.all(),
        )

    try:
        profile = TxProfile.query.get(code)

        # Preparamos la lista de configuración de menús
        menus_config_list = []
        for menu_code in active_menus:
            menus_config_list.append({"menu_code": menu_code, "is_active": True})

        if profile:
            profile.description = description
            profile.menus_list = menus_config_list  # Usamos el setter de models.py
            msg = f'Perfil "{code}" actualizado exitosamente.'
        else:
            print("Configuración de menús para el perfil: ", menus_config_list)
            # Usamos el setter menus_list en lugar de pasar el dict directo a menus_config
            new_profile = TxProfile(code=code, description=description)
            new_profile.menus_list = menus_config_list
            db.session.add(new_profile)
            msg = f'Perfil "{code}" creado exitosamente.'

        db.session.commit()
        return render_template(
            "admin/profiles.html", success_msg=msg, menus=TxMenu.query.all()
        )
    except Exception as e:
        db.session.rollback()
        return render_template(
            "admin/profiles.html",
            error_msg=f"Error al guardar perfil: {str(e)}",
            menus=TxMenu.query.all(),
        )


@admin_bp.route("/users")
@login_required
def manage_users():
    return render_template("admin/users.html", user=None)


@admin_bp.route("/search/users")
@login_required
def search_users():
    users = User.query.all()
    return render_template("common/modal_user_search.html", users=users)


@admin_bp.route("/search/user")
@login_required
def search_user():
    search_code = request.args.get("searchUser", "").strip()
    user = None
    if search_code:
        result = ( db.session.query(User, UserProfile)
            .outerjoin(UserProfile, User.code==UserProfile.user_code)
            .filter(User.code == search_code.upper())
            .first()
        )

        if result:
            print("\n" + "="*50)
            print("DEBUG: RESULTADO DE LA CONSULTA (ROW)")
            # result es un objeto Row (tupla). Accedemos a sus elementos:
            user_obj, up_obj = result
            
            print(f" - Usuario (Entity): {user_obj}")
            if user_obj:
                print(f"   * Columnas User: { {c.name: getattr(user_obj, c.name) for c in user_obj.__table__.columns} }")
            
            print(f" - Perfil Toolbox (Entity): {up_obj}")
            if up_obj:
                print(f"   * Columnas UserProfile: { {c.name: getattr(up_obj, c.name) for c in up_obj.__table__.columns} }")
            print("="*50 + "\n")

            # Inyectamos el código del perfil de toolbox en el objeto user
            user_obj.toolbox_profile_code = up_obj.profile_code if up_obj else None
            user = user_obj # Ahora 'user' es el objeto que el HTML entiende
            
        if not user:
            return render_template(
                "admin/users.html",
                error_msg="Usuario no encontrado.",
                search_code=search_code,
            )

        print(f"Búsqueda usuario: '{search_code}' -> Resultado: {user}")
    return render_template("admin/users.html", user=user, search_code=search_code)


@admin_bp.route("/assign/profile/user", methods=["POST"])
@login_required
def assign_profile_user():
    search_code = request.form.get("searchUser", "").strip()
    profile_code = request.form.get("profile_code", "").strip().upper()
    user = None

    if not search_code:
        return render_template(
            "admin/users.html", error_msg="Debe seleccionar un usuario."
        )

    user = User.query.filter_by(code=search_code.upper()).first()
    if not user:
        return render_template(
            "admin/users.html",
            search_code=search_code,
            error_msg=f'Usuario con código "{search_code}" no encontrado.',
        )

    if not profile_code:
        return render_template(
            "admin/users.html",
            user=user,
            search_code=search_code,
            error_msg="Debe seleccionar un perfil para asignar.",
        )

    profile = TxProfile.query.filter_by(code=profile_code).first()
    if not profile:
        return render_template(
            "admin/users.html",
            user=user,
            search_code=search_code,
            error_msg=f'Perfil con código "{profile_code}" no encontrado.',
        )

    try:
        # Buscamos si el usuario ya tiene algún perfil asignado en esta tabla
        existing_assignment = UserProfile.query.filter_by(user_code=user.code).first()

        if existing_assignment:
            if existing_assignment.profile_code == profile.code:
                # Si ya tiene el mismo perfil, no hacemos nada extra
                msg = f'El usuario "{user.code}" ya tiene asignado el perfil "{profile.code}".'
            else:
                # Si tiene uno distinto, lo actualizamos (borramos y creamos por ser PK compuesta)
                old_profile = existing_assignment.profile_code
                db.session.delete(existing_assignment)
                db.session.flush() # Sincronizamos para evitar conflictos de llave
                
                new_user_profile = UserProfile(user_code=user.code, profile_code=profile.code)
                db.session.add(new_user_profile)
                msg = f'Perfil del usuario "{user.code}" actualizado: "{old_profile}" -> "{profile.code}".'
        else:
            # Si no tiene ninguna asignación, la creamos desde cero
            new_user_profile = UserProfile(user_code=user.code, profile_code=profile.code)
            db.session.add(new_user_profile)
            msg = f'Perfil "{profile.code}" asignado exitosamente al usuario "{user.code}".'

        db.session.commit()
        return render_template(
            "admin/users.html",
            user=user,
            search_code=search_code,
            success_msg=msg,
        )
    except Exception as e:
        db.session.rollback()
        return render_template(
            "admin/users.html",
            user=user,
            search_code=search_code,
            error_msg=f"Error inesperado al asignar perfil: {str(e)}",
        )
