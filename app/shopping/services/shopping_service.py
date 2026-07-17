from datetime import datetime

from sqlalchemy import func, or_

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsCode,
    ProductsStock,
    ProductsUnit,
    Provider,
    ShoppingProductsParam,
    ShoppingProductsParamsHistory,
    Unit,
)


def normalize_code(code: str) -> str:
        return (code or '').strip().upper()


def _resolve_main_code(code: str) -> str:
        normalized = normalize_code(code)
        mapping = ProductsCode.query.filter(
                func.upper(func.trim(ProductsCode.other_code)) == normalized
        ).first()
        return normalize_code(mapping.main_code) if mapping else normalized

    


def get_product_order_details(code):
    if not code:
        return None

    main_code = _resolve_main_code(code)
    product = (
        Product.query
        .with_entities(
            Product.code,
            Product.description,
            Product.department,
            Department.description.label('department_description'),
            Product.referenc,
            Product.mark,
            Mark.description.label('mark_description'),
            Product.minimal_stock,
            Product.maximum_stock,
        )
        .outerjoin(Department, Department.code == Product.department)
        .outerjoin(Mark, Mark.code == Product.mark)
        .filter(func.upper(func.trim(Product.code)) == main_code)
        .first()
    )

    if not product:
        return None

    return {
        'code': product.code,
        'description': product.description,
        'department': product.department,
        'department_description': product.department_description,
        'referenc': product.referenc,
        'mark': product.mark,
        'mark_description': product.mark_description,
        'minimal_stock': product.minimal_stock,
        'maximum_stock': product.maximum_stock,
    }


def build_products_params_context(code=None):
    selected_code = normalize_code(code)
    context = {
        'selected_code': selected_code,
        'product': None,
        'shopping_params': None,
        'inventory_params': None,
        'history_entries': [],
    }

    if not selected_code:
        return context

    main_code = _resolve_main_code(selected_code)
    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    context['selected_code'] = main_code

    if not product:
        return context

    shopping_params = ShoppingProductsParam.query.filter(
        func.upper(func.trim(ShoppingProductsParam.code)) == main_code
    ).first()
    stock_total = (
        db.session.query(func.coalesce(func.sum(ProductsStock.stock), 0))
        .filter(ProductsStock.product_code == main_code)
        .scalar()
    )

    context.update(
        {
            'product': product,
            'shopping_params': shopping_params,
            'inventory_params': {
                'store_name': 'Todos los depósitos',
                'stock': stock_total or 0,
                'minimum_stock': product.minimal_stock or 0,
                'maximum_stock': product.maximum_stock or 0,
            },
            'history_entries': (
                ShoppingProductsParamsHistory.query.filter_by(
                    main_correlative=shopping_params.correlative
                )
                .order_by(ShoppingProductsParamsHistory.register_date.desc())
                .all()
                if shopping_params
                else []
            ),
        }
    )
    return context


def _parse_stock_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return None


def save_products_params(params, user_code):
    code = normalize_code(params.get('code'))
    minimum_stock = _parse_stock_value(params.get('minimum_stock'))
    maximum_stock = _parse_stock_value(params.get('maximum_stock'))

    if not code:
        return False, 'Debe ingresar un código de producto.', build_products_params_context(code)

    main_code = _resolve_main_code(code)
    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    if not product:
        return False, f'No se encontró un producto con el código {code}.', build_products_params_context(code)

    if minimum_stock is None or maximum_stock is None:
        return False, 'Los valores de stock deben ser numéricos.', build_products_params_context(main_code)

    if minimum_stock < 0 or maximum_stock < 0:
        return False, 'Los valores de stock deben ser positivos.', build_products_params_context(main_code)

    if minimum_stock > maximum_stock:
        return False, 'El stock mínimo no puede ser mayor que el máximo.', build_products_params_context(main_code)

    now = datetime.now()
    shopping_params = ShoppingProductsParam.query.filter(
        func.upper(func.trim(ShoppingProductsParam.code)) == main_code
    ).first()

    if shopping_params:
        shopping_params.minimum_stock = minimum_stock
        shopping_params.maximum_stock = maximum_stock
        shopping_params.update_at = now
        message = 'Parámetros de compras actualizados correctamente.'
    else:
        shopping_params = ShoppingProductsParam(
            code=main_code,
            minimum_stock=minimum_stock,
            maximum_stock=maximum_stock,
            update_at=now,
        )
        db.session.add(shopping_params)
        db.session.flush()
        message = 'Parámetros de compras creados correctamente.'

    next_history_correlative = (
        db.session.query(func.coalesce(func.max(ShoppingProductsParamsHistory.correlative), 0) + 1)
        .filter(ShoppingProductsParamsHistory.main_correlative == shopping_params.correlative)
        .scalar()
    )
    db.session.add(
        ShoppingProductsParamsHistory(
            correlative=next_history_correlative,
            main_correlative=shopping_params.correlative,
            user_code=user_code,
            register_date=now,
        )
    )
    db.session.commit()

    return True, message, build_products_params_context(main_code)




