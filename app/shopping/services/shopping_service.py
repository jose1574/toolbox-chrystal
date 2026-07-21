from datetime import datetime

from sqlalchemy import func, or_, text

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsCode,
    ProductsFailure,
    ProductsStock,
    ProductsUnit,
    Provider,
    ShoppingProductsParam,
    ShoppingProductsParamsHistory,
    Store,
    Tax,
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


def _parse_inventory_param_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return None


def get_product_shopping_param(code):
    main_code = _resolve_main_code(code)
    if not main_code:
        return None

    return ShoppingProductsParam.query.filter(
        func.upper(func.trim(ShoppingProductsParam.code)) == main_code
    ).first()


def get_product_shopping_param_form_context(code, errors=None, form_values=None):
    main_code = _resolve_main_code(code)
    if not main_code:
        return None

    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    if not product:
        return None

    return {
        'product': product,
        'shopping_params': get_product_shopping_param(main_code),
        'errors': errors or [],
        'form_values': form_values or {},
    }


def _record_shopping_param_history(shopping_params, user_code, register_date):
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
            register_date=register_date,
        )
    )


def create_product_shopping_param(code, minimum_stock, maximum_stock, user_code):
    now = datetime.now()
    shopping_params = ShoppingProductsParam(
        code=code,
        minimum_stock=minimum_stock,
        maximum_stock=maximum_stock,
        update_at=now,
    )
    db.session.add(shopping_params)
    db.session.flush()
    _record_shopping_param_history(shopping_params, user_code, now)
    db.session.commit()
    return shopping_params


def update_product_shopping_param(shopping_params, minimum_stock, maximum_stock, user_code):
    now = datetime.now()
    shopping_params.minimum_stock = minimum_stock
    shopping_params.maximum_stock = maximum_stock
    shopping_params.update_at = now
    _record_shopping_param_history(shopping_params, user_code, now)
    db.session.commit()
    return shopping_params


def save_product_shopping_param(params, user_code):
    code = normalize_code(params.get('code'))
    minimum_stock = _parse_stock_value(params.get('minimum_stock'))
    maximum_stock = _parse_stock_value(params.get('maximum_stock'))
    errors = []

    if not code:
        errors.append('Debe indicar el producto.')

    main_code = _resolve_main_code(code) if code else ''
    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first() if main_code else None
    if code and not product:
        errors.append('No se encontró el producto seleccionado.')

    if minimum_stock is None or maximum_stock is None:
        errors.append('Los valores mínimo y máximo deben ser numéricos.')
    elif minimum_stock < 0 or maximum_stock < 0:
        errors.append('Los valores mínimo y máximo no pueden ser negativos.')
    elif minimum_stock > maximum_stock:
        errors.append('El mínimo no puede ser mayor que el máximo.')

    if errors:
        context = get_product_shopping_param_form_context(main_code or code, errors, params)
        if context:
            return False, errors, context
        return False, errors, {
            'product': product,
            'shopping_params': None,
            'errors': errors,
            'form_values': params,
        }

    shopping_params = get_product_shopping_param(main_code)
    if shopping_params:
        shopping_params = update_product_shopping_param(shopping_params, minimum_stock, maximum_stock, user_code)
    else:
        shopping_params = create_product_shopping_param(main_code, minimum_stock, maximum_stock, user_code)

    return True, [], {
        'product': product,
        'shopping_params': shopping_params,
        'errors': [],
    }


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

    shopping_params = ShoppingProductsParam.query.filter(
        func.upper(func.trim(ShoppingProductsParam.code)) == main_code
    ).first()

    if shopping_params:
        update_product_shopping_param(shopping_params, minimum_stock, maximum_stock, user_code)
        message = 'Parámetros de compras actualizados correctamente.'
    else:
        create_product_shopping_param(main_code, minimum_stock, maximum_stock, user_code)
        message = 'Parámetros de compras creados correctamente.'

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


