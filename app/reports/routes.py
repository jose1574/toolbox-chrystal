from io import BytesIO
from datetime import datetime
from urllib.parse import urlencode

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

from app import db
from app.models import (
    Department,
    Mark,
    Store,
)
from app.reports import reports_bp
from app.reports.utils import generate_barcode, render_pdf
from app.reports.services import reports_service
from app.inventory.services import inventory_service


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

    main_code = reports_service.resolve_main_code(product_code)
    product = reports_service.get_product_info(main_code)
    if not product:
        return render_template(
            "inventory/partials/product_stock_details.html",
            product=None,
            product_stocks=[],
            stock_total=0,
            error="No se encontro el producto indicado.",
        )

    product_stocks = reports_service.get_stock_by_store(main_code)
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
        reports_service.search_products_for_stock_report(query, page=page, per_page=10)
    )
    return render_template(
        "inventory/partials/modal_producs_stock.html",
        products=products,
        query=query,
        page=current_page,
        total_pages=total_pages,
        total_products=total_products,
    )


PRODUCT_LOCATIONS_PDF_LIMIT = 5000
PRODUCT_LOCATIONS_EXCEL_LIMIT = 65000
PRODUCT_LOCATIONS_STATE_FILTERS = {"with", "without"}


def _build_product_location_filters(args):
    mark_codes = [
        reports_service.normalize_code(code) for code in args.getlist("mark_codes")
    ]
    department_codes = [
        reports_service.normalize_code(code) for code in args.getlist("department_codes")
    ]
    store_codes = [
        reports_service.normalize_code(code) for code in args.getlist("store_codes")
    ]
    location_state = args.get("location_state", "")
    stock_state = args.get("stock_state", "")
    product_status = args.get("product_status", "") or "active"
    return {
        "q": (args.get("q") or "").strip(),
        "mark_codes": [code for code in mark_codes if code],
        "department_codes": [code for code in department_codes if code],
        "store_codes": [code for code in store_codes if code],
        "location_state": (
            location_state if location_state in PRODUCT_LOCATIONS_STATE_FILTERS else ""
        ),
        "stock_state": (
            stock_state if stock_state in PRODUCT_LOCATIONS_STATE_FILTERS else ""
        ),
        "product_status": (
            product_status if product_status in {"active", "all"} else "active"
        ),
        "page": max(args.get("page", 1, type=int) or 1, 1),
    }


def _build_product_location_export_query(filters):
    pairs = []
    if filters["q"]:
        pairs.append(("q", filters["q"]))
    for code in filters["mark_codes"]:
        pairs.append(("mark_codes", code))
    for code in filters["department_codes"]:
        pairs.append(("department_codes", code))
    for code in filters["store_codes"]:
        pairs.append(("store_codes", code))
    if filters["location_state"]:
        pairs.append(("location_state", filters["location_state"]))
    if filters["stock_state"]:
        pairs.append(("stock_state", filters["stock_state"]))
    if filters["product_status"] == "all":
        pairs.append(("product_status", "all"))
    return urlencode(pairs)


def _get_product_location_table_context(filters):
    total_products, total_rows = reports_service.get_product_location_totals(filters)
    total_pages = max(
        (total_rows + reports_service.PRODUCT_LOCATIONS_PER_PAGE - 1)
        // reports_service.PRODUCT_LOCATIONS_PER_PAGE,
        1,
    )
    page = min(filters["page"], total_pages)

    rows = []
    if total_rows:
        rows = db.session.execute(
            reports_service.get_product_location_rows_query(filters)
            .limit(reports_service.PRODUCT_LOCATIONS_PER_PAGE)
            .offset((page - 1) * reports_service.PRODUCT_LOCATIONS_PER_PAGE)
        ).all()

    return {
        "rows": rows,
        "page": page,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "total_products": total_products,
        "export_query": _build_product_location_export_query(filters),
    }


@reports_bp.route("/product_locations")
@login_required
def product_locations():
    filters = _build_product_location_filters(request.args)
    return render_template(
        "reports/product_locations.html",
        filters=filters,
        marks=Mark.query.order_by(Mark.description.asc(), Mark.code.asc()).all(),
        departments=Department.query.order_by(
            Department.description.asc(), Department.code.asc()
        ).all(),
        stores=Store.query.order_by(Store.description.asc(), Store.code.asc()).all(),
        **_get_product_location_table_context(filters),
    )


@reports_bp.route("/product_locations/table")
@login_required
def product_locations_table():
    filters = _build_product_location_filters(request.args)
    return render_template(
        "reports/partials/product_locations_table.html",
        **_get_product_location_table_context(filters),
    )


@reports_bp.route("/product_locations/pdf")
@login_required
def product_locations_pdf():
    filters = _build_product_location_filters(request.args)
    _, total_rows = reports_service.get_product_location_totals(filters)
    rows = db.session.execute(
        reports_service.get_product_location_rows_query(filters).limit(
            PRODUCT_LOCATIONS_PDF_LIMIT
        )
    ).all()

    pdf = render_pdf(
        "reports/product_locations_pdf.html",
        {
            "rows": rows,
            "filters": filters,
            "truncated": total_rows > PRODUCT_LOCATIONS_PDF_LIMIT,
            "limit": PRODUCT_LOCATIONS_PDF_LIMIT,
            "now": datetime.now(),
            "user": current_user,
        },
        paper_format="Letter",
        orientation="Landscape",
    )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=ubicacion_productos.pdf"},
    )


@reports_bp.route("/product_locations/excel")
@login_required
def product_locations_excel():
    filters = _build_product_location_filters(request.args)
    rows = db.session.execute(
        reports_service.get_product_location_rows_query(filters).limit(
            PRODUCT_LOCATIONS_PDF_LIMIT
        )
    ).all()

    output = BytesIO()
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Ubicaciones")

    header_style = xlwt.easyxf(
        "font: bold on; pattern: pattern solid, fore_colour gray25;"
    )
    text_style = xlwt.easyxf(num_format_str="@")
    number_style = xlwt.easyxf(num_format_str="0.00")

    columns = [
        "Código",
        "Nombre",
        "Marca",
        "Departamento",
        "Depósito",
        "Stock",
        "Ubicación",
    ]
    for col_idx, title in enumerate(columns):
        ws.write(0, col_idx, title, header_style)

    for row_idx, row in enumerate(rows, start=1):
        values = [
            row.code,
            row.description,
            row.mark_description,
            row.department_description,
            row.store_description or row.store_code,
        ]
        for col_idx, value in enumerate(values):
            ws.write(row_idx, col_idx, "" if value is None else str(value), text_style)
        ws.write(row_idx, 5, float(row.stock or 0), number_style)
        ws.write(row_idx, 6, row.location or "", text_style)

    for col_idx, title in enumerate(columns):
        ws.col(col_idx).width = min(max(len(title) + 4, 14), 45) * 256

    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="ubicacion_productos.xls",
        mimetype="application/vnd.ms-excel",
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
    product = reports_service.get_product_info(filters["resolved_product_code"])
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
        reports_service.search_products_for_stock_report(query, page=page, per_page=10)
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
