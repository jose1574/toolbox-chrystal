import os
import re
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO

import xlsxwriter
from flask import (
    Response,
    abort,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    flash,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.reports.utils import render_pdf
from app.models import (
    Coin,
    Department,
    Mark,
    ProviderRegistration,
    PurchaseReviewList,
    PurchaseReviewListItem,
    PurchaseReviewNewProductItem,
    ShoppingCart,
    Unit,
    User,
)
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


def _provider_offer_session_key(provider_code):
    return f"provider_offer_items:{normalize_upper(provider_code)}"


def _get_provider_offer_items(provider_code):
    return session.get(_provider_offer_session_key(provider_code), [])


def _set_provider_offer_items(provider_code, items):
    session[_provider_offer_session_key(provider_code)] = items
    session.modified = True


def _provider_offer_coin_symbol():
    coin_code = session.get('provider_offer_coin_code') or service.get_default_provider_coin_code()
    coin = Coin.query.filter(Coin.code == coin_code, Coin.status == '01').first()
    return (coin.symbol or coin.code) if coin else coin_code


def _normalize_offer_item_id(value):
    return (value or '').strip()


PROVIDER_OFFER_IMAGE_MAX_BYTES = 5 * 1024 * 1024


def _provider_offer_image_dir():
    folder = os.path.join(current_app.instance_path, 'provider_offer_images')
    os.makedirs(folder, exist_ok=True)
    return folder


def _detect_provider_offer_image_mime(data):
    if not data or len(data) < 12:
        return None
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _provider_offer_image_token_prefix(provider_code):
    return f'{normalize_upper(provider_code)}_'


def _is_valid_provider_offer_image_token(provider_code, token):
    token = (token or '').strip()
    prefix = _provider_offer_image_token_prefix(provider_code)
    if not token.startswith(prefix):
        return False
    return bool(re.fullmatch(r'[0-9a-f]{32}', token[len(prefix):]))


def _provider_offer_image_paths(token):
    folder = _provider_offer_image_dir()
    return os.path.join(folder, token), os.path.join(folder, f'{token}.type')


def _save_provider_offer_image(provider_code, file_storage):
    if file_storage is None or not (file_storage.filename or '').strip():
        return None, None, None

    data = file_storage.read(PROVIDER_OFFER_IMAGE_MAX_BYTES + 1)
    if not data:
        return None, None, None
    if len(data) > PROVIDER_OFFER_IMAGE_MAX_BYTES:
        return None, None, 'La imagen no debe superar 5 MB.'

    mime = _detect_provider_offer_image_mime(data)
    if not mime:
        return None, None, 'La imagen debe ser JPG, PNG, WEBP o GIF.'

    token = f'{_provider_offer_image_token_prefix(provider_code)}{uuid.uuid4().hex}'
    image_path, type_path = _provider_offer_image_paths(token)
    with open(image_path, 'wb') as handle:
        handle.write(data)
    with open(type_path, 'w', encoding='utf-8') as handle:
        handle.write(mime)
    return token, mime, None


def _read_provider_offer_image(provider_code, token):
    if not _is_valid_provider_offer_image_token(provider_code, token):
        return None, None

    image_path, type_path = _provider_offer_image_paths(token)
    if not os.path.isfile(image_path):
        return None, None

    with open(image_path, 'rb') as handle:
        data = handle.read()

    mime = 'image/jpeg'
    if os.path.isfile(type_path):
        with open(type_path, 'r', encoding='utf-8') as handle:
            mime = (handle.read() or '').strip() or mime
    return data, mime


def _delete_provider_offer_image(provider_code, token):
    if not _is_valid_provider_offer_image_token(provider_code, token):
        return

    image_path, type_path = _provider_offer_image_paths(token)
    for path in (image_path, type_path):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _delete_provider_offer_item_image(provider_code, item):
    _delete_provider_offer_image(provider_code, (item or {}).get('image_token'))


def _render_new_product_modal_error(form_data, error_message):
    marks = Mark.query.order_by(Mark.description.asc(), Mark.code.asc()).all()
    departments = Department.query.order_by(Department.description.asc(), Department.code.asc()).all()
    units = Unit.query.order_by(Unit.description.asc(), Unit.code.asc()).all()
    response = make_response(
        render_template(
            'providers/new_product_modal.html',
            marks=marks,
            departments=departments,
            units=units,
            form_data=form_data,
            error_message=error_message,
        ),
        422,
    )
    response.headers['HX-Retarget'] = '#provider-new-product-modal-container'
    response.headers['HX-Reswap'] = 'innerHTML'
    return response


def _find_offer_item(items, item_id=None, product_code=None):
    normalized_item_id = _normalize_offer_item_id(item_id)
    normalized_product_code = normalize_upper(product_code)

    for item in items:
        current_item_id = _normalize_offer_item_id(item.get('item_id'))
        if normalized_item_id and current_item_id == normalized_item_id:
            return item
        if not normalized_item_id and normalized_product_code and normalize_upper(item.get('code')) == normalized_product_code:
            return item
    return None


def _build_provider_review_reference(provider_code):
    normalized_provider_code = normalize_upper(provider_code) or 'PROVIDER'
    timestamp_suffix = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f"PRV-{normalized_provider_code}-{timestamp_suffix}"


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
    selected_review_item = None
    if any(
        request.args.get(param)
        for param in ('review_quantity', 'review_unit', 'review_unit_price', 'review_subtotal', 'review_status_label', 'review_note', 'review_rejected_reason')
    ):
        selected_review_item = {
            'item_type': (request.args.get('review_item_type') or 'catalog').strip() or 'catalog',
            'quantity': request.args.get('review_quantity', type=float),
            'unit': (request.args.get('review_unit') or '').strip(),
            'unit_price': request.args.get('review_unit_price', type=float),
            'subtotal': request.args.get('review_subtotal', type=float),
            'status_label': (request.args.get('review_status_label') or '').strip(),
            'note': (request.args.get('review_note') or '').strip(),
            'rejected_reason': (request.args.get('review_rejected_reason') or '').strip(),
        }
    return render_template(
        'shopping/panel_shopping/product_order_details.html',
        product=product,
        inventory_params=inventory_params,
        shopping_params=shopping_params,
        purchase_history=purchase_history,
        selected_review_item=selected_review_item,
        selected_provider_code=selected_provider_code,
        include_sales_chart_oob=True,
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
    return render_template(
        'shopping/panel_shopping/product_sales_chart.html',
        sales_context=sales_context,
        compact=request.args.get('compact') == '1',
    )


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

    context['inventory_total_stock'] = service.get_product_total_inventory(context['product'].code)
    return render_template('shopping/panel_shopping/product_shopping_params.html', **context)


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

    return render_template(
        'shopping/panel_shopping/product_inventory_params.html',
        inventory_params=context['inventory_params'],
    )



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


@shopping_bp.route('/test')
def test():
    return render_template('shopping/test.html')

@shopping_bp.route('/offer_list_provider')
@login_required
def offer_list_provider():
    code_provider = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
    provider = service.get_provider_by_code(code_provider) if code_provider else None

    if code_provider and provider is None:
        flash(f'No se encontró un proveedor con el código {code_provider}.', 'error')



    review_lists = []
    if provider:
        review_lists = [
            review_list
            for review_list in service.get_provider_review_lists(
                provider.code,
                coin_symbol=_provider_offer_coin_symbol(),
            )
            if review_list.get('status') == 'SUBMITTED'
        ]
    if not review_lists:
        flash('Este proveedor no tiene listas pendientes por revisar. Se abrió la compra directa.', 'info')
        order_url = url_for('shopping.order', code_provider=provider.code if provider else code_provider)
        if request.headers.get('HX-Request') == 'true':
            response = make_response('', 200)
            response.headers['HX-Redirect'] = order_url
            return response
        return redirect(order_url)
    
    return render_template(
        'shopping/offer_list_provider.html',
        provider=provider,
        selected_provider_code=provider.code if provider else code_provider,
        review_lists=review_lists,
    )


# @shopping_bp.route('/offer_list_provider/list')
# @login_required
# def offer_list_provider_list():
#     code_provider = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
#     provider = service.get_provider_by_code(code_provider) if code_provider else None

#     review_lists = []
#     if provider:
#         review_lists = [
#             review_list
#             for review_list in service.get_provider_review_lists(
#                 provider.code,
#                 coin_symbol=_provider_offer_coin_symbol(),
#             )
#             if review_list.get('status') == 'SUBMITTED'
#         ]

#     return render_template(
#         'shopping/partials/offer_list_provider_list.html',
#         provider=provider,
#         selected_provider_code=provider.code if provider else code_provider,
#         review_lists=review_lists,
#     )

    # if not code_provider:
    #     return render_template(
    #         'shopping/offer_list_provider.html',
    #         provider=None,
    #         selected_provider_code='',
    #         review_lists=[],
    #         selected_review_list=None,
    #         offer_lists_content_endpoint='shopping.offer_list_provider_content',
    #         offer_list_pdf_endpoint='shopping.offer_list_provider_pdf_report',
    #         offer_list_excel_endpoint='shopping.offer_list_provider_excel_report',
    #         provider_code_for_lists='',
    #     )

    # if provider is None:
    #     flash(f'No se encontró un proveedor con el código {code_provider}.', 'error')
    #     return render_template(
    #         'shopping/offer_list_provider.html',
    #         provider=None,
    #         selected_provider_code=code_provider,
    #         review_lists=[],
    #         selected_review_list=None,
    #         offer_lists_content_endpoint='shopping.offer_list_provider_content',
    #         offer_list_pdf_endpoint='shopping.offer_list_provider_pdf_report',
    #         offer_list_excel_endpoint='shopping.offer_list_provider_excel_report',
    #         provider_code_for_lists=code_provider,
    #     )

    # review_lists_context = service.get_provider_review_lists_context(
    #     provider.code,
    #     selected_review_list_correlative=review_list_correlative,
    #     coin_symbol=_provider_offer_coin_symbol(),
    # )
    # return render_template(
    #     'shopping/offer_list_provider.html',
    #     provider=provider,
    #     selected_provider_code=provider.code,
    #     offer_lists_content_endpoint='shopping.offer_list_provider_content',
    #     offer_list_pdf_endpoint='shopping.offer_list_provider_pdf_report',
    #     offer_list_excel_endpoint='shopping.offer_list_provider_excel_report',
    #     provider_code_for_lists=provider.code,
    #     **review_lists_context,
    # )


@shopping_bp.route('/provider_panel')
@provider_session_required
def provider_panel():
    provider_username = session.get('provider_username')
    provider_code = session.get('provider_code')
    coins = Coin.query.filter(Coin.status == '01').order_by(Coin.description.asc(), Coin.code.asc()).all()
    requested_coin_code = (request.args.get('coin_code') or '').strip()
    default_coin_code = service.get_default_provider_coin_code()

    selected_coin_code = requested_coin_code if requested_coin_code else default_coin_code
    available_coin_codes = {coin.code for coin in coins}
    if selected_coin_code not in available_coin_codes:
        selected_coin_code = next(
            (coin.code for coin in coins if (coin.symbol or '').upper() == 'USD'),
            coins[0].code if coins else '',
        )

    selected_coin_symbol = next(
        (coin.symbol or coin.code for coin in coins if coin.code == selected_coin_code),
        selected_coin_code,
    )
    session['provider_offer_coin_code'] = selected_coin_code
    offer_items = _get_provider_offer_items(provider_code)
    offer_context = service.build_provider_offer_context(offer_items, selected_coin_symbol)

    return render_template(
        'providers/provider_panel.html',
        provider_username=provider_username,
        provider_code=provider_code,
        coins=coins,
        selected_coin_code=selected_coin_code,
        selected_coin_symbol=selected_coin_symbol,
        offer_context=offer_context,
    )


@shopping_bp.route('/provider_new_product_modal')
@provider_session_required
def provider_new_product_modal():
    marks = Mark.query.order_by(Mark.description.asc(), Mark.code.asc()).all()
    departments = Department.query.order_by(Department.description.asc(), Department.code.asc()).all()
    units = Unit.query.order_by(Unit.description.asc(), Unit.code.asc()).all()
    return render_template(
        'providers/new_product_modal.html',
        marks=marks,
        departments=departments,
        units=units,
        form_data={},
        error_message='',
    )


@shopping_bp.route('/provider_offer_lists_modal')
@provider_session_required
def provider_offer_lists_modal():
    provider_code = session.get('provider_code', '')
    review_list_correlative = request.args.get('review_list_correlative')
    review_lists_context = service.get_provider_review_lists_context(
        provider_code,
        selected_review_list_correlative=review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    return render_template(
        'providers/partials/offer_lists_modal.html',
        provider_username=session.get('provider_username'),
        **review_lists_context,
    )


@shopping_bp.route('/provider_offer_lists_content')
@provider_session_required
def provider_offer_lists_content():
    provider_code = session.get('provider_code', '')
    review_list_correlative = request.args.get('review_list_correlative')
    review_lists_context = service.get_provider_review_lists_context(
        provider_code,
        selected_review_list_correlative=review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    return render_template('providers/partials/offer_lists_content.html', **review_lists_context)


@shopping_bp.route('/offer_list_provider/content')
@login_required
def offer_list_provider_content():
    provider_code = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
    review_list_correlative = request.args.get('review_list_correlative')
    review_lists_context = service.get_provider_review_lists_context(
        provider_code,
        selected_review_list_correlative=review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    return render_template(
        'providers/partials/offer_lists_content.html',
        offer_lists_content_endpoint='shopping.offer_list_provider_content',
        offer_list_pdf_endpoint='shopping.offer_list_provider_pdf_report',
        offer_list_excel_endpoint='shopping.offer_list_provider_excel_report',
        provider_code_for_lists=provider_code,
        **review_lists_context,
    )


@shopping_bp.route('/provider_offer_lists/<int:review_list_correlative>/pdf')
@provider_session_required
def provider_offer_list_pdf_report(review_list_correlative):
    provider_code = session.get('provider_code', '')
    provider_username = session.get('provider_username')
    provider_registration = ProviderRegistration.query.filter_by(code=provider_code).first()
    review_list = service.get_provider_review_list_detail_context(
        provider_code,
        review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    if review_list is None:
        flash('No se encontro la lista de oferta solicitada.', 'warning')
        return redirect(url_for('shopping.provider_panel'))

    review_list = service.attach_review_list_pdf_images(review_list)
    safe_reference = re.sub(r'[^A-Za-z0-9_-]+', '_', review_list['reference']).strip('_') or f'lista_{review_list_correlative}'
    pdf = render_pdf(
        'providers/reports/provider_offer_list_pdf.html',
        {
            'review_list': review_list,
            'provider_company_name': provider_registration.description if provider_registration else None,
            'provider_username': provider_username,
            'provider_code': provider_code,
            'generated_at': datetime.now(),
        },
        paper_format='Letter',
        orientation='Portrait',
        extra_options={
            'margin-top': '0.35in',
            'margin-right': '0.35in',
            'margin-bottom': '0.35in',
            'margin-left': '0.35in',
        },
    )
    return Response(
        pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename={safe_reference}.pdf'},
    )


@shopping_bp.route('/provider_offer_lists/<int:review_list_correlative>/excel')
@provider_session_required
def provider_offer_list_excel_report(review_list_correlative):
    provider_code = session.get('provider_code', '')
    provider_username = session.get('provider_username')
    review_list = service.get_provider_review_list_detail_context(
        provider_code,
        review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    if review_list is None:
        flash('No se encontro la lista de oferta solicitada.', 'warning')
        return redirect(url_for('shopping.provider_panel'))

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Oferta')

    worksheet.set_paper(1)
    worksheet.set_portrait()
    worksheet.fit_to_pages(1, 0)
    worksheet.repeat_rows(0, 5)
    worksheet.set_margins(0.3, 0.3, 0.4, 0.4)

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'align': 'left',
        'valign': 'vcenter',
    })
    meta_label_format = workbook.add_format({
        'bold': True,
        'font_size': 10,
        'font_color': '#44546A',
    })
    meta_value_format = workbook.add_format({
        'font_size': 10,
    })
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D9E2F3',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })
    text_format = workbook.add_format({
        'border': 1,
        'valign': 'top',
        'text_wrap': True,
    })
    amount_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'top',
        'num_format': '#,##0.00',
    })
    total_label_format = workbook.add_format({
        'bold': True,
        'border': 1,
        'align': 'right',
        'bg_color': '#EDEDED',
    })
    total_amount_format = workbook.add_format({
        'bold': True,
        'border': 1,
        'align': 'right',
        'bg_color': '#EDEDED',
        'num_format': '#,##0.00',
    })

    worksheet.merge_range('A1:F1', f"Detalle de oferta {review_list['reference']}", title_format)
    worksheet.write('A2', 'Proveedor', meta_label_format)
    worksheet.write('B2', provider_username or provider_code or '-', meta_value_format)
    worksheet.write('D2', 'Codigo', meta_label_format)
    worksheet.write('E2', provider_code or '-', meta_value_format)
    worksheet.write('A3', 'Estado', meta_label_format)
    worksheet.write('B3', review_list['status_label'], meta_value_format)
    worksheet.write('D3', 'Enviada', meta_label_format)
    worksheet.write('E3', review_list['submitted_at'].strftime('%d/%m/%Y %H:%M') if review_list['submitted_at'] else '-', meta_value_format)
    worksheet.write('A4', 'Generado', meta_label_format)
    worksheet.write('B4', datetime.now().strftime('%d/%m/%Y %H:%M'), meta_value_format)
    worksheet.write('D4', 'Moneda', meta_label_format)
    worksheet.write('E4', review_list['coin_symbol'], meta_value_format)

    columns = ['Producto', 'Codigo / detalle', 'Cantidad', 'Unidad', 'Precio unitario', 'Subtotal', 'Estado']
    for col_idx, title in enumerate(columns):
        worksheet.write(5, col_idx, title, header_format)

    worksheet.set_column('A:A', 34)
    worksheet.set_column('B:B', 28)
    worksheet.set_column('C:C', 12)
    worksheet.set_column('D:D', 14)
    worksheet.set_column('E:F', 15)
    worksheet.set_column('G:G', 14)

    row_idx = 6
    for item in review_list['items']:
        detail_parts = []
        if item['item_type'] == 'new_product':
            detail_parts.append('Nuevo producto')
            if item.get('main_code'):
                detail_parts.append(f"Codigo: {item['main_code']}")
            if item.get('mark_name'):
                detail_parts.append(item['mark_name'])
            if item.get('department_name'):
                detail_parts.append(item['department_name'])
        else:
            detail_parts.append(f"SKU: {item['code']}")
        if item.get('note'):
            detail_parts.append(f"Nota: {item['note']}")
        if item.get('rejected_reason'):
            detail_parts.append(f"Motivo: {item['rejected_reason']}")

        worksheet.write(row_idx, 0, item['name'], text_format)
        worksheet.write(row_idx, 1, ' | '.join(detail_parts), text_format)
        worksheet.write_number(row_idx, 2, float(item['quantity'] or 0), amount_format)
        worksheet.write(row_idx, 3, item['unit'], text_format)
        worksheet.write_number(row_idx, 4, float(item['unit_price'] or 0), amount_format)
        worksheet.write_number(row_idx, 5, float(item['subtotal'] or 0), amount_format)
        worksheet.write(row_idx, 6, item['status_label'], text_format)
        row_idx += 1

    worksheet.merge_range(row_idx, 0, row_idx, 4, 'Total', total_label_format)
    worksheet.write_number(row_idx, 5, float(review_list['total_amount'] or 0), total_amount_format)
    worksheet.write(row_idx, 6, review_list['coin_symbol'], total_label_format)

    workbook.close()
    output.seek(0)

    safe_reference = re.sub(r'[^A-Za-z0-9_-]+', '_', review_list['reference']).strip('_') or f'lista_{review_list_correlative}'
    return send_file(
        output,
        as_attachment=True,
        download_name=f'{safe_reference}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@shopping_bp.route('/offer_list_provider/<int:review_list_correlative>/pdf')
@login_required
def offer_list_provider_pdf_report(review_list_correlative):
    provider_code = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
    provider = service.get_provider_by_code(provider_code) if provider_code else None
    provider_registration = ProviderRegistration.query.filter_by(code=provider_code).first() if provider_code else None
    review_list = service.get_provider_review_list_detail_context(
        provider_code,
        review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    if review_list is None:
        flash('No se encontro la lista de oferta solicitada.', 'warning')
        return redirect(url_for('shopping.offer_list_provider', code_provider=provider_code))

    review_list = service.attach_review_list_pdf_images(review_list)
    safe_reference = re.sub(r'[^A-Za-z0-9_-]+', '_', review_list['reference']).strip('_') or f'lista_{review_list_correlative}'
    pdf = render_pdf(
        'providers/reports/provider_offer_list_pdf.html',
        {
            'review_list': review_list,
            'provider_company_name': provider_registration.description if provider_registration else (provider.description if provider else None),
            'provider_username': provider_registration.username if provider_registration else None,
            'provider_code': provider_code,
            'generated_at': datetime.now(),
        },
        paper_format='Letter',
        orientation='Portrait',
        extra_options={
            'margin-top': '0.35in',
            'margin-right': '0.35in',
            'margin-bottom': '0.35in',
            'margin-left': '0.35in',
        },
    )
    return Response(
        pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename={safe_reference}.pdf'},
    )


@shopping_bp.route('/offer_list_provider/<int:review_list_correlative>/excel')
@login_required
def offer_list_provider_excel_report(review_list_correlative):
    provider_code = (request.args.get('code_provider') or request.args.get('provider_code') or '').strip()
    provider = service.get_provider_by_code(provider_code) if provider_code else None
    provider_registration = ProviderRegistration.query.filter_by(code=provider_code).first() if provider_code else None
    review_list = service.get_provider_review_list_detail_context(
        provider_code,
        review_list_correlative,
        coin_symbol=_provider_offer_coin_symbol(),
    )
    if review_list is None:
        flash('No se encontro la lista de oferta solicitada.', 'warning')
        return redirect(url_for('shopping.offer_list_provider', code_provider=provider_code))

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Oferta')

    worksheet.set_paper(1)
    worksheet.set_portrait()
    worksheet.fit_to_pages(1, 0)
    worksheet.repeat_rows(0, 5)
    worksheet.set_margins(0.3, 0.3, 0.4, 0.4)

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'align': 'left',
        'valign': 'vcenter',
    })
    meta_label_format = workbook.add_format({
        'bold': True,
        'font_size': 10,
        'font_color': '#44546A',
    })
    meta_value_format = workbook.add_format({
        'font_size': 10,
    })
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D9E2F3',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })
    text_format = workbook.add_format({
        'border': 1,
        'valign': 'top',
        'text_wrap': True,
    })
    amount_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'top',
        'num_format': '#,##0.00',
    })
    total_label_format = workbook.add_format({
        'bold': True,
        'border': 1,
        'align': 'right',
        'bg_color': '#EDEDED',
    })
    total_amount_format = workbook.add_format({
        'bold': True,
        'border': 1,
        'align': 'right',
        'bg_color': '#EDEDED',
        'num_format': '#,##0.00',
    })

    provider_display_name = (
        provider_registration.description if provider_registration else (provider.description if provider else None)
    ) or provider_code or '-'

    worksheet.merge_range('A1:F1', f"Detalle de oferta {review_list['reference']}", title_format)
    worksheet.write('A2', 'Proveedor', meta_label_format)
    worksheet.write('B2', provider_display_name, meta_value_format)
    worksheet.write('D2', 'Codigo', meta_label_format)
    worksheet.write('E2', provider_code or '-', meta_value_format)
    worksheet.write('A3', 'Estado', meta_label_format)
    worksheet.write('B3', review_list['status_label'], meta_value_format)
    worksheet.write('D3', 'Enviada', meta_label_format)
    worksheet.write('E3', review_list['submitted_at'].strftime('%d/%m/%Y %H:%M') if review_list['submitted_at'] else '-', meta_value_format)
    worksheet.write('A4', 'Generado', meta_label_format)
    worksheet.write('B4', datetime.now().strftime('%d/%m/%Y %H:%M'), meta_value_format)
    worksheet.write('D4', 'Moneda', meta_label_format)
    worksheet.write('E4', review_list['coin_symbol'], meta_value_format)

    columns = ['Producto', 'Codigo / detalle', 'Cantidad', 'Unidad', 'Precio unitario', 'Subtotal', 'Estado']
    for col_idx, title in enumerate(columns):
        worksheet.write(5, col_idx, title, header_format)

    worksheet.set_column('A:A', 34)
    worksheet.set_column('B:B', 28)
    worksheet.set_column('C:C', 12)
    worksheet.set_column('D:D', 14)
    worksheet.set_column('E:F', 15)
    worksheet.set_column('G:G', 14)

    row_idx = 6
    for item in review_list['items']:
        detail_parts = []
        if item['item_type'] == 'new_product':
            detail_parts.append('Nuevo producto')
            if item.get('main_code'):
                detail_parts.append(f"Codigo: {item['main_code']}")
            if item.get('mark_name'):
                detail_parts.append(item['mark_name'])
            if item.get('department_name'):
                detail_parts.append(item['department_name'])
        else:
            detail_parts.append(f"SKU: {item['code']}")
        if item.get('note'):
            detail_parts.append(f"Nota: {item['note']}")
        if item.get('rejected_reason'):
            detail_parts.append(f"Motivo: {item['rejected_reason']}")

        worksheet.write(row_idx, 0, item['name'], text_format)
        worksheet.write(row_idx, 1, ' | '.join(detail_parts), text_format)
        worksheet.write_number(row_idx, 2, float(item['quantity'] or 0), amount_format)
        worksheet.write(row_idx, 3, item['unit'], text_format)
        worksheet.write_number(row_idx, 4, float(item['unit_price'] or 0), amount_format)
        worksheet.write_number(row_idx, 5, float(item['subtotal'] or 0), amount_format)
        worksheet.write(row_idx, 6, item['status_label'], text_format)
        row_idx += 1

    worksheet.merge_range(row_idx, 0, row_idx, 4, 'Total', total_label_format)
    worksheet.write_number(row_idx, 5, float(review_list['total_amount'] or 0), total_amount_format)
    worksheet.write(row_idx, 6, review_list['coin_symbol'], total_label_format)

    workbook.close()
    output.seek(0)

    safe_reference = re.sub(r'[^A-Za-z0-9_-]+', '_', review_list['reference']).strip('_') or f'lista_{review_list_correlative}'
    return send_file(
        output,
        as_attachment=True,
        download_name=f'{safe_reference}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@shopping_bp.route('/provider_offer_items/add_new_product', methods=['POST'])
@provider_session_required
def provider_offer_items_add_new_product():
    provider_code = session.get('provider_code', '')
    offer_items = _get_provider_offer_items(provider_code)

    proposed_description = (request.form.get('proposed_description') or '').strip()
    proposed_main_code = normalize_upper(request.form.get('proposed_main_code'))
    proposed_reference = (request.form.get('proposed_reference') or '').strip()
    proposed_mark_code = normalize_upper(request.form.get('proposed_mark_code'))
    proposed_department_code = normalize_upper(request.form.get('proposed_department_code'))
    proposed_unit_code = normalize_upper(request.form.get('proposed_unit_code'))
    provider_note = (request.form.get('provider_note') or '').strip()
    raw_requested_amount = (request.form.get('requested_amount') or '').strip()
    raw_unitary_cost = (request.form.get('unitary_cost') or '').strip()

    form_data = {
        'proposed_description': proposed_description,
        'proposed_main_code': proposed_main_code,
        'proposed_reference': proposed_reference,
        'proposed_mark_code': proposed_mark_code,
        'proposed_department_code': proposed_department_code,
        'proposed_unit_code': proposed_unit_code,
        'provider_note': provider_note,
        'requested_amount': raw_requested_amount,
        'unitary_cost': raw_unitary_cost,
        'image_token': '',
    }

    existing_image_token = (request.form.get('existing_image_token') or '').strip()
    image_token, image_type, image_error = _save_provider_offer_image(
        provider_code,
        request.files.get('proposed_image'),
    )
    if image_error:
        if _is_valid_provider_offer_image_token(provider_code, existing_image_token):
            form_data['image_token'] = existing_image_token
        return _render_new_product_modal_error(form_data, image_error)

    if image_token:
        _delete_provider_offer_image(provider_code, existing_image_token)
        form_data['image_token'] = image_token
    elif _read_provider_offer_image(provider_code, existing_image_token)[0]:
        image_token = existing_image_token
        form_data['image_token'] = existing_image_token

    try:
        requested_amount = max(float(raw_requested_amount), 0)
    except ValueError:
        requested_amount = -1

    try:
        unitary_cost = max(float(raw_unitary_cost), 0)
    except ValueError:
        unitary_cost = -1

    if not proposed_description or not proposed_main_code or requested_amount <= 0 or unitary_cost < 0:
        return _render_new_product_modal_error(
            form_data,
            'Completa el código principal, la descripción, una cantidad válida y un precio unitario válido.',
        )

    selected_mark = Mark.query.filter(Mark.code == proposed_mark_code).first() if proposed_mark_code else None
    selected_department = Department.query.filter(Department.code == proposed_department_code).first() if proposed_department_code else None
    selected_unit = Unit.query.filter(Unit.code == proposed_unit_code).first() if proposed_unit_code else None

    offer_items.append({
        'item_id': f"NEW-{uuid.uuid4().hex[:8]}",
        'item_type': 'new_product',
        'code': proposed_main_code,
        'name': proposed_description,
        'reference': proposed_reference or '-',
        'quantity': requested_amount,
        'main_quantity': requested_amount,
        'unit_price': unitary_cost,
        'unit': (selected_unit.description if selected_unit else proposed_unit_code) or 'UND',
        'unit_code': proposed_unit_code or '',
        'unit_options': [],
        'conversion_factor': 1,
        'unit_type': 0,
        'discount_percent': 0,
        'note': provider_note,
        'proposed_main_code': proposed_main_code,
        'mark_code': selected_mark.code if selected_mark else '',
        'mark_name': selected_mark.description if selected_mark else '',
        'department_code': selected_department.code if selected_department else '',
        'department_name': selected_department.description if selected_department else '',
        'image_token': image_token or '',
        'image_type': image_type or '',
    })

    _set_provider_offer_items(provider_code, offer_items)
    offer_context = service.build_provider_offer_context(offer_items, _provider_offer_coin_symbol())
    return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)


@shopping_bp.route('/provider_offer_items/temp_image/<token>')
@provider_session_required
def provider_offer_temp_image(token):
    provider_code = session.get('provider_code', '')
    image_bytes, image_type = _read_provider_offer_image(provider_code, token)
    if not image_bytes:
        abort(404)
    return send_file(BytesIO(image_bytes), mimetype=image_type or 'image/jpeg')


@shopping_bp.route('/provider_new_product_image/<int:correlative>')
def provider_new_product_image(correlative):
    item = PurchaseReviewNewProductItem.query.filter_by(correlative=correlative).first()
    if item is None or not item.proposed_image:
        abort(404)

    if session.get('provider_logged_in'):
        if normalize_upper(item.review_list.provider_code) != normalize_upper(session.get('provider_code')):
            abort(403)
    elif not current_user.is_authenticated:
        abort(401)

    return send_file(
        BytesIO(bytes(item.proposed_image)),
        mimetype=item.proposed_image_type or 'image/jpeg',
    )


@shopping_bp.route('/provider_offer_items/submit_review', methods=['POST'])
@provider_session_required
def provider_offer_items_submit_review():
    provider_code = session.get('provider_code', '')
    offer_items = _get_provider_offer_items(provider_code)
    provider_description = (request.form.get('provider_description') or '').strip()

    if not offer_items:
        flash('Agrega al menos un producto antes de enviar a revisión.', 'warning')
        return redirect(url_for('shopping.provider_panel'))

    review_list = PurchaseReviewList(
        list_type='PROVIDER_SUBMISSION',
        provider_code=provider_code or None,
        created_by=None,
        buyer_code=None,
        reference=_build_provider_review_reference(provider_code),
        status='SUBMITTED',
        provider_notes=provider_description or None,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(review_list)
    db.session.flush()

    for item in offer_items:
        item_type = item.get('item_type') or 'catalog'
        if item_type == 'new_product':
            image_bytes, image_type = _read_provider_offer_image(provider_code, item.get('image_token'))
            db.session.add(
                PurchaseReviewNewProductItem(
                    main_correlative=review_list.correlative,
                    proposed_description=item.get('name') or '',
                    proposed_main_code=item.get('proposed_main_code') or item.get('code') or None,
                    proposed_reference=(item.get('reference') or '').strip() or None,
                    proposed_mark_code=item.get('mark_code') or None,
                    proposed_department_code=item.get('department_code') or None,
                    proposed_unit_code=item.get('unit_code') or None,
                    requested_amount=float(item.get('quantity') or 0),
                    unitary_cost=float(item.get('unit_price') or 0),
                    provider_note=(item.get('note') or '').strip() or None,
                    status='PENDING',
                    proposed_image=image_bytes,
                    proposed_image_type=image_type if image_bytes else None,
                )
            )
            continue

        product_code = normalize_upper(item.get('code'))
        if not product_code:
            continue

        unit_correlative = item.get('unit_correlative')
        db.session.add(
            PurchaseReviewListItem(
                main_correlative=review_list.correlative,
                product_code=product_code,
                unit=int(unit_correlative) if str(unit_correlative or '').strip() else None,
                requested_amount=float(item.get('quantity') or 0),
                unitary_cost=float(item.get('unit_price') or 0),
                status='PENDING',
                note=(item.get('note') or '').strip() or None,
            )
        )

    db.session.commit()
    for item in offer_items:
        _delete_provider_offer_item_image(provider_code, item)
    _set_provider_offer_items(provider_code, [])
    flash(f'Se envió la oferta a revisión con la referencia {review_list.reference}.', 'success')
    return redirect(url_for('shopping.provider_panel'))


@shopping_bp.route('/provider_offer_items/add', methods=['POST'])
@provider_session_required
def provider_offer_items_add():
    provider_code = session.get('provider_code', '')
    selected_codes = request.form.getlist('selected_product_codes')
    selected_unit_correlatives = request.form.getlist('selected_product_units')
    selected_quantities = request.form.getlist('selected_product_quantities')
    if not selected_codes:
        item_id = _normalize_offer_item_id(request.form.get('item_id'))
        product_code = normalize_upper(request.form.get('product_code'))
        raw_quantity = (request.form.get('quantity') or '').strip()
        raw_unit_price = (request.form.get('unit_price') or '').strip()
        raw_discount_percent = (request.form.get('discount_percent') or '').strip()
        offer_items = _get_provider_offer_items(provider_code)

        if item_id or product_code:
            try:
                quantity = max(float(raw_quantity), 0) if raw_quantity else None
            except ValueError:
                quantity = None

            try:
                unit_price = max(float(raw_unit_price), 0) if raw_unit_price else None
            except ValueError:
                unit_price = None

            try:
                discount_percent = min(max(float(raw_discount_percent), 0), 100) if raw_discount_percent else None
            except ValueError:
                discount_percent = None

            item = _find_offer_item(offer_items, item_id=item_id, product_code=product_code)
            if item:
                if quantity is not None:
                    units_per_main = service._units_per_main(
                        item.get('conversion_factor'), item.get('unit_type')
                    )
                    item['quantity'] = quantity
                    item['main_quantity'] = quantity * units_per_main if units_per_main else quantity

                if unit_price is not None:
                    item['unit_price'] = unit_price

                if discount_percent is not None:
                    item['discount_percent'] = discount_percent

            if item and (quantity is not None or unit_price is not None or discount_percent is not None):
                _set_provider_offer_items(provider_code, offer_items)

        offer_context = service.build_provider_offer_context(
            offer_items, _provider_offer_coin_symbol()
        )
        return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)

    existing_items = _get_provider_offer_items(provider_code)
    existing_by_code = {normalize_upper(item.get('code')): item for item in existing_items}
    requested_quantities_by_code = {}
    for index, product_code in enumerate(selected_codes):
        normalized_code = normalize_upper(product_code)
        if index >= len(selected_quantities):
            continue
        raw_quantity = (selected_quantities[index] or '').strip().replace(',', '.')
        if not raw_quantity:
            continue
        try:
            requested_quantities_by_code[normalized_code] = float(raw_quantity)
        except ValueError:
            continue

    products = service.get_provider_offer_products(provider_code, selected_codes, selected_unit_correlatives)
    for product in products:
        product_code = normalize_upper(product.get('code'))
        if product_code in existing_by_code:
            continue

        selected_unit = next(
            (
                option for option in (product.get('unit_options') or [])
                if str(option.get('correlative') or '') == str(product.get('unit_correlative') or '')
                or (
                    not product.get('unit_correlative') and
                    normalize_upper(option.get('code')) == normalize_upper(product.get('unit_code'))
                )
            ),
            None,
        )
        if selected_unit is None:
            selected_unit = next(
                (
                    option for option in (product.get('unit_options') or [])
                    if normalize_upper(option.get('code')) == normalize_upper(product.get('unit_code'))
                ),
                None,
            )
        selected_unit_correlative = product.get('unit_correlative')
        selected_unit_from_db = service.get_provider_product_unit_by_correlative(selected_unit_correlative)
        if selected_unit_from_db:
            selected_unit = selected_unit_from_db
        conversion_factor = float((selected_unit or {}).get('conversion_factor') or product.get('conversion_factor') or 1)
        unit_type = int((selected_unit or {}).get('unit_type') or product.get('unit_type') or 0)
        units_per_main = service._units_per_main(conversion_factor, unit_type)
        requested_quantity = requested_quantities_by_code.get(product_code)
        if requested_quantity is not None:
            quantity = max(float(requested_quantity), 0)
            main_quantity = quantity * units_per_main if units_per_main else quantity
        else:
            base_quantity = float(product.get('suggested_quantity', 0) or 0)
            quantity = base_quantity / units_per_main if units_per_main else base_quantity
            main_quantity = base_quantity
        unit_price = float(product.get('last_provider_cost') or 0)
        source_cost_unit = next(
            (
                option for option in (product.get('unit_options') or [])
                if str(option.get('correlative') or '') == str(product.get('last_provider_cost_unit_correlative') or '')
            ),
            None,
        )
        source_cost_unit_from_db = service.get_provider_product_unit_by_correlative(
            product.get('last_provider_cost_unit_correlative')
        )
        if source_cost_unit_from_db:
            source_cost_unit = source_cost_unit_from_db
        if source_cost_unit and selected_unit:
            unit_price = service.convert_unit_price(
                unit_price,
                float((source_cost_unit or {}).get('conversion_factor') or 1),
                int((source_cost_unit or {}).get('unit_type') or 0),
                float((selected_unit or {}).get('conversion_factor') or 1),
                int((selected_unit or {}).get('unit_type') or 0),
            )

        existing_items.append({
            'item_id': f"CAT-{product_code}",
            'item_type': 'catalog',
            'code': product.get('code'),
            'name': product.get('name'),
            'reference': product.get('reference'),
            'quantity': quantity,
            'main_quantity': main_quantity,
            'unit_price': unit_price,
            'unit': product.get('unit') or 'UND',
            'unit_code': product.get('unit_code') or '',
            'unit_correlative': product.get('unit_correlative'),
            'unit_options': product.get('unit_options') or [],
            'conversion_factor': conversion_factor,
            'unit_type': unit_type,
            'discount_percent': 0,
        })

    _set_provider_offer_items(provider_code, existing_items)
    offer_context = service.build_provider_offer_context(existing_items, _provider_offer_coin_symbol())
    return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)


