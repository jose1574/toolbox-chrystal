from datetime import date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import and_, case, func, or_, text

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsProvider,
    ProductsCode,
    ProductsFailure,
    ProductsStock,
    ProductsUnit,
    Provider,
    Numbering,
    SalesOperation,
    SalesOperationDetail,
    SalesOperationDetailsCoin,
    ShoppingProductsParam,
    ShoppingProductsParamsHistory,
    Store,
    Tax,
    Unit,
    User,
    ShoppingOperation,
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


def get_product_purchase_history(code, limit=10):
    if not code:
        return []

    main_code = _resolve_main_code(code)
    if not main_code:
        return []

    rows = (
        db.session.query(
            ProductsProvider.emission_date,
            ProductsProvider.provider_code,
            Provider.provider_id,
            Provider.description.label('provider_description'),
            ProductsProvider.amount,
            ProductsProvider.unit.label('unit_correlative'),
            ProductsUnit.unit.label('unit_code'),
            Unit.description.label('unit_description'),
            ProductsProvider.unitary_cost,
        )
        .select_from(ProductsProvider)
        .outerjoin(Provider, Provider.code == ProductsProvider.provider_code)
        .outerjoin(ProductsUnit, ProductsUnit.correlative == ProductsProvider.unit)
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .filter(func.upper(func.trim(ProductsProvider.product_code)) == main_code)
        .order_by(ProductsProvider.emission_date.desc().nullslast(), ProductsProvider.line.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            'emission_date': row.emission_date,
            'provider_code': row.provider_code,
            'provider_id': row.provider_id,
            'provider_description': row.provider_description,
            'amount': row.amount or 0,
            'unit': row.unit_description or row.unit_code or row.unit_correlative,
            'unitary_cost': row.unitary_cost or 0,
            'total': (row.amount or 0) * (row.unitary_cost or 0),
        }
        for row in rows
    ]


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else None
    except (TypeError, ValueError):
        return None


def _build_period_label(period_start, granularity):
    if not period_start:
        return '-'

    if isinstance(period_start, datetime):
        period_start = period_start.date()

    if granularity == 'month':
        return period_start.strftime('%m/%Y')
    if granularity == 'week':
        iso_year, iso_week, _ = period_start.isocalendar()
        return f'Sem {iso_week:02d}/{iso_year}'
    return period_start.strftime('%d')


def _get_secondary_coin_code():
    return db.session.execute(
        text("SELECT r_system_value FROM get_system_properties(52, '001', '00', '00') LIMIT 1")
    ).scalar() or '02'


def _build_sales_amount_expressions():
    factor = func.coalesce(Numbering.factor, 1)
    freight_discount_factor = (
        1
        + (func.coalesce(SalesOperation.percent_freight, 0) / 100)
        - (func.coalesce(SalesOperation.percent_discount, 0) / 100)
    )
    return {
        'amount': func.coalesce(SalesOperationDetail.amount, 0) * factor,
        'total': func.coalesce(SalesOperationDetail.total, 0) * factor,
        'total_net_02': func.coalesce(SalesOperationDetailsCoin.total_net * freight_discount_factor, 0) * factor,
    }


def _assign_store_colors(stores):
    palette = [
        '#0d6efd',
        '#198754',
        '#dc3545',
        '#fd7e14',
        '#20c997',
        '#6f42c1',
        '#0dcaf0',
        '#d63384',
        '#ffc107',
        '#6c757d',
    ]
    for index, store in enumerate(stores):
        store['color'] = palette[index % len(palette)]
    return stores


def _store_color_map(stores):
    return {store['label']: store.get('color', '#0d6efd') for store in stores}


