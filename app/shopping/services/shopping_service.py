import base64
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from sqlalchemy import and_, case, func, literal, or_, text
from sqlalchemy.orm import selectinload

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    PurchaseReviewList,
    PurchaseReviewListItem,
    PurchaseReviewNewProductItem,
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
    SystemProperty,
    Tax,
    Unit,
    User,
    ShoppingOperation,
    ShoppingCart,
    ShoppingCartItem,
)


MONEY_QUANTUM = Decimal('0.01')


def _parse_positive_quantity(value):
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        raise ValueError('La cantidad debe ser un número mayor que cero.')
    if quantity <= 0:
        raise ValueError('La cantidad debe ser mayor que cero.')
    return quantity


def _parse_optional_integer(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError('El identificador indicado no es válido.')


def get_or_create_shopping_cart(provider_code, buyer_code, source_review_list_id=None):
    provider_code = normalize_code(provider_code)
    buyer_code = normalize_code(buyer_code)
    source_review_list_id = _parse_optional_integer(source_review_list_id)
    if not provider_code or not buyer_code:
        raise ValueError('Debes indicar un proveedor y un comprador.')

    cart_query = ShoppingCart.query.filter(
        ShoppingCart.provider_code == provider_code,
        ShoppingCart.buyer_code == buyer_code,
        ShoppingCart.status == 'DRAFT',
    )
    if source_review_list_id is None:
        cart_query = cart_query.filter(ShoppingCart.source_review_list_id.is_(None))
    else:
        cart_query = cart_query.filter(ShoppingCart.source_review_list_id == source_review_list_id)

    cart = cart_query.order_by(ShoppingCart.correlative.desc()).first()
    if cart:
        return cart

    if source_review_list_id is not None:
        review_list = PurchaseReviewList.query.filter(
            PurchaseReviewList.correlative == source_review_list_id,
            PurchaseReviewList.provider_code == provider_code,
        ).first()
        if review_list is None:
            raise ValueError('La lista de revisión no pertenece al proveedor seleccionado.')

    cart = ShoppingCart(
        provider_code=provider_code,
        buyer_code=buyer_code,
        source_review_list_id=source_review_list_id,
        status='DRAFT',
    )
    db.session.add(cart)
    db.session.flush()
    return cart


def get_shopping_cart_context(provider_code, buyer_code, source_review_list_id=None):
    if not provider_code:
        return {'cart': None, 'items': [], 'subtotal': 0.0, 'total': 0.0}

    cart = get_or_create_shopping_cart(provider_code, buyer_code, source_review_list_id)
    items = (
        ShoppingCartItem.query.options(
            selectinload(ShoppingCartItem.product),
            selectinload(ShoppingCartItem.unit).selectinload(ProductsUnit.unit1),
        )
        .filter(ShoppingCartItem.cart_id == cart.correlative)
        .order_by(ShoppingCartItem.correlative.asc())
        .all()
    )
    item_context = []
    subtotal = Decimal('0')
    for item in items:
        line_total = _quantize_money(item.quantity * item.unitary_cost)
        subtotal += line_total
        item_context.append({
            'correlative': item.correlative,
            'product_code': item.product_code,
            'description': item.product.description if item.product else item.product_code,
            'unit': item.unit.unit1.description if item.unit and item.unit.unit1 else 'UND',
            'quantity': float(item.quantity or 0),
            'unitary_cost': float(item.unitary_cost or 0),
            'line_total': float(line_total),
        })
    total = float(_quantize_money(subtotal))
    return {'cart': cart, 'items': item_context, 'subtotal': total, 'total': total}


def add_shopping_cart_item(cart, product_code=None, unit_id=None, quantity=None, unitary_cost=0, note=None, source_review_item_id=None):
    source_review_item_id = _parse_optional_integer(source_review_item_id)
    if source_review_item_id is not None:
        review_item = (
            PurchaseReviewListItem.query.join(PurchaseReviewList)
            .filter(
                PurchaseReviewListItem.correlative == source_review_item_id,
                PurchaseReviewListItem.main_correlative == cart.source_review_list_id,
                PurchaseReviewList.provider_code == cart.provider_code,
                PurchaseReviewListItem.status == 'ACCEPTED',
            )
            .first()
        )
        if review_item is None:
            raise ValueError('El producto no fue aprobado para esta lista de compra.')
        product_code = review_item.product_code
        unit_id = _parse_optional_integer(unit_id) or review_item.unit
        if unit_id is not None and ProductsUnit.query.filter(
            ProductsUnit.correlative == unit_id,
            ProductsUnit.product_code == product_code,
        ).first() is None:
            raise ValueError('La unidad no corresponde al producto aprobado.')
        quantity = _parse_positive_quantity(quantity)
        try:
            unitary_cost = float(unitary_cost or 0)
        except (TypeError, ValueError):
            raise ValueError('El precio unitario no es válido.')
    else:
        if cart.source_review_list_id is not None:
            raise ValueError(
                'Los carritos asociados a una lista solo admiten productos aprobados.'
            )
        product_code = normalize_code(product_code)
        if not product_code or Product.query.filter(Product.code == product_code).first() is None:
            raise ValueError('El producto seleccionado no es válido.')
        unit_id = _parse_optional_integer(unit_id)
        if unit_id is not None and ProductsUnit.query.filter(
            ProductsUnit.correlative == unit_id,
            ProductsUnit.product_code == product_code,
        ).first() is None:
            raise ValueError('La unidad no corresponde al producto seleccionado.')
        quantity = _parse_positive_quantity(quantity)
        try:
            unitary_cost = float(unitary_cost or 0)
        except (TypeError, ValueError):
            raise ValueError('El precio unitario no es válido.')

    existing_item = ShoppingCartItem.query.filter(
        ShoppingCartItem.cart_id == cart.correlative,
        ShoppingCartItem.source_review_item_id == source_review_item_id,
    ).first() if source_review_item_id is not None else None
    if existing_item:
        existing_item.quantity = quantity
        existing_item.unitary_cost = unitary_cost
        existing_item.note = note or None
    else:
        db.session.add(ShoppingCartItem(
            cart_id=cart.correlative,
            product_code=product_code,
            unit_id=unit_id,
            source_review_item_id=source_review_item_id,
            quantity=quantity,
            unitary_cost=unitary_cost,
            note=note or None,
        ))
    db.session.commit()


def update_shopping_cart_item(cart, item_id, quantity):
    item = ShoppingCartItem.query.filter(
        ShoppingCartItem.correlative == item_id,
        ShoppingCartItem.cart_id == cart.correlative,
    ).first()
    if item is None:
        raise ValueError('El producto no pertenece al carrito actual.')
    item.quantity = _parse_positive_quantity(quantity)
    db.session.commit()


def remove_shopping_cart_item(cart, item_id):
    item = ShoppingCartItem.query.filter(
        ShoppingCartItem.correlative == item_id,
        ShoppingCartItem.cart_id == cart.correlative,
    ).first()
    if item is None:
        raise ValueError('El producto no pertenece al carrito actual.')
    db.session.delete(item)
    db.session.commit()


def _to_decimal(value, default='0'):
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return Decimal(default)


def _quantize_money(value):
    return _to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


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


def get_default_provider_coin_code():
    configured_coin_code = (
        db.session.query(SystemProperty.system_value)
        .filter(SystemProperty.code == 65)
        .filter(SystemProperty.system_value.isnot(None))
        .filter(func.trim(SystemProperty.system_value) != '')
        .order_by(
            case((SystemProperty.properties_group == '001', 0), else_=1),
            case((SystemProperty.profile == '00', 0), else_=1),
        )
        .limit(1)
        .scalar()
    )
    return normalize_code(configured_coin_code)


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


def get_provider_catalog_products(
    query='',
    reference='',
    mark_codes=None,
    department_codes=None,
    provider_code='',
    only_provider_products=False,
    page=1,
    per_page=20,
    sort_by='',
    sort_dir='asc',
):
    query = (query or '').strip()
    reference = (reference or '').strip()
    mark_codes = [normalize_code(code) for code in (mark_codes or []) if normalize_code(code)]
    department_codes = [normalize_code(code) for code in (department_codes or []) if normalize_code(code)]
    provider_code = normalize_code(provider_code)
    sort_by = (sort_by or '').strip()
    sort_dir = 'desc' if sort_dir == 'desc' else 'asc'
    page = max(page or 1, 1)
    per_page = max(min(per_page or 20, 100), 1)

    product_query = (
        db.session.query(
            Product.code.label('code'),
            Product.description.label('name'),
            Product.referenc.label('reference'),
            Department.description.label('department'),
            Mark.description.label('brand'),
            func.coalesce(ShoppingProductsParam.minimum_stock, 0).label('minimum_stock'),
            func.coalesce(ShoppingProductsParam.maximum_stock, 0).label('maximum_stock'),
        )
        .outerjoin(Department, Department.code == Product.department)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(ShoppingProductsParam, ShoppingProductsParam.code == Product.code)
        .filter(Product.status == '01')
    )

    if query:
        term = (query or '').strip()
        if '*' in term:
            pattern = _wildcard_pattern(term)
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(pattern, escape='\\'),
                    Product.description.ilike(pattern, escape='\\'),
                    Product.referenc.ilike(pattern, escape='\\'),
                )
            )
        else:
            search_value = f'%{term}%'
            product_query = product_query.filter(
                or_(
                    Product.code.ilike(search_value),
                    Product.description.ilike(search_value),
                    Product.referenc.ilike(search_value),
                )
            )

    if reference:
        ref_value = (reference or '').strip()
        if '*' in ref_value:
            pattern = _wildcard_pattern(ref_value)
            product_query = product_query.filter(Product.referenc.ilike(pattern, escape='\\'))
        else:
            product_query = product_query.filter(Product.referenc.ilike(f'%{ref_value}%'))

    if department_codes:
        product_query = product_query.filter(
            func.upper(func.trim(Product.department)).in_(department_codes)
        )

    if mark_codes:
        product_query = product_query.filter(
            func.upper(func.trim(Product.mark)).in_(mark_codes)
        )

    if only_provider_products and provider_code:
        provider_product_codes = (
            db.session.query(ProductsProvider.product_code)
            .filter(func.upper(func.trim(ProductsProvider.provider_code)) == provider_code)
            .distinct()
        )
        product_query = product_query.filter(Product.code.in_(provider_product_codes))

    total_products = product_query.order_by(None).with_entities(func.count(Product.code)).scalar() or 0

    product_query = _apply_provider_catalog_order(product_query, sort_by, sort_dir, provider_code)

    total_pages = max((total_products + per_page - 1) // per_page, 1)
    page = min(page, total_pages)

    rows = product_query.limit(per_page).offset((page - 1) * per_page).all()
    product_codes = [row.code for row in rows]
    catalog_units = _get_provider_catalog_units(product_codes, provider_code)
    last_costs = _get_latest_provider_costs(product_codes, provider_code)

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
        for stock_row in stock_rows:
            stock_by_product.setdefault(stock_row.product_code, {})[stock_row.store] = float(stock_row.stock_quantity or 0)

    products = []
    for row in rows:
        unit = catalog_units.get(normalize_code(row.code))
        units_per_main = _units_per_main(
            unit['conversion_factor'] if unit else 1,
            unit['unit_type'] if unit else 0,
        )
        raw_stock_by_store = stock_by_product.get(row.code, {})
        stock_total = sum(raw_stock_by_store.values()) / units_per_main
        minimum_stock = float(row.minimum_stock or 0) / units_per_main
        maximum_stock = float(row.maximum_stock or 0) / units_per_main
        replenishment_needed = _calculate_replenishment_quantity(
            stock_total, minimum_stock, maximum_stock
        )
        last_provider_cost = last_costs.get(normalize_code(row.code))
        products.append({
            'code': row.code,
            'name': row.name,
            'department': row.department or '-',
            'brand': row.brand or '-',
            'reference': row.reference or '-',
            'stock_total': stock_total,
            'stock_by_store': {
                store_code: stock_value / units_per_main
                for store_code, stock_value in raw_stock_by_store.items()
            },
            'minimum_stock': minimum_stock,
            'maximum_stock': maximum_stock,
            'replenishment_needed': replenishment_needed,
            'last_provider_cost': last_provider_cost,
            'unit_code': unit['unit_code'] if unit else '',
            'unit_description': unit['unit_description'] if unit else 'UND',
            'conversion_factor': unit['conversion_factor'] if unit else 1.0,
            'unit_type': unit['unit_type'] if unit else 0,
            'unit_correlative': unit['unit_correlative'] if unit else None,
        })

    return products, total_products, total_pages, page, stock_stores


def _stock_aggregate_subquery(store_code=None):
    stock_query = db.session.query(
        ProductsStock.product_code.label('product_code'),
        func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_quantity'),
    )
    if store_code:
        stock_query = stock_query.filter(ProductsStock.store == store_code)
    return stock_query.group_by(ProductsStock.product_code).subquery()


def _latest_provider_cost_subquery(provider_code):
    return (
        db.session.query(
            ProductsProvider.product_code.label('product_code'),
            ProductsProvider.unitary_cost.label('unitary_cost'),
        )
        .distinct(ProductsProvider.product_code)
        .filter(func.upper(func.trim(ProductsProvider.provider_code)) == provider_code)
        .order_by(
            ProductsProvider.product_code,
            ProductsProvider.emission_date.desc().nullslast(),
            ProductsProvider.line.desc(),
        )
        .subquery()
    )


def _get_latest_provider_costs(product_codes, provider_code):
    if not product_codes or not provider_code:
        return {}

    rows = (
        db.session.query(
            ProductsProvider.product_code,
            ProductsProvider.unitary_cost,
        )
        .filter(
            ProductsProvider.product_code.in_(product_codes),
            func.upper(func.trim(ProductsProvider.provider_code)) == provider_code,
        )
        .order_by(
            ProductsProvider.emission_date.desc().nullslast(),
            ProductsProvider.line.desc(),
        )
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault(
            normalize_code(row.product_code),
            float(row.unitary_cost) if row.unitary_cost is not None else None,
        )
    return latest


def _catalog_units_per_main_expression(product_query, provider_code):
    main_units = (
        db.session.query(
            ProductsUnit.product_code.label('product_code'),
            ProductsUnit.conversion_factor.label('conversion_factor'),
            ProductsUnit.unit_type.label('unit_type'),
        )
        .filter(ProductsUnit.main_unit.is_(True))
        .distinct(ProductsUnit.product_code)
        .order_by(ProductsUnit.product_code, ProductsUnit.correlative.desc())
        .subquery()
    )
    product_query = product_query.outerjoin(main_units, main_units.c.product_code == Product.code)
    conversion_factor = main_units.c.conversion_factor
    unit_type = main_units.c.unit_type

    if provider_code:
        provider_units = (
            db.session.query(
                ProductsProvider.product_code.label('product_code'),
                ProductsUnit.conversion_factor.label('conversion_factor'),
                ProductsUnit.unit_type.label('unit_type'),
            )
            .outerjoin(ProductsUnit, ProductsUnit.correlative == ProductsProvider.unit)
            .distinct(ProductsProvider.product_code)
            .filter(func.upper(func.trim(ProductsProvider.provider_code)) == provider_code)
            .order_by(
                ProductsProvider.product_code,
                ProductsProvider.emission_date.desc().nullslast(),
                ProductsProvider.line.desc(),
            )
            .subquery()
        )
        product_query = product_query.outerjoin(provider_units, provider_units.c.product_code == Product.code)
        conversion_factor = func.coalesce(provider_units.c.conversion_factor, main_units.c.conversion_factor)
        unit_type = func.coalesce(provider_units.c.unit_type, main_units.c.unit_type)

    factor = func.greatest(func.coalesce(conversion_factor, 1), 0.0001)
    units_per_main = case(
        (unit_type == 1, factor),
        (unit_type == 2, literal(1.0) / factor),
        else_=literal(1.0),
    )
    return product_query, units_per_main


def _apply_provider_catalog_order(product_query, sort_by, sort_dir, provider_code=''):
    descending = sort_dir == 'desc'

    def ordered(expression):
        return expression.desc().nullslast() if descending else expression.asc().nullsfirst()

    unit_sort = sort_by in ('stock_total', 'replenish', 'minimum', 'maximum') or sort_by.startswith('stock:')
    units_per_main = literal(1.0)
    if unit_sort:
        product_query, units_per_main = _catalog_units_per_main_expression(product_query, provider_code)

    if sort_by.startswith('stock:'):
        store_code = normalize_code(sort_by.split(':', 1)[1])
        if store_code:
            stock_sub = _stock_aggregate_subquery(store_code)
            product_query = product_query.outerjoin(stock_sub, stock_sub.c.product_code == Product.code)
            return product_query.order_by(
                ordered(func.coalesce(stock_sub.c.stock_quantity, 0) / units_per_main),
                Product.description.asc(),
                Product.code.asc(),
            )

    if sort_by in ('stock_total', 'replenish'):
        stock_sub = _stock_aggregate_subquery()
        product_query = product_query.outerjoin(stock_sub, stock_sub.c.product_code == Product.code)
        stock_expr = func.coalesce(stock_sub.c.stock_quantity, 0)
        if sort_by == 'replenish':
            stock_expr = func.greatest(
                literal(0),
                func.coalesce(ShoppingProductsParam.maximum_stock, 0) - stock_expr,
            )
        return product_query.order_by(
            ordered(stock_expr / units_per_main),
            Product.description.asc(),
            Product.code.asc(),
        )

    if sort_by == 'last_cost' and provider_code:
        cost_sub = _latest_provider_cost_subquery(provider_code)
        product_query = product_query.outerjoin(cost_sub, cost_sub.c.product_code == Product.code)
        return product_query.order_by(
            ordered(cost_sub.c.unitary_cost),
            Product.description.asc(),
            Product.code.asc(),
        )

    sort_columns = {
        'code_name': Product.description,
        'department': Department.description,
        'brand': Mark.description,
        'reference': Product.referenc,
        'minimum': func.coalesce(ShoppingProductsParam.minimum_stock, 0) / units_per_main,
        'maximum': func.coalesce(ShoppingProductsParam.maximum_stock, 0) / units_per_main,
    }
    primary = sort_columns.get(sort_by)
    if primary is None:
        return product_query.order_by(Product.description.asc(), Product.code.asc())

    return product_query.order_by(
        ordered(primary),
        Product.description.asc(),
        Product.code.asc(),
    )


def _get_provider_catalog_units(product_codes, provider_code):
    normalized_codes = [normalize_code(code) for code in product_codes if normalize_code(code)]
    if not normalized_codes:
        return {}

    latest_purchase = {}
    if provider_code:
        purchase_rows = (
            db.session.query(
                ProductsProvider.product_code,
                ProductsProvider.unit,
                ProductsUnit.correlative.label('unit_correlative'),
                ProductsUnit.unit.label('unit_code'),
                ProductsUnit.conversion_factor,
                ProductsUnit.unit_type,
                Unit.description.label('unit_description'),
            )
            .outerjoin(ProductsUnit, ProductsUnit.correlative == ProductsProvider.unit)
            .outerjoin(Unit, Unit.code == ProductsUnit.unit)
            .filter(
                func.upper(func.trim(ProductsProvider.product_code)).in_(normalized_codes),
                func.upper(func.trim(ProductsProvider.provider_code)) == provider_code,
            )
            .order_by(
                ProductsProvider.emission_date.desc().nullslast(),
                ProductsProvider.line.desc(),
            )
            .all()
        )
        for row in purchase_rows:
            latest_purchase.setdefault(normalize_code(row.product_code), row)

    fallback_rows = (
        db.session.query(
            ProductsUnit.product_code,
            ProductsUnit.correlative.label('unit_correlative'),
            ProductsUnit.unit.label('unit_code'),
            ProductsUnit.conversion_factor,
            ProductsUnit.unit_type,
            Unit.description.label('unit_description'),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .filter(
            func.upper(func.trim(ProductsUnit.product_code)).in_(normalized_codes),
            ProductsUnit.main_unit.is_(True),
        )
        .all()
    )
    fallback = {normalize_code(row.product_code): row for row in fallback_rows}
    result = {}
    for product_code in normalized_codes:
        row = latest_purchase.get(product_code) or fallback.get(product_code)
        if row:
            result[product_code] = {
                'unit_correlative': getattr(row, 'unit_correlative', None),
                'unit_code': row.unit_code or '',
                'unit_description': row.unit_description or row.unit_code or 'UND',
                'conversion_factor': float(row.conversion_factor or 1),
                'unit_type': row.unit_type or 0,
            }
    return result


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


def get_provider_offer_products(provider_code, product_codes, product_unit_correlatives=None):
    provider_code = normalize_code(provider_code)
    normalized_codes = [normalize_code(code) for code in (product_codes or []) if normalize_code(code)]
    if not normalized_codes:
        return []

    unique_codes = list(dict.fromkeys(normalized_codes))
    selected_correlatives = [str(value or '').strip() for value in (product_unit_correlatives or [])]
    requested_units_by_code = {}
    for index, product_code in enumerate(normalized_codes):
        if index < len(selected_correlatives):
            unit_correlative = selected_correlatives[index]
            if unit_correlative:
                requested_units_by_code[product_code] = unit_correlative

    last_cost_subquery = (
        db.session.query(ProductsProvider.unitary_cost)
        .filter(
            func.upper(func.trim(ProductsProvider.product_code)) == func.upper(func.trim(Product.code)),
            func.upper(func.trim(ProductsProvider.provider_code)) == provider_code,
        )
        .order_by(ProductsProvider.emission_date.desc().nullslast(), ProductsProvider.line.desc())
        .limit(1)
        .scalar_subquery()
    )

    rows = (
        db.session.query(
            Product.code.label('code'),
            Product.description.label('name'),
            Product.referenc.label('reference'),
            func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_total'),
            func.coalesce(ShoppingProductsParam.minimum_stock, 0).label('minimum_stock'),
            func.coalesce(ShoppingProductsParam.maximum_stock, 0).label('maximum_stock'),
            last_cost_subquery.label('last_provider_cost'),
        )
        .outerjoin(ProductsStock, ProductsStock.product_code == Product.code)
        .outerjoin(
            ShoppingProductsParam,
            func.upper(func.trim(ShoppingProductsParam.code)) == func.upper(func.trim(Product.code)),
        )
        .filter(Product.status == '01')
        .filter(func.upper(func.trim(Product.code)).in_(unique_codes))
        .group_by(
            Product.code,
            Product.description,
            Product.referenc,
            ShoppingProductsParam.minimum_stock,
            ShoppingProductsParam.maximum_stock,
        )
        .all()
    )

    row_map = {normalize_code(row.code): row for row in rows}
    catalog_units = _get_provider_catalog_units(unique_codes, provider_code)
    unit_rows = (
        db.session.query(
            ProductsUnit.correlative,
            ProductsUnit.product_code,
            ProductsUnit.unit,
            ProductsUnit.main_unit,
            ProductsUnit.is_for_buy,
            ProductsUnit.conversion_factor,
            ProductsUnit.unit_type,
            Unit.description.label('unit_description'),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .filter(func.upper(func.trim(ProductsUnit.product_code)).in_(unique_codes))
        .all()
    )
    units_by_product = {}
    for unit_row in unit_rows:
        units_by_product.setdefault(normalize_code(unit_row.product_code), []).append(unit_row)

    products = []
    for product_code in unique_codes:
        row = row_map.get(product_code)
        if not row:
            continue

        product_units = units_by_product.get(product_code, [])
        catalog_unit = catalog_units.get(product_code, {})
        selected_unit = None
        requested_unit_correlative = requested_units_by_code.get(product_code)
        if requested_unit_correlative:
            selected_unit = next(
                (unit for unit in product_units if str(getattr(unit, 'correlative', '') or '') == str(requested_unit_correlative)),
                None,
            )
        if selected_unit is None and catalog_unit:
            selected_unit = next(
                (unit for unit in product_units if normalize_code(unit.unit) == normalize_code(catalog_unit.get('unit_code'))),
                None,
            )
        if selected_unit is None:
            selected_unit = next(
                (unit for unit in product_units if unit.is_for_buy and unit.main_unit),
                next((unit for unit in product_units if unit.is_for_buy), None),
            ) or next(
                (unit for unit in product_units if unit.main_unit),
                product_units[0] if product_units else None,
            )

        selected_cost = row.last_provider_cost
        selected_cost_unit_correlative = catalog_unit.get('unit_correlative') if catalog_unit else None
        if requested_unit_correlative:
            selected_cost = (
                db.session.query(ProductsProvider.unitary_cost)
                .filter(
                    func.upper(func.trim(ProductsProvider.product_code)) == normalize_code(product_code),
                    func.upper(func.trim(ProductsProvider.provider_code)) == provider_code,
                    ProductsProvider.unit == requested_unit_correlative,
                )
                .order_by(ProductsProvider.emission_date.desc().nullslast(), ProductsProvider.line.desc())
                .limit(1)
                .scalar()
            )
            if selected_cost is not None:
                selected_cost_unit_correlative = requested_unit_correlative
        if selected_cost is None and catalog_unit and catalog_unit.get('unit_correlative'):
            selected_cost = (
                db.session.query(ProductsProvider.unitary_cost)
                .filter(
                    func.upper(func.trim(ProductsProvider.product_code)) == normalize_code(product_code),
                    func.upper(func.trim(ProductsProvider.provider_code)) == provider_code,
                    ProductsProvider.unit == catalog_unit.get('unit_correlative'),
                )
                .order_by(ProductsProvider.emission_date.desc().nullslast(), ProductsProvider.line.desc())
                .limit(1)
                .scalar()
            )
            if selected_cost is not None:
                selected_cost_unit_correlative = catalog_unit.get('unit_correlative')

        stock_total = float(row.stock_total or 0)
        minimum_stock = float(row.minimum_stock or 0)
        maximum_stock = float(row.maximum_stock or 0)
        suggested_quantity = _calculate_replenishment_quantity(
            stock_total, minimum_stock, maximum_stock
        )
        products.append({
            'code': row.code,
            'name': row.name or row.code,
            'reference': row.reference or '-',
            'suggested_quantity': suggested_quantity,
            'last_provider_cost': float(selected_cost) if selected_cost is not None else None,
            'last_provider_cost_unit_correlative': selected_cost_unit_correlative,
            'unit': selected_unit.unit_description if selected_unit else (catalog_unit.get('unit_description') or 'UND'),
            'unit_code': selected_unit.unit if selected_unit else (catalog_unit.get('unit_code') or ''),
            'unit_correlative': getattr(selected_unit, 'correlative', None) if selected_unit else catalog_unit.get('unit_correlative'),
            'conversion_factor': float((selected_unit.conversion_factor if selected_unit else catalog_unit.get('conversion_factor')) or 1) if (selected_unit or catalog_unit) else 1.0,
            'unit_type': (selected_unit.unit_type if selected_unit is not None else catalog_unit.get('unit_type')) or 0,
            'unit_options': [
                {
                    'code': unit.unit,
                    'description': unit.unit_description or unit.unit,
                    'conversion_factor': float(unit.conversion_factor or 1),
                    'unit_type': unit.unit_type or 0,
                    'main_unit': bool(unit.main_unit),
                    'correlative': getattr(unit, 'correlative', None),
                }
                for unit in product_units
            ],
        })

    return products


def _get_products_stock_totals(product_codes):
    normalized_codes = [normalize_code(code) for code in product_codes if normalize_code(code)]
    if not normalized_codes:
        return {}

    rows = (
        db.session.query(
            func.upper(func.trim(ProductsStock.product_code)).label('product_code'),
            func.coalesce(func.sum(ProductsStock.stock), 0).label('stock_total'),
        )
        .filter(func.upper(func.trim(ProductsStock.product_code)).in_(normalized_codes))
        .group_by(func.upper(func.trim(ProductsStock.product_code)))
        .all()
    )
    return {row.product_code: float(row.stock_total or 0) for row in rows}


def build_provider_offer_context(items, coin_symbol='$'):
    normalized_items = []
    total_amount = Decimal('0')
    stock_totals = _get_products_stock_totals([
        item.get('code')
        for item in (items or [])
        if (item.get('item_type') or 'catalog') != 'new_product'
    ])

    for item in items or []:
        quantity = _to_decimal(item.get('quantity') or 0)
        unit_price = _to_decimal(item.get('unit_price') or 0)
        item_type = item.get('item_type') or 'catalog'
        unit_options = item.get('unit_options') or (
            [] if item_type == 'new_product' else get_provider_product_units(item.get('code'))
        )
        current_units_per_main = _to_decimal(_units_per_main(
            item.get('conversion_factor'), item.get('unit_type')
        ))
        main_quantity = _to_decimal(item.get('main_quantity') or (quantity * current_units_per_main))
        main_unit_price = unit_price / current_units_per_main if current_units_per_main else Decimal('0')
        conversion_factor = max(float(item.get('conversion_factor') or 1), 0.0001)
        unit_type = int(item.get('unit_type') or 0)
        units_per_main = _to_decimal(_units_per_main(conversion_factor, unit_type))
        purchase_quantity = (main_quantity / units_per_main) if units_per_main else main_quantity
        purchase_unit_price = _quantize_money(main_unit_price * units_per_main)
        discount_percent = _to_decimal(item.get('discount_percent') or 0)
        subtotal = _quantize_money(purchase_quantity * purchase_unit_price)
        discount_factor = Decimal('1') - (discount_percent / Decimal('100'))
        total_with_discount = _quantize_money(subtotal * discount_factor)
        total_amount += total_with_discount
        stock_main = stock_totals.get(normalize_code(item.get('code')), 0.0) if item_type != 'new_product' else None
        stock_total = (
            None if stock_main is None
            else (float(stock_main) / float(units_per_main) if units_per_main else float(stock_main))
        )

        normalized_items.append({
            'item_id': item.get('item_id') or item.get('code') or '',
            'item_type': item_type,
            'code': item.get('code') or '',
            'name': item.get('name') or item.get('code') or '-',
            'main_code': item.get('proposed_main_code') or item.get('code') or '',
            'reference': item.get('reference') or '-',
            'stock_total': stock_total,
            'quantity': float(purchase_quantity),
            'unit': item.get('unit') or 'UND',
            'unit_code': item.get('unit_code') or '',
            'unit_correlative': item.get('unit_correlative'),
            'unit_options': unit_options,
            'conversion_factor': conversion_factor,
            'unit_type': unit_type,
            'unit_price': float(purchase_unit_price),
            'discount_percent': float(discount_percent),
            'subtotal': float(subtotal),
            'total_with_discount': float(total_with_discount),
            'note': item.get('note') or '',
            'mark_name': item.get('mark_name') or '',
            'department_name': item.get('department_name') or '',
            'has_image': bool(item.get('image_token')),
            'image_token': item.get('image_token') or '',
            'image_correlative': None,
        })

    return {
        'items': normalized_items,
        'products_count': len(normalized_items),
        'total_items': len(normalized_items),
        'total_amount': float(_quantize_money(total_amount)),
        'coin_symbol': coin_symbol or '$',
    }


def _provider_review_status_meta(status):
    normalized_status = normalize_code(status)
    status_map = {
        'DRAFT': ('Borrador', 'warning'),
        'SUBMITTED': ('En revision', 'info'),
        'REVIEWED': ('Revisada', 'primary'),
        'APPROVED': ('Aprobada', 'success'),
        'REJECTED': ('Rechazada', 'danger'),
    }
    return status_map.get(normalized_status, (normalized_status or 'Sin estado', 'secondary'))


def _build_provider_review_list_detail(review_list, coin_symbol='$'):
    detail_items = []
    total_amount = Decimal('0')

    catalog_items = sorted(review_list.items or [], key=lambda current: current.correlative or 0)
    for item in catalog_items:
        quantity = _to_decimal(item.requested_amount or 0)
        unit_price = _to_decimal(item.unitary_cost or 0)
        subtotal = _quantize_money(quantity * unit_price)
        total_amount += subtotal

        detail_items.append({
            'item_type': 'catalog',
            'review_item_id': item.correlative,
            'code': item.product_code or '',
            'name': (item.product.description if item.product else item.product_code) or '-',
            'reference': (item.product.referenc if item.product else '') or '-',
            'quantity': float(quantity),
            'unit': (item.unit_detail.unit1.description if item.unit_detail and item.unit_detail.unit1 else None) or item.unit_detail.unit if item.unit_detail else 'UND',
            'unit_id': item.unit,
            'unit_price': float(_quantize_money(unit_price)),
            'subtotal': float(subtotal),
            'status': item.status or 'PENDING',
            'status_label': _provider_review_status_meta(item.status)[0],
            'status_badge_class': _provider_review_status_meta(item.status)[1],
            'note': item.note or '',
            'rejected_reason': item.rejected_reason or '',
        })

    new_product_items = sorted(review_list.new_product_items or [], key=lambda current: current.correlative or 0)
    for item in new_product_items:
        quantity = _to_decimal(item.requested_amount or 0)
        unit_price = _to_decimal(item.unitary_cost or 0)
        subtotal = _quantize_money(quantity * unit_price)
        total_amount += subtotal

        detail_items.append({
            'item_type': 'new_product',
            'code': item.proposed_main_code or '',
            'name': item.proposed_description or '-',
            'reference': item.proposed_reference or '-',
            'quantity': float(quantity),
            'unit': (item.unit.description if item.unit else item.proposed_unit_code) or 'UND',
            'unit_price': float(_quantize_money(unit_price)),
            'subtotal': float(subtotal),
            'status': item.status or 'PENDING',
            'status_label': _provider_review_status_meta(item.status)[0],
            'status_badge_class': _provider_review_status_meta(item.status)[1],
            'note': item.provider_note or '',
            'rejected_reason': item.rejected_reason or '',
            'main_code': item.proposed_main_code or '',
            'mark_name': item.mark.description if item.mark else '',
            'department_name': item.department.description if item.department else '',
            'has_image': bool(item.proposed_image_type),
            'image_token': '',
            'image_correlative': item.correlative if item.proposed_image_type else None,
        })

    status_label, status_badge_class = _provider_review_status_meta(review_list.status)
    return {
        'correlative': review_list.correlative,
        'reference': review_list.reference or f'Lista #{review_list.correlative}',
        'status': review_list.status or '',
        'status_label': status_label,
        'status_badge_class': status_badge_class,
        'created_at': review_list.created_at,
        'submitted_at': review_list.submitted_at,
        'reviewed_at': review_list.reviewed_at,
        'buyer_notes': review_list.buyer_notes or '',
        'provider_notes': review_list.provider_notes or '',
        'items': detail_items,
        'products_count': len(detail_items),
        'total_items': len(detail_items),
        'total_amount': float(_quantize_money(total_amount)),
        'coin_symbol': coin_symbol or '$',
    }

def get_provider_review_lists(provider_code, coin_symbol='$'):
    normalized_provider_code = normalize_code(provider_code)
    if not normalized_provider_code:
        return []

    review_lists = (
        PurchaseReviewList.query.options(
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.product),
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.unit_detail).selectinload(ProductsUnit.unit1),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.mark),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.department),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.unit),
        )
        .filter(PurchaseReviewList.provider_code == normalized_provider_code)
        .filter(PurchaseReviewList.list_type == 'PROVIDER_SUBMISSION')
        .order_by(
            PurchaseReviewList.submitted_at.desc().nullslast(),
            PurchaseReviewList.created_at.desc(),
            PurchaseReviewList.correlative.desc(),
        )
        .all()
    )

    review_list_details = [_build_provider_review_list_detail(review_list, coin_symbol=coin_symbol) for review_list in review_lists]
    return [
        {
            'correlative': review_list['correlative'],
            'reference': review_list['reference'],
            'status': review_list['status'],
            'status_label': review_list['status_label'],
            'status_badge_class': review_list['status_badge_class'],
            'created_at': review_list['created_at'],
            'submitted_at': review_list['submitted_at'],
            'reviewed_at': review_list['reviewed_at'],
            'provider_notes': review_list['provider_notes'],
            'products_count': review_list['products_count'],
            'total_items': review_list['total_items'],
            'total_amount': review_list['total_amount'],
            'coin_symbol': review_list['coin_symbol'],
        }
        for review_list in review_list_details
    ]


