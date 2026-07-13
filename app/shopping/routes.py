from flask import render_template, request, flash
from flask_login import login_required

from app.shopping import shopping_bp
from app.shopping.services import shopping_service as service

@shopping_bp.route('/product_order_details')
@login_required
def product_order_details():
    code = (request.args.get('code') or '').strip()
    product = service.get_product_order_details(code)
    return render_template('shopping/partials/product_order_details.html', product=product)



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
    
    return render_template('shopping/order.html', provider=provider)


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

    return render_template('shopping/partials/selected_provider_details.html', provider=provider)


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
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page = service.search_products(
        query=query,
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
        mark_codes=mark_codes,
        department_codes=department_codes,
        marks=marks,
        departments=departments,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
    )


@shopping_bp.route('/products_list')
@login_required
def products_list():
    query = (request.args.get('q') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page = service.search_products(
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
    )

    return render_template(
        'shopping/partials/products_list.html',
        products=products,
        query=query,
        mark_codes=mark_codes,
        department_codes=department_codes,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
    )