def get_product_edit_form_context(code, errors=None, form_values=None):
    main_code = _resolve_main_code(code)
    if not main_code:
        return None

    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    if not product:
        return None

    marks = Mark.query.with_entities(Mark.code, Mark.description).order_by(Mark.description.asc(), Mark.code.asc()).all()
    departments = Department.query.with_entities(Department.code, Department.description).order_by(Department.description.asc(), Department.code.asc()).all()
    taxes = Tax.query.with_entities(Tax.code, Tax.description, Tax.aliquot).order_by(Tax.description.asc(), Tax.code.asc()).all()
    unit_options = Unit.query.with_entities(Unit.code, Unit.description).order_by(Unit.description.asc(), Unit.code.asc()).all()
    product_units = (
        ProductsUnit.query
        .filter(func.upper(func.trim(ProductsUnit.product_code)) == main_code)
        .order_by(ProductsUnit.main_unit.desc(), ProductsUnit.correlative.asc())
        .all()
    )
    product_codes = _build_submitted_product_codes(form_values) if form_values else (
        ProductsCode.query
        .filter(func.upper(func.trim(ProductsCode.main_code)) == main_code)
        .order_by(ProductsCode.other_code.asc())
        .all()
    )

    return {
        'product': product,
        'marks': marks,
        'departments': departments,
        'taxes': taxes,
        'unit_options': unit_options,
        'product_units': product_units,
        'product_codes': product_codes,
        'errors': errors or [],
        'form_values': form_values or {},
    }


def _parse_float_value(value, default=0):
    try:
        return float(value if value not in (None, '') else default)
    except (TypeError, ValueError):
        return None


def _parse_product_units_form(params):
    unit_codes = params.getlist('unit_code')
    conversion_factors = params.getlist('conversion_factor')
    unit_types = params.getlist('unit_type')
    main_unit_index = params.get('main_unit_index')
    show_in_screen_index = params.get('show_in_screen')
    buy_unit_indexes = set(params.getlist('is_for_buy'))
    sale_unit_indexes = set(params.getlist('is_for_sale'))
    units = []
    errors = []
    seen_units = set()
    valid_units = {normalize_code(unit.code) for unit in Unit.query.with_entities(Unit.code).all()}

    for index, unit_code in enumerate(unit_codes):
        normalized_unit = normalize_code(unit_code)
        factor = _parse_float_value(conversion_factors[index] if index < len(conversion_factors) else '')
        if not normalized_unit and factor in (None, 0):
            continue
        if not normalized_unit:
            errors.append('Debe seleccionar la unidad en todas las filas agregadas.')
            continue
        is_main_unit = str(index) == str(main_unit_index)
        unit_type = '0' if is_main_unit else unit_types[index] if index < len(unit_types) else '1'
        if unit_type not in ('0', '1', '2'):
            errors.append('Debe seleccionar una forma de multiplicación válida.')
            continue
        if not is_main_unit and unit_type == '0':
            errors.append('Solo la unidad principal puede tener tipo de unidad principal.')
            continue
        if factor is None or factor <= 0:
            errors.append('El factor de conversión de cada unidad debe ser mayor a cero.')
            continue
        if normalized_unit not in valid_units:
            errors.append('Debe seleccionar una unidad válida.')
            continue
        if normalized_unit in seen_units:
            errors.append('No puede repetir la misma unidad para el producto.')
            continue
        seen_units.add(normalized_unit)
        units.append({
            'index': str(index),
            'unit': normalized_unit,
            'conversion_factor': factor,
            'unit_type': int(unit_type),
            'main_unit': is_main_unit,
            'show_in_screen': str(index) == str(show_in_screen_index),
            'is_for_buy': str(index) in buy_unit_indexes,
            'is_for_sale': str(index) in sale_unit_indexes,
        })

    if not units:
        errors.append('Debe indicar al menos una unidad para el producto.')
    elif not any(unit['main_unit'] for unit in units):
        errors.append('Debe seleccionar una unidad principal.')
    elif not any(unit['show_in_screen'] for unit in units):
        errors.append('Debe seleccionar una unidad de inicio.')

    return units, errors


def _build_submitted_product_codes(params):
    other_codes = params.getlist('other_code') if hasattr(params, 'getlist') else []
    code_types = params.getlist('code_type') if hasattr(params, 'getlist') else []
    codes = []
    for index, other_code in enumerate(other_codes):
        normalized_code = normalize_code(other_code)
        if not normalized_code:
            continue
        codes.append({
            'other_code': normalized_code,
            'code_type': (code_types[index] if index < len(code_types) else '').strip(),
        })
    return codes


