from datetime import datetime

from app import db
from app.models import ProductPricingUpdateSetting, User


def get_authorized_price_update_users():
    config = ProductPricingUpdateSetting.get_or_create_default()
    return config.authorized_users_list


def get_authorized_price_update_user_details():
    user_codes = get_authorized_price_update_users()
    if not user_codes:
        return []

    users_by_code = {
        user.code.upper(): user.description or user.code
        for user in User.query.filter(User.code.in_(user_codes)).all()
    }
    return [
        {"code": code, "name": users_by_code.get(code, code)}
        for code in user_codes
    ]


def save_authorized_price_update_users(user_codes, updated_by):
    config = ProductPricingUpdateSetting.get_or_create_default()
    config.authorized_users_list = user_codes
    config.updated_by = updated_by
    config.updated_at = datetime.utcnow()
    db.session.add(config)
    db.session.commit()
    return config.authorized_users_list


def list_users():
    return [
        {
            "code": user.code,
            "description": user.description or "",
            "email": user.email or "",
        }
        for user in User.query.order_by(User.code).all()
    ]
