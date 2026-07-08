from io import BytesIO
from datetime import datetime

import xlwt
from flask import (
    Response,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsCode,
    ProductsStock,
    ProductsUnit,
    Store,
    Unit,
)
from app.reports import reports_bp
from app.reports.utils import generate_barcode, render_pdf
from app.inventory.services import inventory_service


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _resolve_main_code(code: str) -> str:
    normalized = _normalize_code(code)
    mapping = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == normalized
    ).first()
    return _normalize_code(mapping.main_code) if mapping else normalized


def _get_product_info(main_code):
    if not main_code:
        return None

    stmt = (
        select(
            Product.code,
            Product.description,
            Product.referenc,
            Unit.description.label("unit_description"),
            Mark.description.label("mark_description"),
            Department.description.label("department_description"),
        )
        .join(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .join(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .where(func.upper(func.trim(Product.code)) == main_code)
    )
    return db.session.execute(stmt).first()


def _get_stock_by_store(main_code):
    stock_by_store = (
        select(
            ProductsStock.store.label("store_code"),
            func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock"),
        )
        .where(
            func.upper(func.trim(ProductsStock.product_code)) == main_code,
        )
        .group_by(ProductsStock.store)
        .subquery()
    )

    stmt = (
        select(
            Store.code.label("store_code"),
            Store.description.label("store_description"),
            func.coalesce(stock_by_store.c.stock, 0).label("stock"),
        )
        .outerjoin(stock_by_store, stock_by_store.c.store_code == Store.code)
        .order_by(Store.description.asc())
    )
    return db.session.execute(stmt).all()


def _search_products_for_stock_report(query, page=1, per_page=10):
    query = (query or "").strip()
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    stock_totals = (
        select(
            ProductsStock.product_code.label("product_code"),
            func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
        )
        .group_by(ProductsStock.product_code)
        .subquery()
    )

    filters = []
    if query:
        # 1. Reemplazamos los asteriscos por espacios para normalizar la búsqueda
        # Ejemplo: "*busing*1/4" -> " busing 1/4" -> ["busing", "1/4"]
        clean_query = query.replace('*', ' ')
        tokens = [token for token in clean_query.split() if token]

        # 2. Por cada palabra clave, exigimos que coincida con ALGUNO de los campos (OR)
        for token in tokens:
            search_value = f"%{token}%"
            # Este bloque evalúa una sola palabra contra todas las columnas
            token_filter = (
                (Product.code.ilike(search_value))
                | (Product.description.ilike(search_value))
                | (Product.referenc.ilike(search_value))
                | (ProductsCode.other_code.ilike(search_value))
            )
            # Al hacer append, SQLAlchemy las unirá con AND en el .where()
            filters.append(token_filter)

    base_stmt = (
        select(
            Product.code,
            Product.description,
            Product.referenc,
            Unit.description.label("unit_description"),
            Mark.description.label("mark_description"),
            Department.description.label("department_description"),
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
        )
        .join(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .join(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    )
    
    if filters:
        # *filters aplicará (FiltroToken1 AND FiltroToken2 AND FiltroToken3...)
        base_stmt = base_stmt.outerjoin(
            ProductsCode, ProductsCode.main_code == Product.code
        ).where(*filters)
        
    base_stmt = base_stmt.distinct(Product.code).order_by(Product.code.asc())

    if filters:
        count_stmt = (
            select(func.count(func.distinct(Product.code)))
            .select_from(Product)
            .join(
                ProductsUnit,
                (ProductsUnit.product_code == Product.code)
                & (ProductsUnit.main_unit.is_(True)),
            )
            .outerjoin(ProductsCode, ProductsCode.main_code == Product.code)
            .where(*filters)
        )
        total = db.session.execute(count_stmt).scalar() or 0
    else:
        total = db.session.execute(select(func.count()).select_from(Product)).scalar() or 0

    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    products = db.session.execute(
        base_stmt.limit(per_page).offset((page - 1) * per_page)
    ).all()
    
    return products, total, total_pages, page


@reports_bp.route("/product_stock")
@login_required
def product_stock():
    return render_template("inventory/product_stock.html")


@reports_bp.route("/product_stock/product_stock_details", methods=["GET"])
@login_required
def product_stock_details():
    product_code = request.args.get("product_code")
    if not product_code:
        return render_template(
            "inventory/partials/product_stock_details.html",
            product=None,
            product_stocks=[],
            stock_total=0,
            error=None,
        )

    main_code = _resolve_main_code(product_code)
    product = _get_product_info(main_code)
    if not product:
        return render_template(
            "inventory/partials/product_stock_details.html",
            product=None,
            product_stocks=[],
            stock_total=0,
            error="No se encontro el producto indicado.",
        )

    product_stocks = _get_stock_by_store(main_code)
    stock_total = sum(float(row.stock or 0) for row in product_stocks)

    return render_template(
        "inventory/partials/product_stock_details.html",
        product=product,
        product_stocks=product_stocks,
        stock_total=stock_total,
        error=None,
    )


@reports_bp.route("/product_stock/modal_producs_stock", methods=["GET"])
@login_required
def modal_producs_stock():
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    products, total_products, total_pages, current_page = (
        _search_products_for_stock_report(query, page=page, per_page=10)
    )
    return render_template(
        "inventory/partials/modal_producs_stock.html",
        products=products,
        query=query,
        page=current_page,
        total_pages=total_pages,
        total_products=total_products,
    )


FLOW_RECOLLECTION_ISSUED = "RECOLLECTION_ISSUED"
FLOW_RECOLLECTION_CHECKED = "RECOLLECTION_CHECKED"
FLOW_IN_TRANSIT = "IN_TRANSIT"
FLOW_RECEIVED = "RECEIVED"

TRANSFER_FLOW_STEPS = [
    {
        "key": "recollection_issued",
        "label": "Orden de recolección",
        "user_field": "recollection_issued_user",
        "user_name_field": "recollection_issued_user_name",
        "date_field": "recollection_issued_at",
    },
    {
        "key": "checked",
        "label": "Chequeo de orden de recolección",
        "user_field": "checking_user",
        "user_name_field": "checking_user_name",
        "date_field": "checked_at",
    },
    {
        "key": "in_transit",
        "label": "Firma digital del responsable de carga",
        "user_field": "in_transit_user",
        "user_name_field": "in_transit_user_name",
        "date_field": "in_transit_at",
    },
    {
        "key": "received",
        "label": "Recepción de traslado procesada",
        "user_field": "receiving_user",
        "user_name_field": "receiving_user_name",
        "date_field": "received_at",
    },
]

TRANSFER_STATUS_LABELS = {
    FLOW_RECOLLECTION_ISSUED: "Orden emitida",
    FLOW_RECOLLECTION_CHECKED: "Orden chequeada",
    FLOW_IN_TRANSIT: "En tránsito",
    FLOW_RECEIVED: "Recepcionado y procesado",
}


@reports_bp.route("/transfer_traceability", methods=["GET"])
@login_required
def transfer_traceability():
    filters = inventory_service.build_transfer_traceability_filters(
        request.args.get("status"),
        request.args.get("date_from"),
        request.args.get("date_to"),
        request.args.get("q"),
    )
    transfers = inventory_service.get_transfer_traceability_rows(filters)
    return render_template(
        "reports/transfer_traceability.html",
        transfers=transfers,
        filters=filters,
        flow_steps=TRANSFER_FLOW_STEPS,
        status_labels=TRANSFER_STATUS_LABELS,
    )


@reports_bp.route("/transfer_differences", methods=["GET"])
@login_required
def transfer_differences():
    filters = inventory_service.build_transfer_differences_filters(
        request.args.get("date_from"),
        request.args.get("date_to"),
        request.args.get("q"),
        request.args.get("resolution_status"),
    )
    transfers = inventory_service.get_transfer_differences_rows(filters)
    return render_template(
        "reports/transfer_differences.html",
        transfers=transfers,
        filters=filters,
        status_labels=TRANSFER_STATUS_LABELS,
    )


@reports_bp.route("/transfer_differences/<int:order_id>/resolve", methods=["POST"])
@login_required
def resolve_transfer_differences(order_id):
    try:
        updated = inventory_service.resolve_transfer_reception_differences(
            order_id,
            current_user.code,
            request.form.get("resolution_note"),
        )
        flash(f"Se resolvieron {updated} diferencia(s) del traslado #{order_id}.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")

    return redirect(
        url_for(
            "reports.transfer_differences",
            date_from=request.form.get("date_from", ""),
            date_to=request.form.get("date_to", ""),
            q=request.form.get("q", ""),
            resolution_status=request.form.get("resolution_status", ""),
        )
    )


@reports_bp.route("/transfer_product_traceability", methods=["GET"])
@login_required
def transfer_product_traceability():
    filters = inventory_service.build_transfer_product_traceability_filters(
        request.args.get("product_code")
    )
    product = _get_product_info(filters["resolved_product_code"])
    rows = inventory_service.get_transfer_product_traceability_rows(filters) if product else []
    return render_template(
        "reports/transfer_product_traceability.html",
        rows=rows,
        product=product,
        filters=filters,
        status_labels=TRANSFER_STATUS_LABELS,
    )


@reports_bp.route("/transfer_product_traceability/products_modal", methods=["GET"])
@login_required
def transfer_product_traceability_products_modal():
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    products, total_products, total_pages, current_page = (
        _search_products_for_stock_report(query, page=page, per_page=10)
    )
    return render_template(
        "reports/partials/transfer_product_traceability_products_modal.html",
        products=products,
        query=query,
        page=current_page,
        total_pages=total_pages,
        total_products=total_products,
    )


@reports_bp.route("/transfer_traceability/pdf", methods=["GET"])
@login_required
def transfer_traceability_pdf():
    filters = inventory_service.build_transfer_traceability_filters(
        request.args.get("status"),
        request.args.get("date_from"),
        request.args.get("date_to"),
        request.args.get("q"),
    )
    transfers = inventory_service.get_transfer_traceability_rows(filters)
    pdf = render_pdf(
        "reports/transfer_traceability_pdf.html",
        {
            "transfers": transfers,
            "filters": filters,
            "flow_steps": TRANSFER_FLOW_STEPS,
            "status_labels": TRANSFER_STATUS_LABELS,
            "now": datetime.now(),
            "user": current_user,
        },
        paper_format="Letter",
        orientation="Landscape",
    )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=trazabilidad_traslados.pdf"},
    )


@reports_bp.route("/transfer_traceability/excel", methods=["GET"])
@login_required
def transfer_traceability_excel():
    filters = inventory_service.build_transfer_traceability_filters(
        request.args.get("status"),
        request.args.get("date_from"),
        request.args.get("date_to"),
        request.args.get("q"),
    )
    transfers = inventory_service.get_transfer_traceability_rows(filters)

    output = BytesIO()
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Trazabilidad")

    header_style = xlwt.easyxf("font: bold on; pattern: pattern solid, fore_colour gray25;")
    text_style = xlwt.easyxf(num_format_str="@")
    date_style = xlwt.easyxf(num_format_str="DD/MM/YYYY HH:MM")

    columns = [
        "Correlativo",
        "Documento",
        "Fecha emisión",
        "Descripción",
        "Depósito origen",
        "Depósito destino",
        "Estado",
        "Orden usuario",
        "Orden fecha",
        "Chequeo usuario",
        "Chequeo fecha",
        "Carga usuario",
        "Carga fecha",
        "Recepción usuario",
        "Recepción fecha",
    ]

    for col_idx, title in enumerate(columns):
        ws.write(0, col_idx, title, header_style)

    def write_value(row_idx, col_idx, value):
        if isinstance(value, datetime):
            ws.write(row_idx, col_idx, value, date_style)
        else:
            ws.write(row_idx, col_idx, "" if value is None else str(value), text_style)

    for row_idx, transfer in enumerate(transfers, start=1):
        values = [
            transfer.operation_correlative,
            transfer.document_no,
            transfer.emission_date,
            transfer.description,
            f"{transfer.store_description or ''} ({transfer.store or ''})",
            f"{transfer.destination_store_description or ''} ({transfer.destination_store or ''})",
            TRANSFER_STATUS_LABELS.get(transfer.current_status, transfer.current_status),
            transfer.recollection_issued_user_name or transfer.recollection_issued_user,
            transfer.recollection_issued_at,
            transfer.checking_user_name or transfer.checking_user,
            transfer.checked_at,
            transfer.in_transit_user_name or transfer.in_transit_user,
            transfer.in_transit_at,
            transfer.receiving_user_name or transfer.receiving_user,
            transfer.received_at,
        ]
        for col_idx, value in enumerate(values):
            write_value(row_idx, col_idx, value)

    for col_idx, title in enumerate(columns):
        ws.col(col_idx).width = min(max(len(title) + 4, 14), 45) * 256

    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="trazabilidad_traslados.xls",
        mimetype="application/vnd.ms-excel",
    )


@reports_bp.route("/transfer_operation/reception_differences_report/<int:order_id>")
@login_required
def transfer_reception_differences_report(order_id):
    user = current_user
    order, differences, participants = inventory_service.get_transfer_reception_differences_report_data(order_id)

    barcode_base64 = generate_barcode(order.correlative)

    return Response(
        render_pdf(
            "reports/transfer_reception_differences_pdf.html",
            {
                "order": order,
                "differences": differences,
                "participants": participants,
                "title": f"Diferencias de recepción de traslado {order.correlative}",
                "now": datetime.now(),
                "barcode_base64": barcode_base64,
                "user": user,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=diferencias_traslado_{order.correlative}.pdf"
        },
    )