def _parse_product_codes_form(params, product_code):
    codes = _build_submitted_product_codes(params)
    errors = []
    seen_codes = set()

    for code_data in codes:
        other_code = normalize_code(code_data['other_code'])
        if other_code in seen_codes:
            errors.append(f'El código alterno {other_code} está repetido en el formulario.')
            continue
        seen_codes.add(other_code)

        existing_code = ProductsCode.query.filter(func.upper(func.trim(ProductsCode.other_code)) == other_code).first()
        if other_code == product_code:
            if existing_code and normalize_code(existing_code.main_code) == product_code:
                continue
            errors.append('Un código alterno no puede ser igual al código principal del producto.')
            continue

        existing_product = Product.query.filter(func.upper(func.trim(Product.code)) == other_code).first()
        if existing_product and normalize_code(existing_product.code) != product_code:
            errors.append(f'El código alterno {other_code} ya pertenece a otro producto.')
            continue

        if existing_code and normalize_code(existing_code.main_code) != product_code:
            errors.append(f'El código alterno {other_code} ya está asignado a otro producto.')

    return codes, errors


def _call_set_product(product, params):
    db.session.execute(
        text(
            """
            SELECT set_product(
                :code, :description, :short_name, :mark, :model, :referenc, :department,
                :days_warranty, :sale_tax, :buy_tax, :rounding_type, :costing_type,
                :discount, :max_discount, :minimal_sale, :maximal_sale, :status, :origin,
                :take_department_utility, :allow_decimal, :edit_name, :sale_price,
                :product_type, :technician, :request_technician, :serialized,
                :request_details, :request_amount, :coin, :allow_negative_stock,
                :use_scale, :add_unit_description, :use_lots, :lots_order,
                :minimal_stock, :notify_minimal_stock, :size, :color,
                :extract_net_from_unit_cost_plus_tax, :extract_net_from_unit_price_plus_tax,
                :maximum_stock, :action
            )
            """
        ),
        {
            'code': product.code,
            'description': (params.get('description') or '').strip(),
            'short_name': (params.get('short_name') or '').strip(),
            'mark': normalize_code(params.get('mark')) or None,
            'model': (params.get('model') or '').strip() or None,
            'referenc': (params.get('referenc') or '').strip() or None,
            'department': normalize_code(params.get('department')) or None,
            'days_warranty': product.days_warranty or 0,
            'sale_tax': normalize_code(params.get('sale_tax')) or None,
            'buy_tax': normalize_code(params.get('buy_tax')) or None,
            'rounding_type': product.rounding_type or 0,
            'costing_type': product.costing_type or 0,
            'discount': product.discount or 0,
            'max_discount': product.max_discount or 0,
            'minimal_sale': product.minimal_sale or 0,
            'maximal_sale': product.maximal_sale or 0,
            'status': product.status,
            'origin': product.origin,
            'take_department_utility': bool(product.take_department_utility),
            'allow_decimal': bool(product.allow_decimal),
            'edit_name': bool(product.edit_name),
            'sale_price': product.sale_price or 0,
            'product_type': product.product_type,
            'technician': product.technician,
            'request_technician': bool(product.request_technician),
            'serialized': bool(product.serialized),
            'request_details': bool(product.request_details),
            'request_amount': bool(product.request_amount),
            'coin': product.coin,
            'allow_negative_stock': bool(product.allow_negative_stock),
            'use_scale': bool(product.use_scale),
            'add_unit_description': bool(product.add_unit_description),
            'use_lots': bool(product.use_lots),
            'lots_order': product.lots_order or 0,
            'minimal_stock': product.minimal_stock or 0,
            'notify_minimal_stock': bool(product.notify_minimal_stock),
            'size': product.size,
            'color': product.color,
            'extract_net_from_unit_cost_plus_tax': bool(product.extract_net_from_unit_cost_plus_tax),
            'extract_net_from_unit_price_plus_tax': bool(product.extract_net_from_unit_price_plus_tax),
            'maximum_stock': product.maximum_stock or 0,
            'action': 'I',
        },
    )


