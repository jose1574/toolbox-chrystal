from flask import render_template, request, flash
from flask_login import login_required

from app.shopping import shopping_bp
from app.shopping.services import shopping_service as service


@shopping_bp.route('/')
@login_required
def index():
    page_data = service.get_shopping_overview()
    return render_template('shopping/index.html', page_data=page_data)


#menu de orden de compras sin lista previa de productos
@shopping_bp.route('/no_list_order')
@login_required 
def no_list_order():
    code_provider = (request.args.get('code_provider') or '').strip()


    if not code_provider:
        return render_template('shopping/no_list_order.html', provider=None, selected_provider_code='')

    provider = service.get_provider_by_code(code_provider)
    if not provider:
        flash(f'No se encontró un proveedor con el código {code_provider}.', 'error')
        return render_template('shopping/no_list_order.html', provider=None, selected_provider_code=code_provider)
    
    return render_template('shopping/no_list_order.html', provider=provider)


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