from flask import make_response, render_template, request, flash
from flask_login import current_user, login_required

from app.shopping import shopping_bp
from app.shopping.services import shopping_service as service

@shopping_bp.route('/product_order_details')
@login_required
def product_order_details():
    code = (request.args.get('code') or '').strip()
    product = service.get_product_order_details(code)
    inventory_params = service.get_product_inventory_params(code)
    shopping_params = service.get_product_shopping_param(code)
    purchase_history = service.get_product_purchase_history(code)
    return render_template(
        'shopping/partials/product_order_details.html',
        product=product,
        inventory_params=inventory_params,
        shopping_params=shopping_params,
        purchase_history=purchase_history,
        include_inventory_params_oob=True,
        include_sales_chart_oob=True,
        include_purchase_history_oob=True,
    )


@shopping_bp.route('/product_sales_chart')
@login_required
def product_sales_chart():
    sales_context = service.get_product_sales_context(
        code=(request.args.get('code') or '').strip(),
        date_from=request.args.get('date_from'),
        date_to=request.args.get('date_to'),
        granularity=request.args.get('granularity', 'month'),
        chart_group=request.args.get('chart_group', 'period'),
    )
    return render_template('shopping/partials/product_sales_chart.html', sales_context=sales_context)


@shopping_bp.route('/product_edit_modal')
@login_required
def product_edit_modal():
    code = (request.args.get('code') or '').strip()
    context = service.get_product_edit_form_context(code)
    if not context:
        return render_template(
            'shopping/partials/product_edit_modal.html',
            errors=['No se encontraron los datos del producto para editar.'],
            product=None,
            marks=[],
            departments=[],
            taxes=[],
            unit_options=[],
            product_units=[],
        )
    return render_template('shopping/partials/product_edit_modal.html', **context)


@shopping_bp.route('/product_create_modal')
@login_required
def product_create_modal():
    context = service.get_product_edit_form_context('', form_mode='create')
    return render_template('shopping/partials/product_edit_modal.html', **context)


@shopping_bp.route('/product_code_availability')
@login_required
def product_code_availability():
    code = (request.args.get('code') or '').strip()
    context = service.get_product_code_availability_context(code)
    return render_template('shopping/partials/product_code_availability.html', **context)


@shopping_bp.route('/save_product_attributes', methods=['POST'])
@login_required
def save_product_attributes():
    success, errors, context = service.save_product_attributes(request.form)
    if not success:
        response = make_response(render_template('shopping/partials/product_edit_modal.html', **context))
        response.headers['HX-Retarget'] = '#product-edit-modal-container'
        response.headers['HX-Reswap'] = 'innerHTML'
        return response

    return render_template('shopping/partials/product_order_details.html', **context)


@shopping_bp.route('/product_shopping_param_modal')
@login_required
def product_shopping_param_modal():
    code = (request.args.get('code') or '').strip()
    context = service.get_product_shopping_param_form_context(code)
    if not context:
        return render_template(
            'shopping/partials/product_shopping_param_modal.html',
            errors=['No se encontraron los datos para modificar el parámetro.'],
            product=None,
            shopping_params=None,
        )
    return render_template('shopping/partials/product_shopping_param_modal.html', **context)


@shopping_bp.route('/save_product_shopping_param', methods=['POST'])
@login_required
def save_product_shopping_param():
    success, errors, context = service.save_product_shopping_param(request.form.to_dict(), current_user.get_id())
    if not success:
        response = make_response(render_template('shopping/partials/product_shopping_param_modal.html', **context))
        response.headers['HX-Retarget'] = '#product-shopping-param-modal-container'
        response.headers['HX-Reswap'] = 'innerHTML'
        return response

    return render_template('shopping/partials/product_shopping_params.html', **context)


@shopping_bp.route('/product_inventory_param_modal')
@login_required
def product_inventory_param_modal():
    code = (request.args.get('code') or '').strip()
    store_code = (request.args.get('store_code') or '').strip()
    context = service.get_product_inventory_param_form_context(code, store_code)
    if not context:
        return render_template(
            'shopping/partials/product_inventory_param_modal.html',
            errors=['No se encontraron los datos para modificar el parámetro.'],
            product=None,
            store=None,
            stock=0,
            params=None,
        )
    return render_template('shopping/partials/product_inventory_param_modal.html', **context)


@shopping_bp.route('/save_product_inventory_param', methods=['POST'])
@login_required
def save_product_inventory_param():
    success, errors, context = service.save_product_inventory_param(request.form.to_dict())
    if not success:
        response = make_response(render_template('shopping/partials/product_inventory_param_modal.html', **context), 422)
        response.headers['HX-Retarget'] = '#product-inventory-param-modal-container'
        response.headers['HX-Reswap'] = 'innerHTML'
        return response

    return render_template('shopping/partials/product_inventory_params.html', inventory_params=context['inventory_params'])



@shopping_bp.route('/')
@login_required
def index():
    page_data = service.get_shopping_overview()
    return render_template('shopping/index.html', page_data=page_data)


