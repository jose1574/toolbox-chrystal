import math
from datetime import datetime

from flask import (
    Response,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db, get_device_id
from app.models import SalesInvoiceDispatchItem
from app.printer_config.services import printer_config_service
from app.reports.utils import generate_barcode, render_pdf
from app.sales import sales_bp
from app.sales.services import printing_service, sales_service


@sales_bp.route("/point-of-sale")
@login_required
def point_of_sale():
    return render_template("bill_point/sales_bill_point.html")


@sales_bp.route("/point-of-sale/products")
@login_required
def pos_product_catalog():
    result = sales_service.list_pos_products(
        page=request.args.get("page", 1, type=int),
        query_text=request.args.get("q", ""),
        profile_code=current_user.profile,
    )
    return render_template("bill_point/partials/product_catalog_results.html", **result)


@sales_bp.route("/point-of-sale/product-by-code")
@login_required
def pos_product_by_code():
    product = sales_service.get_pos_product_by_code(
        request.args.get("code", ""), profile_code=current_user.profile
    )
    if not product:
        return jsonify({"message": "No se encontró un producto con ese código."}), 404
    if not product["can_add"]:
        return jsonify({"message": "El producto no tiene un precio configurado."}), 422

    return jsonify(
        {
            "code": product["code"],
            "description": product["description"] or product["code"],
            "unit": product["unit_description"] or "UND",
            "coinCode": product["coin_code"] or "",
            "coinSymbol": product["coin_symbol"] or product["coin_code"] or "",
            "price": float(product["unit_price"]),
            "allowDecimal": bool(product["allow_decimal"]),
            "canAdd": True,
        }
    )


def _dispatch_context(dispatch, extra=None):
    items = sales_service.get_dispatch_items(dispatch.correlative)
    context = {
        "dispatch": dispatch,
        "items": items,
        "participants": sales_service.get_dispatch_participants(dispatch.correlative),
        "error": None,
        "invoice_code": dispatch.document_no or "",
    }
    if extra:
        context.update(extra)
    return context


@sales_bp.route("/dispatch", methods=["GET", "POST"])
@login_required
def invoice_dispatch():
    if request.method == "POST":
        invoice_code = (request.form.get("invoice_code") or "").strip()
        if not invoice_code:
            return render_template(
                "sales/invoice_dispatch.html",
                dispatch=None,
                items=[],
                error="Debe escanear o ingresar el codigo de la factura.",
                invoice_code=invoice_code,
            )

        invoice = sales_service.find_sales_invoice(invoice_code)
        if not invoice:
            return render_template(
                "sales/invoice_dispatch.html",
                dispatch=None,
                items=[],
                error="No se encontro una factura de venta valida con ese codigo.",
                invoice_code=invoice_code,
            )

        try:
            dispatch, created = sales_service.load_or_open_dispatch(
                invoice, current_user.code
            )
        except sales_service.DispatchError as exc:
            return render_template(
                "sales/invoice_dispatch.html",
                dispatch=None,
                items=[],
                error=str(exc),
                invoice_code=invoice_code,
            )

        if created:
            flash("Factura cargada y registrada para despacho.", "success")
        else:
            flash("Se reabrio el despacho de esta factura.", "info")
        return redirect(url_for("sales.invoice_dispatch_detail", dispatch_id=dispatch.correlative))

    return render_template(
        "sales/invoice_dispatch.html",
        dispatch=None,
        items=[],
        error=None,
        invoice_code="",
    )


@sales_bp.route("/dispatch/<int:dispatch_id>")
@login_required
def invoice_dispatch_detail(dispatch_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        flash("No se encontro el despacho indicado.", "error")
        return redirect(url_for("sales.invoice_dispatch"))
    show_completion_choice = (
        request.args.get("ask_report") == "1"
        and dispatch.status == sales_service.STATUS_COMPLETE
    )
    return render_template(
        "sales/invoice_dispatch.html",
        **_dispatch_context(dispatch),
        show_completion_choice=show_completion_choice,
    )


@sales_bp.route("/dispatch/reprints")
@login_required
def dispatch_reprints():
    page = request.args.get("page", 1, type=int) or 1
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "status": request.args.get("status") or "all",
    }
    if filters["status"] not in ("all", sales_service.STATUS_PARTIAL, sales_service.STATUS_COMPLETE):
        filters["status"] = "all"

    result = sales_service.list_dispatches_for_reprint(
        page=page,
        query_text=filters["q"],
        status_filter=filters["status"],
    )
    result["page_numbers"] = range(
        max(1, result["page"] - 2), min(result["pages"], result["page"] + 2) + 1
    )
    result["filters"] = filters
    return render_template("sales/dispatch_reprints.html", **result)


def _render_dispatched_products_pdf(dispatch, items):
    document_no = dispatch.document_no or str(dispatch.sales_operation_correlative)
    barcode_base64 = generate_barcode(document_no) if document_no else None

    estimated_extra_lines = 0
    for item in items:
        description = item.product_description or ""
        description_lines = max(1, math.ceil(len(description) / 22))
        estimated_extra_lines += max(0, description_lines - 3)
    page_height_mm = max(
        120, 89 + (len(items) * 14.5) + (estimated_extra_lines * 2.8)
    )

    return render_pdf(
        "sales/reports/dispatched_products_pdf.html",
        {
            "dispatch": dispatch,
            "items": items,
            "now": datetime.now(),
            "user": current_user,
            "barcode_base64": barcode_base64,
        },
        paper_format="Letter",
        orientation="Portrait",
        extra_options={
            "page-width": "80mm",
            "page-height": f"{page_height_mm}mm",
            "margin-top": "0mm",
            "margin-right": "0mm",
            "margin-bottom": "0mm",
            "margin-left": "0mm",
            "disable-smart-shrinking": None,
            "print-media-type": None,
        },
    )


@sales_bp.route("/dispatch/<int:dispatch_id>/dispatched-pdf")
@login_required
def dispatched_products_pdf(dispatch_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        flash("No se encontro el despacho indicado.", "error")
        return redirect(url_for("sales.invoice_dispatch"))

    items = sales_service.get_dispatched_items(dispatch_id)
    document_no = dispatch.document_no or str(dispatch.sales_operation_correlative)
    return Response(
        _render_dispatched_products_pdf(dispatch, items),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=despacho_{document_no}.pdf"
        },
    )


@sales_bp.route("/dispatch/<int:dispatch_id>/print", methods=["POST"])
@login_required
def print_dispatched_products(dispatch_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        return jsonify(error="No se encontro el despacho indicado."), 404

    items = sales_service.get_dispatched_items(dispatch_id)
    if not items:
        return jsonify(error="No hay productos despachados para imprimir."), 400

    printer_name = printer_config_service.resolve_printer_name(
        get_device_id(), "sales_dispatch"
    )
    if not printer_name:
        return jsonify(
            error="No hay una impresora configurada para este dispositivo ni "
            "una predeterminada en el servidor. Configure una en "
            "Configuracion de impresoras."
        ), 400

    try:
        printing_service.print_pdf_to_windows_printer(
            _render_dispatched_products_pdf(dispatch, items),
            printer_name=printer_name,
            width_dots=current_app.config["DISPATCH_PRINTER_WIDTH_DOTS"],
        )
    except Exception:
        current_app.logger.exception(
            "Failed to print dispatched products for dispatch %s", dispatch_id
        )
        return jsonify(error="No se pudo enviar el recibo a la impresora."), 502

    return jsonify(message=f"El trabajo fue enviado a la impresora {printer_name}.")


@sales_bp.route("/dispatch/<int:dispatch_id>/scan-product", methods=["GET"])
@login_required
def scan_dispatch_product(dispatch_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        return render_template(
            "sales/partials/dispatch_qty_modal.html",
            item=None,
            remaining=0,
            error="No se encontro el despacho indicado.",
        )

    scanned_code = request.args.get("product_code")
    try:
        item, main_code, remaining = sales_service.find_pending_item_for_product(
            dispatch_id, scanned_code
        )
    except sales_service.DispatchError as exc:
        return render_template(
            "sales/partials/dispatch_qty_modal.html",
            item=None,
            remaining=0,
            error=str(exc),
            scanned_code=scanned_code,
        )

    return render_template(
        "sales/partials/dispatch_qty_modal.html",
        item=item,
        remaining=remaining,
        error=None,
        scanned_code=main_code,
        dispatch=dispatch,
    )


@sales_bp.route("/dispatch/<int:dispatch_id>/manual-qty/<int:item_id>", methods=["GET"])
@login_required
def manual_dispatch_qty(dispatch_id, item_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        return render_template(
            "sales/partials/dispatch_qty_modal.html",
            item=None,
            remaining=0,
            error="No se encontro el despacho indicado.",
        )

    try:
        item, remaining = sales_service.get_item_for_manual_qty(dispatch_id, item_id)
    except sales_service.DispatchError as exc:
        return render_template(
            "sales/partials/dispatch_qty_modal.html",
            item=None,
            remaining=0,
            error=str(exc),
        )

    return render_template(
        "sales/partials/dispatch_qty_modal.html",
        item=item,
        remaining=remaining,
        error=None,
        scanned_code=item.product_code,
        dispatch=dispatch,
    )


@sales_bp.route("/dispatch/<int:dispatch_id>/confirm-qty", methods=["POST"])
@login_required
def confirm_dispatch_qty(dispatch_id):
    dispatch = sales_service.get_dispatch(dispatch_id)
    if not dispatch:
        response = make_response(
            render_template(
                "sales/partials/dispatch_qty_modal.html",
                item=None,
                remaining=0,
                error="No se encontro el despacho indicado.",
            )
        )
        response.headers["HX-Retarget"] = "#dispatch-qty-modal"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    item_id = request.form.get("item_id", type=int)
    quantity = request.form.get("quantity")
    try:
        dispatch, item = sales_service.confirm_dispatch_quantity(
            dispatch_id, item_id, quantity, current_user.code
        )
    except sales_service.DispatchError as exc:
        item = SalesInvoiceDispatchItem.query.get(item_id)
        remaining = sales_service.remaining_amount(item) if item else 0
        response = make_response(
            render_template(
                "sales/partials/dispatch_qty_modal.html",
                item=item,
                remaining=remaining,
                error=str(exc),
                scanned_code=item.product_code if item else "",
                dispatch=dispatch,
            )
        )
        response.headers["HX-Retarget"] = "#dispatch-qty-modal"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    if dispatch.status == sales_service.STATUS_COMPLETE:
        flash(
            "Se completo el despacho de la factura "
            f"{dispatch.document_no or dispatch.sales_operation_correlative}.",
            "success",
        )
        completion_url = url_for(
            "sales.invoice_dispatch_detail",
            dispatch_id=dispatch.correlative,
            ask_report=1,
        )
        if request.headers.get("HX-Request"):
            response = make_response("", 200)
            response.headers["HX-Redirect"] = completion_url
            return response
        return redirect(completion_url)

    items = sales_service.get_dispatch_items(dispatch.correlative)
    participants = sales_service.get_dispatch_participants(dispatch.correlative)
    if item.status == sales_service.STATUS_PARTIAL:
        complete_message = (
            f"Despacho parcial de {item.product_code}. "
            f"Pendiente: {sales_service.remaining_amount(item):.2f}."
        )
    else:
        complete_message = f"Producto {item.product_code} despachado por completo."

    response = make_response(
        render_template(
            "sales/partials/dispatch_lines.html",
            dispatch=dispatch,
            items=items,
            participants=participants,
            success_message=complete_message,
        )
    )
    response.headers["HX-Trigger"] = "dispatchQtySaved"
    return response


@sales_bp.route("/pending")
@login_required
def pending_invoices():
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "status": request.args.get("status") or "open",
    }
    rows = sales_service.list_pending_dispatches(filters["q"], filters["status"])
    return render_template(
        "sales/pending_invoices.html",
        rows=rows,
        filters=filters,
    )


@sales_bp.route("/pending/table")
@login_required
def pending_invoices_table():
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "status": request.args.get("status") or "open",
    }
    rows = sales_service.list_pending_dispatches(filters["q"], filters["status"])
    return render_template(
        "sales/partials/pending_invoices_table.html",
        rows=rows,
        filters=filters,
    )


@sales_bp.route("/pending/pdf")
@login_required
def pending_invoices_pdf():
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "status": request.args.get("status") or "open",
    }
    rows = sales_service.list_pending_dispatches(filters["q"], filters["status"])
    pdf = render_pdf(
        "sales/reports/pending_invoices_pdf.html",
        {
            "rows": rows,
            "filters": filters,
            "now": datetime.now(),
            "user": current_user,
        },
        paper_format="Letter",
        orientation="Landscape",
    )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=facturas_por_despachar.pdf"},
    )