@shopping_bp.route('/provider_offer_items/unit', methods=['POST'])
@provider_session_required
def provider_offer_items_unit():
    provider_code = session.get('provider_code', '')
    item_id = _normalize_offer_item_id(request.form.get('item_id'))
    product_code = normalize_upper(request.form.get('product_code'))
    unit_code = normalize_upper(request.form.get('unit_code'))
    unit_correlative = (request.form.get('unit_correlative') or '').strip()
    offer_items = _get_provider_offer_items(provider_code)

    item = _find_offer_item(offer_items, item_id=item_id, product_code=product_code)
    if item and item.get('item_type') == 'new_product':
        offer_context = service.build_provider_offer_context(offer_items, _provider_offer_coin_symbol())
        return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)

    if item:
        unit = next(
            (
                option for option in item.get('unit_options', [])
                if str(option.get('correlative') or '') == str(unit_correlative or '')
                or (
                    not unit_correlative and
                    normalize_upper(option.get('code')) == unit_code
                )
            ),
            None,
        )
        if unit is None:
            unit = next(
                (
                    option for option in service.get_provider_product_units(product_code)
                    if str(option.get('correlative') or '') == str(unit_correlative or '')
                    or (
                        not unit_correlative and
                        normalize_upper(option.get('code')) == unit_code
                    )
                ),
                None,
            )
        if unit:
            selected_unit_from_db = service.get_provider_product_unit_by_correlative(
                unit.get('correlative') or unit_correlative
            )
            if selected_unit_from_db:
                unit = selected_unit_from_db
            previous_unit = service.get_provider_product_unit_by_correlative(item.get('unit_correlative'))
            previous_units_per_main = service._units_per_main(
                (previous_unit or {}).get('conversion_factor') or item.get('conversion_factor'),
                (previous_unit or {}).get('unit_type') if previous_unit is not None else item.get('unit_type')
            )
            new_units_per_main = service._units_per_main(
                unit.get('conversion_factor'), unit.get('unit_type')
            )
            current_main_quantity = float(item.get('main_quantity') or (float(item.get('quantity') or 0) * previous_units_per_main))
            current_unit_price = float(item.get('unit_price') or 0)

            item['unit_code'] = unit.get('code') or unit.get('unit') or unit.get('unit_code') or item.get('unit_code')
            item['unit'] = unit.get('description') or unit.get('unit') or item.get('unit')
            item['unit_correlative'] = unit.get('correlative') or item.get('unit_correlative')
            item['conversion_factor'] = unit.get('conversion_factor') or 1
            item['unit_type'] = unit.get('unit_type') or 0
            item['main_quantity'] = current_main_quantity
            item['quantity'] = current_main_quantity / new_units_per_main if new_units_per_main else current_main_quantity
            item['unit_price'] = (
                current_unit_price * new_units_per_main / previous_units_per_main
                if previous_units_per_main and new_units_per_main
                else current_unit_price
            )

    _set_provider_offer_items(provider_code, offer_items)
    offer_context = service.build_provider_offer_context(offer_items, _provider_offer_coin_symbol())
    return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)


