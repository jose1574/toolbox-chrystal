from flask import Response, render_template, request
from pathlib import Path

from flask_login import login_required
from sqlalchemy import func
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


@label_bp.route("/")
@login_required
def index():
    return render_template("products_label.html")


@label_bp.route("/listado-de-etiquetas")
@login_required
def product_label_list():
    return render_template("list_product_label.html")


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


@label_bp.route("/agregar-producto-listado-etiquetas", methods=["POST"])
@login_required
def add_product_list():
    code = (request.values.get("code") or "").strip()
    description = (request.values.get("description") or "").strip()
    main_code = (request.values.get("main_code") or "").strip()

    if not code:
        return "", 400

    return f"""
        <tr class="">
            <td class="p-4">
                {main_code}
                <input type="hidden" name="main_code" value="{main_code}">
            </td>
            <td class="p-4">
                {description}
                <input type="hidden" name="description" value="{description}">
            </td>
            <td class="p-4">
                {code}
                <input type="hidden" name="code_printer" value="{code}">
            </td>
        </tr>
    """


@label_bp.route('/imprimitir-etiquetas', methods=['POST'])
@login_required 
def print_labels():
    products_list = [
        value.strip() for value in request.form.getlist('code_printer') if value.strip()
    ]
    main_codes = request.form.getlist('main_code')
    descriptions = request.form.getlist('description')

    if not products_list:
        return "No se recibieron codigos para imprimir.", 400

    labels = []
    for index, code in enumerate(products_list):
        main_code = (main_codes[index].strip() if index < len(main_codes) else "")
        description = (
            descriptions[index].strip() if index < len(descriptions) else ""
        )
        labels.append(
            {
                'code': code,
                'main_code': main_code,
                'description': description,
                'barcode_base64': generate_barcode(code),
            }
        )

    html_source = Path(__file__).resolve().parent / 'reports' / 'product_label_pdf.html'

    pdf = render_pdf_from_html_file(
        html_source,
        {
            'labels': labels,
        },
        paper_format='Label56x44',
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