def get_product_sales_context(code=None, date_from=None, date_to=None, granularity='month', chart_group='period'):
    allowed_granularities = {'day': 'day', 'week': 'week', 'month': 'month'}
    allowed_chart_groups = {'period': 'period', 'store': 'store'}
    selected_granularity = allowed_granularities.get(granularity, 'month')
    selected_chart_group = allowed_chart_groups.get(chart_group, 'period')
    selected_code = normalize_code(code)
    main_code = _resolve_main_code(selected_code) if selected_code else ''
    end_date = _parse_date(date_to) or date.today()
    start_date = _parse_date(date_from) or end_date.replace(day=1)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    context = {
        'selected_code': main_code or selected_code,
        'date_from': start_date.isoformat(),
        'date_to': end_date.isoformat(),
        'granularity': selected_granularity,
        'chart_group': selected_chart_group,
        'series': [],
        'chart_series': [],
        'sales_by_store': [],
        'sales_by_user': [],
        'totals': {'amount': 0, 'total': 0, 'total_net_02': 0},
        'max_period_amount': 0,
    }

    if not main_code:
        return context

    secondary_coin_code = _get_secondary_coin_code()
    amount_expressions = _build_sales_amount_expressions()
    base_filters = (
        func.upper(func.trim(SalesOperationDetail.code_product)) == main_code,
        SalesOperation.operation_type == 'BILL',
        SalesOperation.emission_date.between(start_date, end_date),
        SalesOperation.wait.is_(False),
        or_(SalesOperation.canceled.is_(False), SalesOperation.canceled.is_(None)),
    )
    coin_join = and_(
        SalesOperationDetailsCoin.main_correlative == SalesOperationDetail.main_correlative,
        SalesOperationDetailsCoin.main_line == SalesOperationDetail.line,
        SalesOperationDetailsCoin.coin_code == secondary_coin_code,
    )
    period_start = func.date_trunc(selected_granularity, SalesOperation.emission_date).label('period_start')

    period_rows = (
        db.session.query(
            period_start,
            func.coalesce(func.sum(amount_expressions['amount']), 0).label('amount'),
            func.coalesce(func.sum(amount_expressions['total']), 0).label('total'),
            func.coalesce(func.sum(amount_expressions['total_net_02']), 0).label('total_net_02'),
        )
        .select_from(SalesOperationDetail)
        .join(SalesOperation, SalesOperation.correlative == SalesOperationDetail.main_correlative)
        .join(Numbering, and_(Numbering.code == SalesOperation.operation_type, Numbering.module == 'SALES'))
        .outerjoin(SalesOperationDetailsCoin, coin_join)
        .filter(*base_filters)
        .group_by(period_start)
        .order_by(period_start)
        .all()
    )
    series = [
        {
            'label': _build_period_label(row.period_start, selected_granularity),
            'amount': float(row.amount or 0),
            'total': float(row.total or 0),
            'total_net_02': float(row.total_net_02 or 0),
        }
        for row in period_rows
    ]

    store_rows = (
        db.session.query(
            SalesOperationDetail.store.label('store_code'),
            Store.description.label('store_description'),
            func.coalesce(func.sum(amount_expressions['amount']), 0).label('amount'),
            func.coalesce(func.sum(amount_expressions['total']), 0).label('total'),
            func.coalesce(func.sum(amount_expressions['total_net_02']), 0).label('total_net_02'),
        )
        .select_from(SalesOperationDetail)
        .join(SalesOperation, SalesOperation.correlative == SalesOperationDetail.main_correlative)
        .join(Numbering, and_(Numbering.code == SalesOperation.operation_type, Numbering.module == 'SALES'))
        .outerjoin(SalesOperationDetailsCoin, coin_join)
        .outerjoin(Store, Store.code == SalesOperationDetail.store)
        .filter(*base_filters)
        .group_by(SalesOperationDetail.store, Store.description)
        .order_by(func.sum(amount_expressions['amount']).desc())
        .all()
    )

    sales_by_store = _assign_store_colors([
        {
            'label': row.store_description or row.store_code or 'Sin depósito',
            'amount': float(row.amount or 0),
            'total': float(row.total or 0),
            'total_net_02': float(row.total_net_02 or 0),
        }
        for row in store_rows
    ])
    store_colors = _store_color_map(sales_by_store)

    store_period_rows = (
        db.session.query(
            period_start,
            SalesOperationDetail.store.label('store_code'),
            Store.description.label('store_description'),
            func.coalesce(func.sum(amount_expressions['amount']), 0).label('amount'),
            func.coalesce(func.sum(amount_expressions['total']), 0).label('total'),
            func.coalesce(func.sum(amount_expressions['total_net_02']), 0).label('total_net_02'),
        )
        .select_from(SalesOperationDetail)
        .join(SalesOperation, SalesOperation.correlative == SalesOperationDetail.main_correlative)
        .join(Numbering, and_(Numbering.code == SalesOperation.operation_type, Numbering.module == 'SALES'))
        .outerjoin(SalesOperationDetailsCoin, coin_join)
        .outerjoin(Store, Store.code == SalesOperationDetail.store)
        .filter(*base_filters)
        .group_by(period_start, SalesOperationDetail.store, Store.description)
        .order_by(period_start, Store.description)
        .all()
    )
    store_period_series = []
    for row in store_period_rows:
        store_label = row.store_description or row.store_code or 'Sin depósito'
        period_label = _build_period_label(row.period_start, selected_granularity)
        store_period_series.append(
            {
                'label': period_label,
                'detail_label': store_label,
                'amount': float(row.amount or 0),
                'total': float(row.total or 0),
                'total_net_02': float(row.total_net_02 or 0),
                'color': store_colors.get(store_label, '#0d6efd'),
            }
        )

    user_rows = (
        db.session.query(
            SalesOperation.user_code,
            User.description.label('user_description'),
            func.coalesce(func.sum(amount_expressions['amount']), 0).label('amount'),
            func.coalesce(func.sum(amount_expressions['total']), 0).label('total'),
            func.coalesce(func.sum(amount_expressions['total_net_02']), 0).label('total_net_02'),
        )
        .select_from(SalesOperationDetail)
        .join(SalesOperation, SalesOperation.correlative == SalesOperationDetail.main_correlative)
        .join(Numbering, and_(Numbering.code == SalesOperation.operation_type, Numbering.module == 'SALES'))
        .outerjoin(SalesOperationDetailsCoin, coin_join)
        .outerjoin(User, User.code == SalesOperation.user_code)
        .filter(*base_filters)
        .group_by(SalesOperation.user_code, User.description)
        .order_by(func.sum(amount_expressions['amount']).desc())
        .all()
    )

    sales_by_user = [
        {
            'label': row.user_description or row.user_code or 'Sin usuario',
            'amount': float(row.amount or 0),
            'total': float(row.total or 0),
            'total_net_02': float(row.total_net_02 or 0),
        }
        for row in user_rows
    ]
    chart_series = store_period_series if selected_chart_group == 'store' else series

    context.update(
        {
            'series': series,
            'chart_series': chart_series,
            'sales_by_store': sales_by_store,
            'sales_by_user': sales_by_user,
            'store_legend': sales_by_store if selected_chart_group == 'store' else [],
            'totals': {
                'amount': sum(item['amount'] for item in series),
                'total': sum(item['total'] for item in series),
                'total_net_02': sum(item['total_net_02'] for item in series),
            },
            'max_period_amount': max((item['amount'] for item in chart_series), default=0),
        }
    )
    return context


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