@shopping_bp.route('/provider_offer_items/remove', methods=['POST'])
@provider_session_required
def provider_offer_items_remove():
    provider_code = session.get('provider_code', '')
    item_id = _normalize_offer_item_id(request.form.get('item_id'))
    product_code = normalize_upper(request.form.get('product_code'))
    existing_items = _get_provider_offer_items(provider_code)
    remaining_items = [
        item for item in existing_items
        if _normalize_offer_item_id(item.get('item_id')) != item_id
        and (item_id or normalize_upper(item.get('code')) != product_code)
    ]
    for item in existing_items:
        if item not in remaining_items:
            _delete_provider_offer_item_image(provider_code, item)

    _set_provider_offer_items(provider_code, remaining_items)
    offer_context = service.build_provider_offer_context(remaining_items, _provider_offer_coin_symbol())
    return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)


@shopping_bp.route('/provider_offer_items/clear', methods=['POST'])
@provider_session_required
def provider_offer_items_clear():
    provider_code = session.get('provider_code', '')
    for item in _get_provider_offer_items(provider_code):
        _delete_provider_offer_item_image(provider_code, item)
    _set_provider_offer_items(provider_code, [])
    offer_context = service.build_provider_offer_context([], _provider_offer_coin_symbol())
    return render_template('providers/partials/offer_details_container.html', offer_context=offer_context)


