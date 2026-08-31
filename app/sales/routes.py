from datetime import datetime

from flask import Response, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import SalesInvoiceDispatchItem
from app.reports.utils import render_pdf
from app.sales import sales_bp
from app.sales.services import sales_service


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
    return render_template("sales/invoice_dispatch.html", **_dispatch_context(dispatch))


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
        response = make_response("", 200)
        response.headers["HX-Redirect"] = url_for("sales.invoice_dispatch")
        return response

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
