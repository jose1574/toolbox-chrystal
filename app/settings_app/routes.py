from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.settings_app import settings_app_bp
from app.settings_app.services import settings_app_service


@settings_app_bp.route("/price-update-access")
@login_required
def price_update_access():
    return render_template(
        "settings_app/price_update_access.html",
        authorized_users=settings_app_service.get_authorized_price_update_users(),
        authorized_user_details=settings_app_service.get_authorized_price_update_user_details(),
    )


@settings_app_bp.route("/save-price-update-access", methods=["POST"])
@login_required
def save_price_update_access():
    settings_app_service.save_authorized_price_update_users(
        request.form.get("authorized_users", ""), current_user.code
    )
    flash("Los usuarios autorizados para actualizar precios se guardaron correctamente.", "success")
    return redirect(url_for("settings_app.price_update_access"))


@settings_app_bp.route("/price-update-users")
@login_required
def price_update_users():
    return jsonify(settings_app_service.list_users())