@shopping_bp.route('/provider_logout')
def provider_logout():
    provider_code = session.get('provider_code', '')
    for item in _get_provider_offer_items(provider_code):
        _delete_provider_offer_item_image(provider_code, item)
    session.pop('provider_logged_in', None)
    session.pop('provider_username', None)
    session.pop('provider_code', None)
    flash('Sesión de proveedor cerrada correctamente.', 'success')
    return redirect(url_for('shopping.provider_login'))


@shopping_bp.route('/order')
@login_required 
def order():
    code_provider = (request.args.get('code_provider') or '').strip()
    review_list_correlative = request.args.get('review_list_correlative')
    selected_product_code = (request.args.get('product_code') or '').strip()


    if not code_provider:
        cart_context = service.get_shopping_cart_context('', current_user.get_id())
        return render_template(
            'shopping/panel_shopping/order.html',
            provider=None,
            selected_provider_code='',
            **cart_context,
        )

    provider = service.get_provider_by_code(code_provider)
    if not provider:
        flash(f'No se encontró un proveedor con el código {code_provider}.', 'error')
        cart_context = service.get_shopping_cart_context('', current_user.get_id())
        return render_template(
            'shopping/panel_shopping/order.html',
            provider=None,
            selected_provider_code=code_provider,
            **cart_context,
        )

    selected_review_list = None
    review_products = []
    total_review_products = 0
    selected_product = None
    selected_review_item = None
    inventory_params = []
    shopping_params = None
    purchase_history = []
    product_units = []

    if review_list_correlative:
        selected_review_list = service.get_provider_review_list_detail_context(
            provider.code,
            review_list_correlative,
            coin_symbol=_provider_offer_coin_symbol(),
        )
        if selected_review_list is None:
            flash('No se encontró la lista de oferta seleccionada para este proveedor.', 'warning')
        else:
            review_products = selected_review_list.get('items', [])
            total_review_products = len(review_products)
            first_catalog_product = next(
                (
                    item for item in review_products
                    if (item.get('item_type') == 'catalog' and (item.get('code') or '').strip())
                ),
                None,
            )
            if first_catalog_product:
                selected_code = first_catalog_product.get('code', '').strip()
                selected_product = service.get_product_order_details(selected_code)
                selected_review_item = first_catalog_product
                inventory_params = service.get_product_inventory_params(selected_code)
                shopping_params = service.get_product_shopping_param(selected_code)
                purchase_history = service.get_product_purchase_history(selected_code)
                product_units = service.get_provider_product_units(selected_code)

    if not review_products:
        review_products, total_review_products, _, _, _ = service.search_products(
            provider_code=provider.code,
            page=1,
            per_page=12,
        )

    navigable_products = [
        item for item in review_products
        if item.get('item_type', 'catalog') == 'catalog' and (item.get('code') or '').strip()
    ]
    selected_product_index = 0
    if navigable_products:
        selected_product_index = next(
            (
                index
                for index, item in enumerate(navigable_products)
                if item.get('code', '').strip() == selected_product_code
            ),
            0,
        )
        selected_navigation_item = navigable_products[selected_product_index]
        selected_navigation_code = selected_navigation_item.get('code', '').strip()
        if selected_navigation_code and (
            selected_product is None or selected_product.get('code') != selected_navigation_code
        ):
            selected_product = service.get_product_order_details(selected_navigation_code)
            selected_review_item = selected_navigation_item if review_list_correlative else None
            inventory_params = service.get_product_inventory_params(selected_navigation_code)
            shopping_params = service.get_product_shopping_param(selected_navigation_code)
            purchase_history = service.get_product_purchase_history(selected_navigation_code)
            product_units = service.get_provider_product_units(selected_navigation_code)
    
    cart_context = service.get_shopping_cart_context(
        provider.code,
        current_user.get_id(),
        review_list_correlative,
    )
    inventory_total_stock = sum(inventory_param['stock'] for inventory_param in inventory_params)
    return render_template(
        'shopping/panel_shopping/order.html',
        provider=provider,
        selected_provider_code=provider.code,
        review_list_correlative=review_list_correlative,
        selected_review_list=selected_review_list,
        review_products=review_products,
        review_products_total=total_review_products,
        product=selected_product,
        selected_review_item=selected_review_item,
        navigable_products=navigable_products,
        selected_product_index=selected_product_index,
        product_units=product_units,
        inventory_params=inventory_params,
        inventory_total_stock=inventory_total_stock,
        shopping_params=shopping_params,
        purchase_history=purchase_history,
        **cart_context,
    )