def _save_product_units(product_code, units):
    existing_units = {
        normalize_code(product_unit.unit): product_unit
        for product_unit in ProductsUnit.query.filter(func.upper(func.trim(ProductsUnit.product_code)) == product_code).all()
    }

    for unit_data in units:
        product_unit = existing_units.get(unit_data['unit'])
        if product_unit is None:
            product_unit = ProductsUnit(
                product_code=product_code,
                unit=unit_data['unit'],
                show_in_screen=True,
                is_for_buy=True,
                is_for_sale=True,
                unit_type=0,
            )
            db.session.add(product_unit)
        product_unit.conversion_factor = unit_data['conversion_factor']
        product_unit.unit_type = unit_data['unit_type']
        product_unit.main_unit = unit_data['main_unit']
        product_unit.show_in_screen = unit_data['show_in_screen']
        product_unit.is_for_buy = unit_data['is_for_buy']
        product_unit.is_for_sale = unit_data['is_for_sale']


def _save_product_codes(product_code, codes):
    ProductsCode.query.filter(func.upper(func.trim(ProductsCode.main_code)) == product_code).delete(synchronize_session=False)
    for code_data in codes:
        db.session.add(
            ProductsCode(
                main_code=product_code,
                other_code=normalize_code(code_data['other_code']),
                code_type=(code_data.get('code_type') or '').strip() or None,
            )
        )


def save_product_attributes(params):
    code = normalize_code(params.get('code'))
    errors = []
    if not code:
        errors.append('Debe indicar el producto.')

    product = Product.query.filter(func.upper(func.trim(Product.code)) == code).first() if code else None
    if code and not product:
        errors.append('No se encontró el producto seleccionado.')

    description = (params.get('description') or '').strip()
    if not description:
        errors.append('Debe indicar el nombre del producto.')

    if params.get('department') and not Department.query.filter_by(code=normalize_code(params.get('department'))).first():
        errors.append('Debe seleccionar un departamento válido.')
    if params.get('mark') and not Mark.query.filter_by(code=normalize_code(params.get('mark'))).first():
        errors.append('Debe seleccionar una marca válida.')
    if params.get('buy_tax') and not Tax.query.filter_by(code=normalize_code(params.get('buy_tax'))).first():
        errors.append('Debe seleccionar un impuesto de compra válido.')
    if params.get('sale_tax') and not Tax.query.filter_by(code=normalize_code(params.get('sale_tax'))).first():
        errors.append('Debe seleccionar un impuesto de venta válido.')

    units, unit_errors = _parse_product_units_form(params)
    errors.extend(unit_errors)
    product_codes, code_errors = _parse_product_codes_form(params, code)
    errors.extend(code_errors)

    if errors:
        context = get_product_edit_form_context(code, errors, params)
        if context:
            return False, errors, context
        return False, errors, {'product': product, 'errors': errors, 'form_values': params}

    _call_set_product(product, params)
    _save_product_units(code, units)
    _save_product_codes(code, product_codes)
    db.session.commit()
    return True, [], {
        'product': get_product_order_details(code),
        'inventory_params': get_product_inventory_params(code),
        'shopping_params': get_product_shopping_param(code),
        'include_inventory_params_oob': True,
    }


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