def get_provider_review_lists_context(provider_code, selected_review_list_correlative=None, coin_symbol='$'):
    normalized_provider_code = normalize_code(provider_code)
    if not normalized_provider_code:
        return {
            'review_lists': [],
            'selected_review_list': None,
        }

    review_lists = (
        PurchaseReviewList.query.options(
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.product),
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.unit_detail).selectinload(ProductsUnit.unit1),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.mark),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.department),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.unit),
        )
        .filter(PurchaseReviewList.provider_code == normalized_provider_code)
        .filter(PurchaseReviewList.list_type == 'PROVIDER_SUBMISSION')
        .order_by(
            PurchaseReviewList.submitted_at.desc().nullslast(),
            PurchaseReviewList.created_at.desc(),
            PurchaseReviewList.correlative.desc(),
        )
        .all()
    )

    selected_correlative = None
    try:
        selected_correlative = int(selected_review_list_correlative) if selected_review_list_correlative else None
    except (TypeError, ValueError):
        selected_correlative = None

    review_list_details = [_build_provider_review_list_detail(review_list, coin_symbol=coin_symbol) for review_list in review_lists]
    selected_review_list = next(
        (review_list for review_list in review_list_details if review_list['correlative'] == selected_correlative),
        review_list_details[0] if review_list_details else None,
    )

    review_list_summaries = [
        {
            'correlative': review_list['correlative'],
            'reference': review_list['reference'],
            'status': review_list['status'],
            'status_label': review_list['status_label'],
            'status_badge_class': review_list['status_badge_class'],
            'created_at': review_list['created_at'],
            'submitted_at': review_list['submitted_at'],
            'products_count': review_list['products_count'],
            'total_amount': review_list['total_amount'],
            'coin_symbol': review_list['coin_symbol'],
            'provider_notes': review_list['provider_notes'],
            'is_selected': bool(selected_review_list and review_list['correlative'] == selected_review_list['correlative']),
        }
        for review_list in review_list_details
    ]

    return {
        'review_lists': review_list_summaries,
        'selected_review_list': selected_review_list,
    }