@shopping_bp.route('/shopping_cart')
@login_required
def shopping_cart():
    code_provider = (request.args.get('code_provider') or '').strip()
    review_list_correlative = request.args.get('review_list_correlative')
    cart_context = service.get_shopping_cart_context(
        code_provider,
        current_user.get_id(),
        review_list_correlative,
    )

    return render_template('shopping/panel_shopping/shopping_cart.html', **cart_context)


def _render_shopping_cart(provider_code, review_list_correlative=None):
    cart_context = service.get_shopping_cart_context(
        provider_code,
        current_user.get_id(),
        review_list_correlative,
    )
    return render_template('shopping/panel_shopping/shopping_cart.html', **cart_context)


@shopping_bp.route('/shopping_cart/items', methods=['POST'])
@login_required
def shopping_cart_add_item():
    provider_code = (request.form.get('code_provider') or '').strip()
    review_list_correlative = request.form.get('review_list_correlative')
    try:
        cart = service.get_or_create_shopping_cart(
            provider_code,
            current_user.get_id(),
            review_list_correlative,
        )
        service.add_shopping_cart_item(
            cart,
            product_code=request.form.get('product_code'),
            unit_id=request.form.get('unit_id'),
            quantity=request.form.get('quantity'),
            unitary_cost=request.form.get('unitary_cost'),
            note=request.form.get('note'),
            source_review_item_id=request.form.get('source_review_item_id'),
        )
    except ValueError as error:
        flash(str(error), 'error')
    return _render_shopping_cart(provider_code, review_list_correlative)