def get_product_code_availability_context(code):
    product_code = normalize_code(code)
    if not product_code:
        return {
            'code': product_code,
            'is_available': False,
            'message': 'Debe indicar el codigo del producto.',
        }

    existing_product = Product.query.filter(func.upper(func.trim(Product.code)) == product_code).first()
    if existing_product:
        return {
            'code': product_code,
            'is_available': False,
            'message': 'Ya existe un producto con ese codigo.',
        }

    existing_alternate_code = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == product_code
    ).first()
    if existing_alternate_code:
        return {
            'code': product_code,
            'is_available': False,
            'message': 'Ya existe un codigo alterno registrado con ese codigo.',
        }

    return {
        'code': product_code,
        'is_available': True,
        'message': 'Codigo disponible.',
    }


def _get_product_edit_options():
    return {
        'marks': Mark.query.with_entities(Mark.code, Mark.description).order_by(Mark.description.asc(), Mark.code.asc()).all(),
        'departments': Department.query.with_entities(Department.code, Department.description).order_by(Department.description.asc(), Department.code.asc()).all(),
        'taxes': Tax.query.with_entities(Tax.code, Tax.description, Tax.aliquot).order_by(Tax.description.asc(), Tax.code.asc()).all(),
        'unit_options': Unit.query.with_entities(Unit.code, Unit.description).order_by(Unit.description.asc(), Unit.code.asc()).all(),
    }