def get_shopping_overview():
    return {
        'purchase_orders': 0,
        'pending_approvals': 0,
        'received_orders': 0,
        'recent_activities': [],
    }


def get_provider_by_code(code_provider):
    if not code_provider:
        return None

    provider = Provider.query.filter_by(code=code_provider).first()
    return provider 


def _wildcard_pattern(value):
    pattern = (value or '').strip().replace('\\', '\\\\')
    pattern = pattern.replace('%', '\\%').replace('_', '\\_')
    pattern = f"%{pattern.replace('*', '%')}%"
    while '%%' in pattern:
        pattern = pattern.replace('%%', '%')
    return pattern


def get_product_filter_options():
    marks = (
        Mark.query
        .with_entities(Mark.code, Mark.description)
        .order_by(Mark.description.asc(), Mark.code.asc())
        .all()
    )
    departments = (
        Department.query
        .with_entities(Department.code, Department.description)
        .order_by(Department.description.asc(), Department.code.asc())
        .all()
    )
    return marks, departments


def search_products(query='', mark_codes=None, department_codes=None, page=1, per_page=10):
    query = (query or '').strip()
    mark_codes = [normalize_code(code) for code in (mark_codes or []) if normalize_code(code)]
    department_codes = [normalize_code(code) for code in (department_codes or []) if normalize_code(code)]
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    product_query = (
        Product.query
        .with_entities(
            Product.code,
            Product.description,
            Unit.description.label('unit_description'),
            ProductsUnit.main_unit.label('main_unit'),
            Mark.description.label('mark_description'),
            Department.description.label('department_description'),
        )
        .outerjoin(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
    )

    if query:
        if '*' in query:
            search_value = _wildcard_pattern(query)
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(search_value, escape='\\'),
                    Product.description.ilike(search_value, escape='\\'),
                    Product.referenc.ilike(search_value, escape='\\'),
                )
            )
        else:
            search_value = f'%{query}%'
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(search_value),
                    Product.description.ilike(search_value),
                    Product.referenc.ilike(search_value),
                )
            )

    if mark_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.mark)).in_(mark_codes))

    if department_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.department)).in_(department_codes))

    product_query = product_query.order_by(Product.description.asc(), Product.code.asc())
    total = product_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    products = product_query.limit(per_page).offset((page - 1) * per_page).all()

    return products, total, total_pages, page


def search_products_for_params(query='', mark_codes=None, department_codes=None, page=1, per_page=10):
    query = (query or '').strip()
    mark_codes = [normalize_code(code) for code in (mark_codes or []) if normalize_code(code)]
    department_codes = [normalize_code(code) for code in (department_codes or []) if normalize_code(code)]
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    product_query = (
        Product.query
        .with_entities(
            Product.code,
            Product.description,
            Unit.description.label('unit_description'),
            ProductsUnit.main_unit.label('main_unit'),
            Mark.description.label('mark_description'),
            Department.description.label('department_description'),
            ShoppingProductsParam.minimum_stock.label('shopping_minimum_stock'),
            ShoppingProductsParam.maximum_stock.label('shopping_maximum_stock'),
            ShoppingProductsParam.update_at.label('shopping_update_at'),
        )
        .outerjoin(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .outerjoin(ShoppingProductsParam, ShoppingProductsParam.code == Product.code)
    )

    if query:
        if '*' in query:
            search_value = _wildcard_pattern(query)
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(search_value, escape='\\'),
                    Product.description.ilike(search_value, escape='\\'),
                    Product.referenc.ilike(search_value, escape='\\'),
                )
            )
        else:
            search_value = f'%{query}%'
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(search_value),
                    Product.description.ilike(search_value),
                    Product.referenc.ilike(search_value),
                )
            )

    if mark_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.mark)).in_(mark_codes))

    if department_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.department)).in_(department_codes))

    product_query = product_query.order_by(Product.description.asc(), Product.code.asc())
    total = product_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    products = product_query.limit(per_page).offset((page - 1) * per_page).all()

    return products, total, total_pages, page

def search_providers(query='', page=1, per_page=10):
    query = (query or '').strip()
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    provider_query = Provider.query.with_entities(
        Provider.code,
        Provider.contact,
        Provider.description,
    )

    if query:
        search_value = f'%{query}%'
        provider_query = provider_query.filter(
            or_(
                Provider.code.ilike(search_value),
                Provider.description.ilike(search_value),
            )
        )

    provider_query = provider_query.order_by(Provider.description.asc(), Provider.code.asc())
    total = provider_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    providers = provider_query.limit(per_page).offset((page - 1) * per_page).all()

    return providers, total, total_pages, page