@shopping_bp.route('/shopping_cart/items/<int:item_id>', methods=['POST'])
@login_required
def shopping_cart_update_item(item_id):
    provider_code = (request.form.get('code_provider') or '').strip()
    review_list_correlative = request.form.get('review_list_correlative')
    try:
        cart = service.get_or_create_shopping_cart(
            provider_code,
            current_user.get_id(),
            review_list_correlative,
        )
        service.update_shopping_cart_item(cart, item_id, request.form.get('quantity'))
    except ValueError as error:
        flash(str(error), 'error')
    return _render_shopping_cart(provider_code, review_list_correlative)


@shopping_bp.route('/shopping_cart/items/<int:item_id>/remove', methods=['POST'])
@login_required
def shopping_cart_remove_item(item_id):
    provider_code = (request.form.get('code_provider') or '').strip()
    review_list_correlative = request.form.get('review_list_correlative')
    try:
        cart = service.get_or_create_shopping_cart(
            provider_code,
            current_user.get_id(),
            review_list_correlative,
        )
        service.remove_shopping_cart_item(cart, item_id)
    except ValueError as error:
        flash(str(error), 'error')
    return _render_shopping_cart(provider_code, review_list_correlative)

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
    query = (request.args.get('q') or '').strip()
    reference = (request.args.get('reference') or '').strip()
    mark_codes = request.args.getlist('mark_codes')
    department_codes = request.args.getlist('department_codes')
    only_provider_products = request.args.get('only_provider_products', '1') == '1'
    provider_code = session.get('provider_code', '')
    page = request.args.get('page', 1, type=int)
    append = request.args.get('append') == '1'
    list_only = request.args.get('list_only') == '1'

    products, total_products, total_pages, current_page, stock_stores = service.get_provider_catalog_products(
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        department_codes=department_codes,
        provider_code=provider_code,
        only_provider_products=only_provider_products,
        page=page,
        per_page=20,
    )

    if append:
        return render_template(
            'providers/products_modal_provider/rows.html',
            products=products,
            query=query,
            reference=reference,
            mark_codes=mark_codes,
            department_codes=department_codes,
            only_provider_products=only_provider_products,
            total_products=total_products,
            total_pages=total_pages,
            current_page=current_page,
            stock_stores=stock_stores,
        )

    if list_only:
        return render_template(
            'providers/products_modal_provider/list.html',
            products=products,
            query=query,
            reference=reference,
            mark_codes=mark_codes,
            department_codes=department_codes,
            only_provider_products=only_provider_products,
            total_products=total_products,
            total_pages=total_pages,
            current_page=current_page,
            stock_stores=stock_stores,
        )

    marks, departments = service.get_product_filter_options()
    return render_template(
        'providers/products_modal_provider/modal.html',
        products=products,
        query=query,
        reference=reference,
        mark_codes=mark_codes,
        marks=marks,
        department_codes=department_codes,
        departments=departments,
        only_provider_products=only_provider_products,
        total_products=total_products,
        total_pages=total_pages,
        current_page=current_page,
        stock_stores=stock_stores,
    )

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
        'shopping/partials/modal_providers/modal_providers.html',
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
        'shopping/partials/modal_providers/modal_providers_rows.html',
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