def _build_new_product_form_product(code='', form_values=None):
    form_values = form_values or {}
    return SimpleNamespace(
        code=normalize_code(form_values.get('code') or code),
        description=(form_values.get('description') or '').strip(),
        short_name=(form_values.get('short_name') or '').strip(),
        mark=normalize_code(form_values.get('mark')) or None,
        model=(form_values.get('model') or '').strip() or None,
        referenc=(form_values.get('referenc') or '').strip() or None,
        department=normalize_code(form_values.get('department')) or '00',
        buy_tax=normalize_code(form_values.get('buy_tax')) or None,
        sale_tax=normalize_code(form_values.get('sale_tax')) or None,
        days_warranty=0,
        rounding_type=0,
        costing_type=0,
        discount=0,
        max_discount=0,
        minimal_sale=0,
        maximal_sale=0,
        status=None,
        origin=None,
        take_department_utility=False,
        allow_decimal=False,
        edit_name=False,
        sale_price=0,
        product_type=None,
        technician=None,
        request_technician=False,
        serialized=False,
        request_details=False,
        request_amount=False,
        coin=None,
        allow_negative_stock=False,
        use_scale=False,
        add_unit_description=False,
        use_lots=False,
        lots_order=0,
        minimal_stock=0,
        notify_minimal_stock=False,
        size=None,
        color=None,
        extract_net_from_unit_cost_plus_tax=False,
        extract_net_from_unit_price_plus_tax=False,
        maximum_stock=0,
    )


def _build_submitted_product_units(params):
    if not params or not hasattr(params, 'getlist'):
        return []

    unit_codes = params.getlist('unit_code')
    conversion_factors = params.getlist('conversion_factor')
    unit_types = params.getlist('unit_type')
    main_unit_index = params.get('main_unit_index')
    show_in_screen_index = params.get('show_in_screen')
    buy_unit_indexes = set(params.getlist('is_for_buy'))
    sale_unit_indexes = set(params.getlist('is_for_sale'))
    units = []

    for index, unit_code in enumerate(unit_codes):
        units.append(SimpleNamespace(
            unit=normalize_code(unit_code),
            conversion_factor=conversion_factors[index] if index < len(conversion_factors) else 1,
            unit_type=int(unit_types[index]) if index < len(unit_types) and unit_types[index] in ('0', '1', '2') else 1,
            main_unit=str(index) == str(main_unit_index),
            show_in_screen=str(index) == str(show_in_screen_index),
            is_for_buy=str(index) in buy_unit_indexes,
            is_for_sale=str(index) in sale_unit_indexes,
        ))

    return units