def get_provider_review_list_detail_context(provider_code, review_list_correlative, coin_symbol='$'):
    normalized_provider_code = normalize_code(provider_code)
    if not normalized_provider_code:
        return None

    try:
        selected_correlative = int(review_list_correlative)
    except (TypeError, ValueError):
        return None

    review_list = (
        PurchaseReviewList.query.options(
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.product),
            selectinload(PurchaseReviewList.items).selectinload(PurchaseReviewListItem.unit_detail).selectinload(ProductsUnit.unit1),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.mark),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.department),
            selectinload(PurchaseReviewList.new_product_items).selectinload(PurchaseReviewNewProductItem.unit),
        )
        .filter(PurchaseReviewList.correlative == selected_correlative)
        .filter(PurchaseReviewList.provider_code == normalized_provider_code)
        .filter(PurchaseReviewList.list_type == 'PROVIDER_SUBMISSION')
        .first()
    )

    if review_list is None:
        return None

    return _build_provider_review_list_detail(review_list, coin_symbol=coin_symbol)


def attach_review_list_pdf_images(review_list_detail):
    items = (review_list_detail or {}).get('items') or []
    correlatives = [
        item.get('image_correlative')
        for item in items
        if item.get('has_image') and item.get('image_correlative')
    ]
    if not correlatives:
        return review_list_detail

    rows = (
        db.session.query(
            PurchaseReviewNewProductItem.correlative,
            PurchaseReviewNewProductItem.proposed_image,
            PurchaseReviewNewProductItem.proposed_image_type,
        )
        .filter(PurchaseReviewNewProductItem.correlative.in_(correlatives))
        .all()
    )
    images = {}
    for row in rows:
        if not row.proposed_image:
            continue
        images[row.correlative] = {
            'image_base64': base64.b64encode(bytes(row.proposed_image)).decode('ascii'),
            'image_mime': row.proposed_image_type or 'image/jpeg',
        }

    for item in items:
        image_data = images.get(item.get('image_correlative')) or {}
        item['image_base64'] = image_data.get('image_base64', '')
        item['image_mime'] = image_data.get('image_mime', '')

    return review_list_detail