#menu de orden de compras sin lista previa de productos
@shopping_bp.route('/order')
@login_required 
def order():
    code_provider = (request.args.get('code_provider') or '').strip()


    if not code_provider:
        return render_template('shopping/order.html', provider=None, selected_provider_code='')

    provider = service.get_provider_by_code(code_provider)
    if not provider:
        flash(f'No se encontró un proveedor con el código {code_provider}.', 'error')
        return render_template('shopping/order.html', provider=None, selected_provider_code=code_provider)
    
    return render_template(
        'shopping/order.html',
        provider=provider,
        inventory_params=[],
        purchase_history=[],
    )


@shopping_bp.route('/selected_provider_details')
@login_required
def selected_provider_details():
    code_provider = (request.args.get('code_provider') or '').strip()
    provider = service.get_provider_by_code(code_provider) if code_provider else None

    if provider is None:
        message = 'Ingresa un código de proveedor válido.'
        if code_provider:
            message = f'No se encontró un proveedor con el código {code_provider}.'
        flash(message, 'error')
        return render_template('shopping/partials/selected_provider_details.html', provider=None)

    purchase_context = service.get_provider_purchase_context(provider.code, page=1, per_page=5)
    inventory_context = service.get_provider_inventory_context(provider.code, page=1, per_page=5)
    return render_template(
        'shopping/partials/selected_provider_details.html',
        provider=provider,
        purchase_context=purchase_context,
        inventory_context=inventory_context,
    )


@shopping_bp.route('/provider_purchases')
@login_required
def provider_purchases():
    code_provider = (request.args.get('code_provider') or '').strip()
    page = request.args.get('page', 1, type=int)
    purchase_context = service.get_provider_purchase_context(code_provider, page=page, per_page=5)
    return render_template(
        'shopping/partials/provider_purchases.html',
        purchase_context=purchase_context,
    )


@shopping_bp.route('/provider_inventory')
@login_required
def provider_inventory():
    code_provider = (request.args.get('code_provider') or '').strip()
    page = request.args.get('page', 1, type=int)
    inventory_context = service.get_provider_inventory_context(code_provider, page=page, per_page=5)
    return render_template(
        'shopping/partials/provider_inventory.html',
        inventory_context=inventory_context,
    )


@shopping_bp.route('/providers_modal')
@login_required
def providers_modal():
    query = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    providers, total_providers, total_pages, current_page = service.search_providers(
        query=query,
        page=page,
        per_page=10,
    )

    return render_template(
        'shopping/partials/modal_providers.html',
        providers=providers,
        query=query,
        total_providers=total_providers,
        total_pages=total_pages,
        current_page=current_page,
    )


@shopping_bp.route('/providers_list')
@login_required
def providers_list():
    query = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    providers, total_providers, total_pages, current_page = service.search_providers(
        query=query,
        page=page,
        per_page=10,
    )

    return render_template(
        'shopping/partials/providers_list.html',
        providers=providers,
        query=query,
        total_providers=total_providers,
        total_pages=total_pages,
        current_page=current_page,
    )


@shopping_bp.route('/products_modal')
@login_required
def products_modal():
    query = (request.args.get('q') or '').strip()
    reference = (request.args.get('reference') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page, stock_stores = service.search_products(
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
    )
    marks, departments = service.get_product_filter_options()

    return render_template(
        'shopping/partials/modal_products.html',
        products=products,
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        marks=marks,
        departments=departments,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
        stock_stores=stock_stores,
    )


@shopping_bp.route('/products_list')
@login_required
def products_list():
    query = (request.args.get('q') or '').strip()
    reference = (request.args.get('reference') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    append = request.args.get('append') == '1'
    products, total_products, total_pages, current_page, stock_stores = service.search_products(
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
    )

    if append:
        return render_template(
            'shopping/partials/products_list_rows.html',
            products=products,
            query=query,
            reference=reference,
            mark_codes=mark_codes,
            department_codes=department_codes,
            total_pages=total_pages,
            current_page=current_page,
            stock_stores=stock_stores,
        )

    return render_template(
        'shopping/partials/products_list.html',
        products=products,
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
        stock_stores=stock_stores,
    )


@shopping_bp.route('/products_params')
@login_required
def products_params():
    code = (request.args.get('code') or '').strip()
    context = service.build_products_params_context(code)
    if code and not context.get('product'):
        flash(f'No se encontró un producto con el código {code}.', 'error')
    return render_template('shopping/shopping_products_params.html', **context)


@shopping_bp.route('/products_params_modal')
@login_required
def products_params_modal():
    query = (request.args.get('q') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page = service.search_products_for_params(
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
    )
    marks, departments = service.get_product_filter_options()

    return render_template(
        'shopping/partials/products_params_modal.html',
        products=products,
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        marks=marks,
        departments=departments,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
    )


@shopping_bp.route('/products_params_list')
@login_required
def products_params_list():
    query = (request.args.get('q') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page = service.search_products_for_params(
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
    )

    return render_template(
        'shopping/partials/products_params_list.html',
        products=products,
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
    )



# guardar parametros de compra
@shopping_bp.route('/save_products_params', methods=['POST'])
@login_required
def save_products_params():
    params = request.form.to_dict()
    success, message, context = service.save_products_params(params, current_user.get_id())
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return render_template('shopping/shopping_products_params.html', **context)