def get_product_edit_form_context(code, errors=None, form_values=None, form_mode='edit'):
    main_code = _resolve_main_code(code)
    if form_mode == 'create':
        return {
            'product': _build_new_product_form_product(code, form_values),
            **_get_product_edit_options(),
            'product_units': _build_submitted_product_units(form_values),
            'product_codes': _build_submitted_product_codes(form_values) if form_values else [],
            'errors': errors or [],
            'form_values': form_values or {},
            'form_mode': 'create',
        }

    if not main_code:
        return None

    product = Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
    if not product:
        return None

    product_units = _build_submitted_product_units(form_values) if form_values else (
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
        **_get_product_edit_options(),
        'product_units': product_units,
        'product_codes': product_codes,
        'errors': errors or [],
        'form_values': form_values or {},
        'form_mode': 'edit',
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
    form_mode = params.get('form_mode') or 'edit'
    is_create = form_mode == 'create'
    errors = []
    if not code:
        errors.append('Debe indicar el producto.')

    product = Product.query.filter(func.upper(func.trim(Product.code)) == code).first() if code else None
    if is_create and product:
        errors.append('Ya existe un producto con ese código.')
    elif not is_create and code and not product:
        errors.append('No se encontró el producto seleccionado.')

    if is_create and code:
        existing_alternate_code = ProductsCode.query.filter(func.upper(func.trim(ProductsCode.other_code)) == code).first()
        if existing_alternate_code:
            errors.append('Ya existe un código alterno registrado con ese código.')

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
        context = get_product_edit_form_context(code, errors, params, form_mode=form_mode)
        if context:
            return False, errors, context
        return False, errors, {'product': product, 'errors': errors, 'form_values': params, 'form_mode': form_mode}

    if is_create:
        product = _build_new_product_form_product(code, params)

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


def search_products(query='', reference='', mark_codes=None, department_codes=None, page=1, per_page=10, sort_by='', sort_dir='asc', provider_code='', show_all_products=False):
    query = (query or '').strip()
    reference = (reference or '').strip()
    mark_codes = [normalize_code(code) for code in (mark_codes or []) if normalize_code(code)]
    department_codes = [normalize_code(code) for code in (department_codes or []) if normalize_code(code)]
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)
    sort_by = (sort_by or '').strip()
    sort_dir = 'desc' if sort_dir == 'desc' else 'asc'
    provider_code = normalize_code(provider_code)

    product_query = (
        Product.query
        .with_entities(
            Product.code,
            Product.description,
            Product.referenc,
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
        .where(Product.status == '01')
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

    if reference:
        if '*' in reference:
            reference_value = _wildcard_pattern(reference)
            product_query = product_query.filter(Product.referenc.ilike(reference_value, escape='\\'))
        else:
            product_query = product_query.filter(Product.referenc.ilike(f'%{reference}%'))

    if mark_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.mark)).in_(mark_codes))

    if department_codes:
        product_query = product_query.filter(func.upper(func.trim(Product.department)).in_(department_codes))

    if provider_code and not show_all_products:
        provider_product_codes = (
            db.session.query(func.upper(func.trim(ProductsProvider.product_code)))
            .filter(func.upper(func.trim(ProductsProvider.provider_code)) == provider_code)
            .distinct()
        )
        product_query = product_query.filter(func.upper(func.trim(Product.code)).in_(provider_product_codes))

    stock_sort_store = None
    if sort_by.startswith('stock:'):
        stock_sort_store = normalize_code(sort_by.split(':', 1)[1])

    if stock_sort_store:
        stock_sort_subquery = (
            db.session.query(
                ProductsStock.product_code.label('product_code'),
                func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_quantity'),
            )
            .filter(func.upper(func.trim(ProductsStock.store)) == stock_sort_store)
            .group_by(ProductsStock.product_code)
            .subquery()
        )
        stock_sort_expression = func.coalesce(stock_sort_subquery.c.stock_quantity, 0)
        product_query = product_query.outerjoin(stock_sort_subquery, stock_sort_subquery.c.product_code == Product.code)
        product_query = product_query.order_by(
            stock_sort_expression.desc() if sort_dir == 'desc' else stock_sort_expression.asc(),
            Product.description.asc(),
            Product.code.asc(),
        )
    else:
        product_query = product_query.order_by(Product.description.asc(), Product.code.asc())

    total = product_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    product_rows = product_query.limit(per_page).offset((page - 1) * per_page).all()
    product_codes = [row.code for row in product_rows]

    stock_stores = [
        {
            'code': row.code,
            'description': row.description or row.code,
        }
        for row in Store.query.with_entities(Store.code, Store.description).order_by(Store.description.asc(), Store.code.asc()).all()
    ]
    stock_by_product = {code: {} for code in product_codes}

    if product_codes:
        stock_rows = (
            db.session.query(
                ProductsStock.product_code,
                ProductsStock.store,
                func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_quantity'),
            )
            .filter(ProductsStock.product_code.in_(product_codes))
            .group_by(ProductsStock.product_code, ProductsStock.store)
            .all()
        )

        for row in stock_rows:
            stock_by_product.setdefault(row.product_code, {})[row.store] = float(row.stock_quantity or 0)

    products = []
    for row in product_rows:
        product = row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)
        product['stock_by_store'] = stock_by_product.get(row.code, {})
        products.append(product)

    return products, total, total_pages, page, stock_stores


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


def get_provider_purchase_context(provider_code, page=1, per_page=10):
    provider_code = normalize_code(provider_code)
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    empty_context = {
        'provider_code': provider_code,
        'shopping_operations': [],
        'total_purchases': 0,
        'total_pages': 1,
        'current_page': 1,
        'last_purchase_date': None,
        'total_purchase_amount': 0.0,
        'per_page': per_page,
    }

    provider = Provider.query.filter(func.upper(func.trim(Provider.code)) == provider_code).first()
    if not provider:
        return empty_context

    shopping_query = (
        ShoppingOperation.query
        .with_entities(
            ShoppingOperation.correlative,
            ShoppingOperation.document_no,
            ShoppingOperation.control_no,
            ShoppingOperation.emission_date,
            ShoppingOperation.wait,
            ShoppingOperation.total,
        )
        .filter(func.upper(func.trim(ShoppingOperation.provider_code)) == provider_code)
        .order_by(ShoppingOperation.emission_date.desc(), ShoppingOperation.correlative.desc())
    )

    total = shopping_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    shopping_operations = shopping_query.limit(per_page).offset((page - 1) * per_page).all()

    summary = (
        db.session.query(
            func.max(ShoppingOperation.emission_date).label('last_purchase_date'),
            func.coalesce(func.sum(ShoppingOperation.total), 0).label('total_purchase_amount'),
        )
        .filter(func.upper(func.trim(ShoppingOperation.provider_code)) == provider_code)
        .first()
    )

    return {
        'provider_code': provider_code,
        'shopping_operations': shopping_operations,
        'total_purchases': total,
        'total_pages': total_pages,
        'current_page': page,
        'last_purchase_date': summary.last_purchase_date if summary else None,
        'total_purchase_amount': float(summary.total_purchase_amount or 0) if summary else 0.0,
        'per_page': per_page,
    }


