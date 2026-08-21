import re
from functools import wraps

from flask import make_response, redirect, render_template, request, flash, session, url_for
from flask_login import current_user, login_required

from app import db
from app.models import ProviderRegistration, User
from app.shopping import shopping_bp
from app.shopping.services import shopping_service as service


def normalize_upper(value):
    return (value or '').strip().upper()


def normalize_rif(value):
    return re.sub(r'[\s\-]+', '', (value or '').strip()).upper()


def is_valid_rif(value):
    rif = normalize_rif(value)
    if not rif or len(rif) < 9 or len(rif) > 10:
        return False
    if rif[0] not in {'J', 'V', 'E'}:
        return False
    if not rif[1:].isdigit():
        return False
    return True


def is_valid_phone(value):
    phone = (value or '').strip()
    if not phone:
        return False
    return bool(re.fullmatch(r'\+\d{1,3}(?:[\s.-]?\d){7,14}', phone))


def is_valid_email(value):
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', (value or '').strip()))


def is_valid_password(value):
    password = (value or '').strip()
    if len(password) < 8:
        return False
    if re.search(r'\s', password):
        return False
    return True


def username_is_registered(value):
    username = (value or '').strip()
    if not username:
        return False

    normalized = username.lower()
    return bool(
        ProviderRegistration.query.filter(
            db.func.lower(ProviderRegistration.username) == normalized
        ).first()
        or User.query.filter(db.func.lower(User.code) == normalized).first()
    )


def provider_session_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('provider_logged_in') or not session.get('provider_username'):
            flash('Debes iniciar sesión como proveedor para acceder a este panel.', 'warning')
            return redirect(url_for('shopping.provider_login'))
        return view_func(*args, **kwargs)
    return wrapped


@shopping_bp.route('/provider_username_availability')
def provider_username_availability():
    username = (request.args.get('username') or '').strip()
    if not username:
        return {'available': False, 'message': 'Debes ingresar un usuario.'}

    available = not username_is_registered(username)
    return {
        'available': available,
        'message': 'Usuario disponible.' if available else 'Este nombre de usuario ya está registrado.'
    }


@shopping_bp.route('/product_order_details')
@login_required
def product_order_details():
    code = (request.args.get('code') or '').strip()
    selected_provider_code = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
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
        selected_provider_code=selected_provider_code,
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
@shopping_bp.route('/provider_selection')
@login_required
def provider_selection():
    code_provider = (request.args.get('code_provider') or '').strip()
    provider = service.get_provider_by_code(code_provider) if code_provider else None

    return render_template(
        'providers/provider_selection.html',
        provider=provider,
        selected_provider_code=code_provider,
    )


@shopping_bp.route('/provider_panel')
@provider_session_required
def provider_panel():
    provider_username = session.get('provider_username')
    provider_code = session.get('provider_code')
    return render_template(
        'providers/provider_panel.html',
        provider_username=provider_username,
        provider_code=provider_code,
    )


@shopping_bp.route('/provider_logout')
def provider_logout():
    session.pop('provider_logged_in', None)
    session.pop('provider_username', None)
    session.pop('provider_code', None)
    flash('Sesión de proveedor cerrada correctamente.', 'success')
    return redirect(url_for('shopping.provider_login'))


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


@shopping_bp.route('/provider_catalog_modal')
@provider_session_required
def provider_catalog_modal():
    return render_template('providers/provider_catalog_modal_products.html')