def _units_per_main(conversion_factor, unit_type):
    factor = max(float(conversion_factor or 1), 0.0001)
    unit_type = int(unit_type or 0)
    return factor if unit_type == 1 else (1 / factor if unit_type == 2 else 1)


def _calculate_replenishment_quantity(stock_total, minimum_stock, maximum_stock):
    stock_total = float(stock_total or 0)
    maximum_stock = float(maximum_stock or 0)
    return max(0.0, maximum_stock - stock_total)


def convert_unit_price(price, from_conversion_factor, from_unit_type, to_conversion_factor, to_unit_type):
    """Convert a unit price from one product unit into another using ProductUnit factors."""
    if price is None:
        return 0.0

    from_units_per_main = _units_per_main(from_conversion_factor, from_unit_type)
    to_units_per_main = _units_per_main(to_conversion_factor, to_unit_type)
    if not from_units_per_main or not to_units_per_main:
        return float(price)

    return float(price) * to_units_per_main / from_units_per_main


def get_provider_product_units(product_code):
    rows = (
        db.session.query(
            ProductsUnit.correlative,
            ProductsUnit.unit,
            ProductsUnit.conversion_factor,
            ProductsUnit.unit_type,
            ProductsUnit.main_unit,
            ProductsUnit.is_for_buy,
            Unit.description.label('unit_description'),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .filter(func.upper(func.trim(ProductsUnit.product_code)) == normalize_code(product_code))
        .all()
    )
    return [
        {
            'code': row.unit,
            'description': row.unit_description or row.unit,
            'conversion_factor': float(row.conversion_factor or 1),
            'unit_type': row.unit_type or 0,
            'main_unit': bool(row.main_unit),
            'is_for_buy': bool(row.is_for_buy),
            'correlative': getattr(row, 'correlative', None),
        }
        for row in rows
    ]


def get_provider_product_unit_by_correlative(unit_correlative):
    if not unit_correlative:
        return None

    row = (
        db.session.query(
            ProductsUnit.correlative,
            ProductsUnit.unit,
            ProductsUnit.conversion_factor,
            ProductsUnit.unit_type,
            ProductsUnit.main_unit,
            ProductsUnit.is_for_buy,
            Unit.description.label('unit_description'),
        )
        .outerjoin(Unit, Unit.code == ProductsUnit.unit)
        .filter(ProductsUnit.correlative == unit_correlative)
        .first()
    )
    if not row:
        return None

    return {
        'code': row.unit,
        'description': row.unit_description or row.unit,
        'conversion_factor': float(row.conversion_factor or 1),
        'unit_type': row.unit_type or 0,
        'main_unit': bool(row.main_unit),
        'is_for_buy': bool(row.is_for_buy),
        'correlative': getattr(row, 'correlative', None),
    }


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

    product_unit = (
        db.session.query(Unit.description.label('unit_description'))
        .outerjoin(ProductsUnit, ProductsUnit.unit == Unit.code)
        .filter(
            func.upper(func.trim(ProductsUnit.product_code)) == main_code,
            ProductsUnit.main_unit.is_(True),
        )
        .first()
    )
    unit_description = (product_unit.unit_description if product_unit else None) or 'UND'

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
            'unit_description': unit_description,
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
                'unit_description': unit_description,
                'minimum_stock': None,
                'maximum_stock': None,
                'is_total': False,
            },
        )
        stores[normalized_store]['minimum_stock'] = row.minimum_stock
        stores[normalized_store]['maximum_stock'] = row.maximum_stock

    return sorted(stores.values(), key=lambda store: store['store_name'] or '')


def get_product_total_inventory(code):
    return sum(inventory_param['stock'] for inventory_param in get_product_inventory_params(code))


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