def get_provider_inventory_context(provider_code, page=1, per_page=10):
    provider_code = normalize_code(provider_code)
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    empty_context = {
        'provider_code': provider_code,
        'products': [],
        'total_products': 0,
        'total_pages': 1,
        'current_page': 1,
        'total_product_units': 0.0,
        'with_inventory': 0,
        'without_inventory': 0,
        'with_inventory_percent': 0.0,
        'without_inventory_percent': 0.0,
        'per_page': per_page,
    }

    provider = Provider.query.filter(func.upper(func.trim(Provider.code)) == provider_code).first()
    if not provider:
        return empty_context

    provider_products = (
        db.session.query(
            func.upper(func.trim(ProductsProvider.product_code)).label('product_code'),
            func.coalesce(func.sum(ProductsProvider.amount), 0).label('purchased_amount'),
            func.max(ProductsProvider.emission_date).label('last_purchase_date'),
        )
        .filter(func.upper(func.trim(ProductsProvider.provider_code)) == provider_code)
        .filter(ProductsProvider.product_code.isnot(None))
        .group_by(func.upper(func.trim(ProductsProvider.product_code)))
        .subquery()
    )

    stock_totals = (
        db.session.query(
            func.upper(func.trim(ProductsStock.product_code)).label('product_code'),
            func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_total'),
        )
        .group_by(func.upper(func.trim(ProductsStock.product_code)))
        .subquery()
    )

    total_products = db.session.query(func.count()).select_from(provider_products).scalar() or 0
    total_pages = max((total_products + per_page - 1) // per_page, 1)
    page = min(page, total_pages)

    summary = (
        db.session.query(
            func.coalesce(func.sum(provider_products.c.purchased_amount), 0).label('total_product_units'),
            func.coalesce(
                func.sum(
                    case(
                        (func.coalesce(stock_totals.c.stock_total, 0) > 0, 1),
                        else_=0,
                    )
                ),
                0,
            ).label('with_inventory'),
        )
        .select_from(provider_products)
        .outerjoin(stock_totals, stock_totals.c.product_code == provider_products.c.product_code)
        .first()
    )

    with_inventory = int(summary.with_inventory or 0) if summary else 0
    without_inventory = max(total_products - with_inventory, 0)
    with_inventory_percent = (with_inventory / total_products * 100) if total_products else 0.0
    without_inventory_percent = (without_inventory / total_products * 100) if total_products else 0.0

    rows = (
        db.session.query(
            provider_products.c.product_code,
            Product.description.label('product_description'),
            provider_products.c.purchased_amount,
            provider_products.c.last_purchase_date,
            func.coalesce(stock_totals.c.stock_total, 0).label('stock_total'),
        )
        .select_from(provider_products)
        .outerjoin(Product, func.upper(func.trim(Product.code)) == provider_products.c.product_code)
        .outerjoin(stock_totals, stock_totals.c.product_code == provider_products.c.product_code)
        .order_by(provider_products.c.last_purchase_date.desc().nullslast(), provider_products.c.product_code.asc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )

    return {
        'provider_code': provider_code,
        'products': rows,
        'total_products': total_products,
        'total_pages': total_pages,
        'current_page': page,
        'total_product_units': float(summary.total_product_units or 0) if summary else 0.0,
        'with_inventory': with_inventory,
        'without_inventory': without_inventory,
        'with_inventory_percent': with_inventory_percent,
        'without_inventory_percent': without_inventory_percent,
        'per_page': per_page,
    }


def shopping_operation_by_provider(provider_code, page=1, per_page=10):
    context = get_provider_purchase_context(provider_code, page, per_page)
    return (
        context['shopping_operations'],
        context['total_purchases'],
        context['total_pages'],
        context['current_page'],
    )