def get_product_inventory_params(code):
    main_code = _resolve_main_code(code)
    if not main_code:
        return []

    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    if not product:
        return []

    stock_rows = (
        db.session.query(
            ProductsStock.store.label('store_code'),
            Store.description.label('store_name'),
            func.coalesce(func.sum(ProductsStock.stock), 0).label('stock'),
        )
        .outerjoin(Store, Store.code == ProductsStock.store)
        .filter(func.upper(func.trim(ProductsStock.product_code)) == main_code)
        .group_by(ProductsStock.store, Store.description)
        .all()
    )
    params_rows = (
        db.session.query(
            ProductsFailure.store_code.label('store_code'),
            Store.description.label('store_name'),
            ProductsFailure.minimal_stock.label('minimum_stock'),
            ProductsFailure.maximum_stock.label('maximum_stock'),
        )
        .outerjoin(Store, Store.code == ProductsFailure.store_code)
        .filter(func.upper(func.trim(ProductsFailure.product_code)) == main_code)
        .all()
    )

    stores = {}
    for row in stock_rows:
        normalized_store = normalize_code(row.store_code)
        stores[normalized_store] = {
            'product_code': product.code,
            'store_code': row.store_code,
            'store_name': row.store_name or row.store_code,
            'stock': float(row.stock or 0),
            'minimum_stock': None,
            'maximum_stock': None,
            'is_total': False,
        }

    for row in params_rows:
        normalized_store = normalize_code(row.store_code)
        stores.setdefault(
            normalized_store,
            {
                'product_code': product.code,
                'store_code': row.store_code,
                'store_name': row.store_name or row.store_code,
                'stock': 0,
                'minimum_stock': None,
                'maximum_stock': None,
                'is_total': False,
            },
        )
        stores[normalized_store]['minimum_stock'] = row.minimum_stock
        stores[normalized_store]['maximum_stock'] = row.maximum_stock

    return sorted(stores.values(), key=lambda store: store['store_name'] or '')


def get_product_inventory_param_form_context(code, store_code, errors=None):
    main_code = _resolve_main_code(code)
    normalized_store_code = normalize_code(store_code)
    if not main_code or not normalized_store_code:
        return None

    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    store = Store.query.filter(func.upper(func.trim(Store.code)) == normalized_store_code).first()
    if not product or not store:
        return None

    params = ProductsFailure.query.filter(
        func.upper(func.trim(ProductsFailure.product_code)) == main_code,
        func.upper(func.trim(ProductsFailure.store_code)) == normalized_store_code,
    ).first()

    stock = (
        db.session.query(func.coalesce(func.sum(ProductsStock.stock), 0))
        .filter(
            func.upper(func.trim(ProductsStock.product_code)) == main_code,
            func.upper(func.trim(ProductsStock.store)) == normalized_store_code,
        )
        .scalar()
    )

    return {
        'product': product,
        'store': store,
        'stock': float(stock or 0),
        'params': params,
        'errors': errors or [],
    }


def save_product_inventory_param(params):
    code = _resolve_main_code(params.get('code'))
    store_code = normalize_code(params.get('store_code'))
    minimum_stock = _parse_inventory_param_value(params.get('minimum_stock'))
    maximum_stock = _parse_inventory_param_value(params.get('maximum_stock'))
    errors = []

    if not code:
        errors.append('Debe indicar el producto.')
    if not store_code:
        errors.append('Debe indicar el depósito.')
    if minimum_stock is None or maximum_stock is None:
        errors.append('Los valores mínimo y máximo deben ser numéricos.')
    elif minimum_stock < 0 or maximum_stock < 0:
        errors.append('Los valores mínimo y máximo no pueden ser negativos.')
    elif minimum_stock > maximum_stock:
        errors.append('El mínimo no puede ser mayor que el máximo.')

    product = Product.query.filter(func.upper(func.trim(Product.code)) == code).first() if code else None
    store = Store.query.filter(func.upper(func.trim(Store.code)) == store_code).first() if store_code else None
    if code and not product:
        errors.append('No se encontró el producto seleccionado.')
    if store_code and not store:
        errors.append('No se encontró el depósito seleccionado.')

    if errors:
        context = get_product_inventory_param_form_context(code, store_code, errors)
        if context:
            return False, errors, context
        return False, errors, {
            'product': product,
            'store': store,
            'stock': 0,
            'params': None,
            'errors': errors,
        }

    inventory_param = ProductsFailure.query.filter(
        func.upper(func.trim(ProductsFailure.product_code)) == code,
        func.upper(func.trim(ProductsFailure.store_code)) == store_code,
    ).first()

    if inventory_param:
        inventory_param.minimal_stock = minimum_stock
        inventory_param.maximum_stock = maximum_stock
    else:
        inventory_param = ProductsFailure(
            product_code=code,
            store_code=store_code,
            minimal_stock=minimum_stock,
            maximum_stock=maximum_stock,
        )
        db.session.add(inventory_param)

    db.session.commit()
    return True, [], {
        'inventory_params': get_product_inventory_params(code),
        'product_code': code,
    }