@shopping_bp.route('/provider_login', methods=['GET', 'POST'])
def provider_login():
    submitted_login_value = (
        request.form.get('login_value')
        or request.form.get('username')
        or request.form.get('email')
        or request.form.get('user')
        or ''
    ).strip()
    login_type = (request.form.get('login_type') or request.args.get('login_type') or '').strip().lower()
    if not login_type:
        login_type = 'correo' if '@' in submitted_login_value else 'usuario'
    password = (request.form.get('password') or '').strip()

    if request.method == 'POST':
        if not submitted_login_value or not password:
            return render_template(
                'providers/provider_login.html',
                login_type=login_type,
                login_value=submitted_login_value,
                password=password,
                show_demo_message=True,
                error_message='Ingresa tu usuario o correo y tu clave.',
            )

        searched_value = submitted_login_value.lower()

        registration = None
        if login_type == 'correo' or '@' in submitted_login_value:
            registration = ProviderRegistration.query.filter(
                db.func.lower(ProviderRegistration.email) == searched_value
            ).first()

        if registration is None:
            registration = ProviderRegistration.query.filter(
                db.func.lower(ProviderRegistration.username) == searched_value
            ).first()

        if registration is None:
            return render_template(
                'providers/provider_login.html',
                login_type=login_type,
                login_value=submitted_login_value,
                password=password,
                show_demo_message=True,
                error_message='No está registrado. Registre su cuenta antes de iniciar sesión.',
            )

        if registration.password != password:
            return render_template(
                'providers/provider_login.html',
                login_type=login_type,
                login_value=submitted_login_value,
                password=password,
                show_demo_message=True,
                error_message='Usuario o clave incorrectos.',
            )

        if registration.status == 'BLOCKED':
            return render_template(
                'providers/provider_login.html',
                login_type=login_type,
                login_value=submitted_login_value,
                password=password,
                show_demo_message=True,
                error_message='Esta cuenta está bloqueada o inactiva. Contacte a soporte para reactivarla.',
            )

        if registration.status == 'PENDING':
            return render_template(
                'providers/provider_register_status.html',
                registration=registration,
                status_label='PENDIENTE',
            )

        session['provider_logged_in'] = True
        session['provider_username'] = registration.username
        session['provider_code'] = registration.code

        return redirect(url_for('shopping.provider_panel'))

    return render_template('providers/provider_login.html', login_type=login_type, login_value=submitted_login_value, password='')


@shopping_bp.route('/provider_register_status')
def provider_register_status():
    username = (request.args.get('username') or '').strip()
    registration = None

    if username:
        registration = ProviderRegistration.query.filter(
            db.func.lower(ProviderRegistration.username) == username.lower()
        ).first()

    if registration is None:
        return redirect(url_for('shopping.provider_login'))

    return render_template(
        'providers/provider_register_status.html',
        registration=registration,
        status_label='PENDIENTE',
    )


@shopping_bp.route('/provider_approvals')
@login_required
def provider_approvals():
    registrations = ProviderRegistration.query.order_by(ProviderRegistration.registered_at.desc()).all()
    return render_template('providers/provider_approvals.html', registrations=registrations)


@shopping_bp.route('/provider_approval/<string:registration_code>', methods=['POST'])
@login_required
def provider_approval(registration_code):
    registration = ProviderRegistration.query.filter_by(code=registration_code).first_or_404()
    registration.status = 'APPROVED'
    db.session.commit()
    flash('El registro del proveedor fue aprobado correctamente.', 'success')
    return redirect(url_for('shopping.provider_approvals'))


@shopping_bp.route('/provider_block/<string:registration_code>', methods=['POST'])
@login_required
def provider_block(registration_code):
    registration = ProviderRegistration.query.filter_by(code=registration_code).first_or_404()
    registration.status = 'BLOCKED'
    db.session.commit()
    flash('El usuario proveedor fue bloqueado e inactivado correctamente.', 'warning')
    return redirect(url_for('shopping.provider_approvals'))


