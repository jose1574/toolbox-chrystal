from flask import Response, render_template, request, flash
import base64
from pathlib import Path

from flask_login import login_required
from sqlalchemy import func
from app import db
from app.reports.utils import generate_barcode, render_pdf_from_html_file

from app.products_label import label_bp

from app.models import (
    Product,
    ProductsCode,
)


def _resolve_main_code(code):
    normalized = (code or "").strip().upper()
    if not normalized:
        return None

    mapping = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == normalized
    ).first()

    return mapping.main_code if mapping else normalized


def _load_logo_base64():
    logo_path = Path(__file__).resolve().parent / 'images' / 'logo.png'
    if not logo_path.exists():
        return None

    try:
        return base64.b64encode(logo_path.read_bytes()).decode('utf-8')
    except OSError:
        return None


def _render_product_label_row(main_code, short_name, code):
    return f"""
        <tr class="">
            <td class="p-4">
                {main_code}
                <input type="hidden" name="main_code" value="{main_code}">
            </td>
            <td class="p-4">
                {short_name}
                <input type="hidden" name="short_name" value="{short_name}">
            </td>
            <td class="p-4">
                {code}
                <input type="hidden" name="code_printer" value="{code}">
            </td>
            <td class="p-4">
                <button type="button" class="remove-row-btn text-red-500 hover:text-red-700" onclick="removeProductRow(this)">
                    Eliminar
                </button>
            </td>
        </tr>
    """


@label_bp.route("/")
@login_required
def index():
    return render_template("products_label.html")


@label_bp.route("/etiqueta-de-producto")
@login_required
def product_label_modal():
    code = request.args.get("product_code", "")
    main_code = _resolve_main_code(code)

    product_info = None
    if main_code:
        product_info = Product.query.filter(
            func.upper(func.trim(Product.code)) == main_code
        ).first()

    product_codes = (
        ProductsCode.query.filter_by(main_code=product_info.code).all()
        if product_info
        else []
    )

    error_message = None
    if not code.strip():
        error_message = "Ingresa un codigo de producto."
    elif not product_info:
        error_message = f'No se encontro producto para el codigo "{code}".'

    return render_template(
        "partials/product_label_modal.html",
        product=product_info,
        product_codes=product_codes,
        error_message=error_message,
    )


@label_bp.route("/modal-actualizar-nombre-corto")
@login_required
def update_short_name_modal():
    code = request.args.get("product_code", "")
    label_code = (request.args.get("label_code") or "").strip()

    product_info = None
    if code:
        product_info = Product.query.filter(
            func.upper(func.trim(Product.code)) == code
        ).first()

    error_message = None
    if not code.strip():
        error_message = "Ingresa un codigo de producto."
        flash(error_message, "error")
    elif not product_info:
        error_message = f'No se encontro producto para el codigo "{code}".'
        flash(error_message, "error")

    return render_template(
        "partials/update_short_name_product.html",
        product=product_info,
        label_code=label_code,
        error_message=error_message,
    )


@label_bp.route("/actualizar-nombre-corto", methods=["POST"])
@login_required
def update_short_name_product():
    code = (request.form.get("product_code") or "").strip()
    short_name = (request.form.get("short_name") or "").strip()
    code_to_add = (request.form.get("code_to_add") or "").strip()

    main_code = _resolve_main_code(code)
    product_info = None
    if main_code:
        product_info = Product.query.filter(
            func.upper(func.trim(Product.code)) == main_code
        ).first()

    if not product_info:
        return (
            render_template(
                "partials/update_short_name_product.html",
                product=None,
                label_code=code_to_add,
                error_message="No se encontro el producto a actualizar.",
            ),
            404,
        )

    product_info.short_name = short_name
    db.session.add(product_info)
    db.session.commit()

    main_code = product_info.code
    label_code = code_to_add or product_info.code
    short_name = product_info.short_name or product_info.description or ""

    return _render_product_label_row(main_code, short_name, label_code)


@label_bp.route('/imprimitir-etiquetas', methods=['POST'])
@login_required 
def print_labels():
    products_list = [
        value.strip() for value in request.form.getlist('code_printer') if value.strip()
    ]
    main_codes = request.form.getlist('main_code')
    short_names = request.form.getlist('short_name')

    if not products_list:
        return "No se recibieron codigos para imprimir.", 400

    labels = []
    for index, code in enumerate(products_list):
        main_code = (main_codes[index].strip() if index < len(main_codes) else "")
        short_name = (
            short_names[index].strip() if index < len(short_names) else ""
        )
        labels.append(
            {
                'code': code,
                'main_code': main_code,
                'description': short_name,  # El PDF espera 'description'
                'barcode_base64': generate_barcode(code),
            }
        )

    logo_base64 = _load_logo_base64()

    html_source = Path(__file__).resolve().parent / 'templates' / 'reports' / 'product_label_pdf.html'

    pdf = render_pdf_from_html_file(
        html_source,
        {
            'labels': labels,
            'logo_base64': logo_base64,
        },
        paper_format='label_56mmx32mm',
        orientation='Portrait',
        extra_options={
            'margin-top': '0mm',
            'margin-right': '0mm',
            'margin-bottom': '0mm',
            'margin-left': '0mm',
            'disable-smart-shrinking': None,
            'dpi': 203,
            'image-dpi': 203,
            'image-quality': 100,
            'zoom': 1,
            'print-media-type': None,
        },
    )

    return Response(
        pdf,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'inline; filename=etiquetas_productos.pdf'
        },
    )