@shopping_bp.route('/provider_register', methods=['GET', 'POST'])
def provider_register():
    form_data = request.form.to_dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        company_tax_id = normalize_rif(form_data.get('company_tax_id'))
        company_name = normalize_upper(form_data.get('company_name'))
        address = normalize_upper(form_data.get('address'))
        salesperson_name = normalize_upper(form_data.get('salesperson_name'))
        salesperson_phone = normalize_upper(form_data.get('salesperson_phone'))
        company_email = (form_data.get('company_email') or '').strip()
        provider_username = (form_data.get('provider_username') or '').strip()
        provider_password = (form_data.get('provider_password') or '').strip()

        errors = []

        required_fields = {
            'RIF del proveedor': company_tax_id,
            'Nombre de la empresa': company_name,
            'Dirección': address,
            'Nombre del vendedor': salesperson_name,
            'Teléfono del contacto': salesperson_phone,
            'Correo electrónico de la empresa': company_email,
            'Usuario del proveedor': provider_username,
            'Clave del proveedor': provider_password,
        }

        for field_name, value in required_fields.items():
            if not value:
                errors.append(f'Falta completar: {field_name}.')

        if company_tax_id and not is_valid_rif(company_tax_id):
            errors.append('El RIF del proveedor es inválido. Debe comenzar con J, V o E y contener solo números después de la letra, sin espacios ni guiones.')

        if salesperson_phone and not is_valid_phone(salesperson_phone):
            errors.append('El teléfono del contacto contiene caracteres no válidos.')

        if company_email and not is_valid_email(company_email):
            errors.append('El correo electrónico ingresado no es válido.')

        if provider_username and (len(provider_username) < 4 or len(provider_username) > 50):
            errors.append('El usuario debe tener entre 4 y 50 caracteres.')

        if provider_username and username_is_registered(provider_username):
            errors.append('Ese nombre de usuario ya está registrado. Elige otro.')

        if provider_password and not is_valid_password(provider_password):
            errors.append('La clave debe tener al menos 8 caracteres y no puede contener espacios.')

        if errors:
            for message in errors:
                flash(message, 'error')
            return render_template('providers/provider_register.html', form_data=form_data, errors=errors)

        code = company_tax_id
        if ProviderRegistration.query.filter_by(code=code).first():
            errors.append('Ya existe una solicitud de registro con este RIF.')
            for message in errors:
                flash(message, 'error')
            return render_template('providers/provider_register.html', form_data=form_data, errors=errors)

        if ProviderRegistration.query.filter_by(username=provider_username).first():
            errors.append('Ese nombre de usuario ya está en uso.')
            for message in errors:
                flash(message, 'error')
            return render_template('providers/provider_register.html', form_data=form_data, errors=errors)

        registration = ProviderRegistration(
            code=code,
            description=company_name,
            address=address,
            provider_id=company_tax_id,
            email=company_email,
            phone=salesperson_phone,
            contact=salesperson_name,
            username=provider_username,
            password=provider_password,
            status='PENDING',
        )

        db.session.add(registration)
        db.session.commit()

        flash('Tu solicitud de proveedor fue enviada y queda pendiente de aprobación.', 'success')
        return redirect(url_for('shopping.provider_login'))

    return render_template('providers/provider_register.html', form_data=form_data, errors=[])


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
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_dir = 'desc' if request.args.get('sort_dir') == 'desc' else 'asc'
    provider_code = (request.args.get('provider_code') or request.args.get('code_provider') or '').strip()
    show_all_products = request.args.get('show_all_products') == '1'
    page = request.args.get('page', 1, type=int)
    products, total_products, total_pages, current_page, stock_stores = service.search_products(
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider_code=provider_code,
        show_all_products=show_all_products,
    )
    marks, departments = service.get_product_filter_options()

    return render_template(
        'shopping/partials/products_modal/modal.html',
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
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider_code=provider_code,
        show_all_products=show_all_products,
    )


@shopping_bp.route('/products_list')
@login_required
def products_list():
    query = (request.args.get('q') or '').strip()
    reference = (request.args.get('reference') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_dir = 'desc' if request.args.get('sort_dir') == 'desc' else 'asc'
    provider_code = (request.args.get('provider_code') or request.args.get('code_provider') or '').strip()
    show_all_products = request.args.get('show_all_products') == '1'
    page = request.args.get('page', 1, type=int)
    append = request.args.get('append') == '1'
    products, total_products, total_pages, current_page, stock_stores = service.search_products(
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        page=page,
        per_page=10,
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider_code=provider_code,
        show_all_products=show_all_products,
    )

    if append:
        return render_template(
            'shopping/partials/products_modal/rows.html',
            products=products,
            query=query,
            reference=reference,
            mark_codes=mark_codes,
            department_codes=department_codes,
            total_pages=total_pages,
            current_page=current_page,
            stock_stores=stock_stores,
            sort_by=sort_by,
            sort_dir=sort_dir,
            provider_code=provider_code,
            show_all_products=show_all_products,
        )

    return render_template(
        'shopping/partials/products_modal/list.html',
        products=products,
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
        stock_stores=stock_stores,
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider_code=provider_code,
        show_all_products=show_all_products,
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