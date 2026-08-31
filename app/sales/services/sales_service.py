from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    ProductsCode,
    SalesInvoiceDispatch,
    SalesInvoiceDispatchEvent,
    SalesInvoiceDispatchItem,
    SalesOperation,
    SalesOperationDetail,
    User,
)

STATUS_PENDING = "PENDING"
STATUS_PARTIAL = "PARTIAL"
STATUS_COMPLETE = "COMPLETE"
OPEN_STATUSES = (STATUS_PENDING, STATUS_PARTIAL)
ALL_STATUSES = (STATUS_PENDING, STATUS_PARTIAL, STATUS_COMPLETE)
QTY_EPSILON = 1e-9


class DispatchError(Exception):
    pass


def normalize_code(code):
    return (code or "").strip().upper()


def resolve_main_code(code):
    normalized = normalize_code(code)
    if not normalized:
        return ""
    mapping = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == normalized
    ).first()
    return normalize_code(mapping.main_code) if mapping else normalized


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def remaining_amount(item):
    return max(_as_float(item.invoiced_amount) - _as_float(item.dispatched_amount), 0.0)


def derive_line_status(invoiced_amount, dispatched_amount):
    invoiced = _as_float(invoiced_amount)
    dispatched = _as_float(dispatched_amount)
    if dispatched <= QTY_EPSILON:
        return STATUS_PENDING
    if dispatched + QTY_EPSILON >= invoiced:
        return STATUS_COMPLETE
    return STATUS_PARTIAL


def derive_header_status(items):
    if not items:
        return STATUS_PENDING
    statuses = [item.status for item in items]
    if all(status == STATUS_COMPLETE for status in statuses):
        return STATUS_COMPLETE
    if any(status != STATUS_PENDING for status in statuses):
        return STATUS_PARTIAL
    return STATUS_PENDING


def _invoice_filters():
    return [
        SalesOperation.operation_type == "BILL",
        or_(SalesOperation.canceled.is_(False), SalesOperation.canceled.is_(None)),
        or_(SalesOperation.wait.is_(False), SalesOperation.wait.is_(None)),
    ]


def find_sales_invoice(code):
    raw = (code or "").strip()
    if not raw:
        return None

    normalized = raw.upper()
    filters = _invoice_filters()

    invoice = (
        SalesOperation.query.filter(
            func.upper(func.trim(SalesOperation.document_no)) == normalized,
            *filters,
        )
        .order_by(SalesOperation.correlative.desc())
        .first()
    )
    if invoice:
        return invoice

    invoice = (
        SalesOperation.query.filter(
            func.upper(func.trim(SalesOperation.control_no)) == normalized,
            *filters,
        )
        .order_by(SalesOperation.correlative.desc())
        .first()
    )
    if invoice:
        return invoice

    if raw.isdigit():
        return SalesOperation.query.filter(
            SalesOperation.correlative == int(raw),
            *filters,
        ).first()

    return None


def get_dispatch(dispatch_id):
    return SalesInvoiceDispatch.query.get(dispatch_id)


def get_dispatch_items(dispatch_id):
    return (
        SalesInvoiceDispatchItem.query.filter_by(dispatch_id=dispatch_id)
        .order_by(SalesInvoiceDispatchItem.sales_line.asc())
        .all()
    )


def _invoice_details(invoice_correlative):
    return (
        SalesOperationDetail.query.filter_by(main_correlative=invoice_correlative)
        .order_by(SalesOperationDetail.line.asc())
        .all()
    )


def load_or_open_dispatch(invoice, user_code):
    existing = SalesInvoiceDispatch.query.filter_by(
        sales_operation_correlative=invoice.correlative
    ).first()
    if existing:
        return existing, False

    details = [
        detail
        for detail in _invoice_details(invoice.correlative)
        if normalize_code(detail.code_product)
    ]
    if not details:
        raise DispatchError("La factura no tiene productos para despachar.")

    now = datetime.now()
    dispatch = SalesInvoiceDispatch(
        sales_operation_correlative=invoice.correlative,
        document_no=invoice.document_no,
        client_code=invoice.client_code,
        client_name=invoice.client_name,
        emission_date=invoice.emission_date,
        status=STATUS_PENDING,
        loaded_by=user_code,
        loaded_at=now,
        updated_at=now,
    )
    db.session.add(dispatch)
    db.session.flush()

    for detail in details:
        invoiced = _as_float(detail.amount)
        db.session.add(
            SalesInvoiceDispatchItem(
                dispatch_id=dispatch.correlative,
                sales_line=detail.line,
                product_code=normalize_code(detail.code_product),
                product_description=detail.description_product,
                invoiced_amount=invoiced,
                dispatched_amount=0,
                status=derive_line_status(invoiced, 0),
            )
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = SalesInvoiceDispatch.query.filter_by(
            sales_operation_correlative=invoice.correlative
        ).first()
        if existing:
            return existing, False
        raise DispatchError("No se pudo registrar la factura para despacho.")
    return dispatch, True


def find_pending_item_for_product(dispatch_id, scanned_code):
    main_code = resolve_main_code(scanned_code)
    if not main_code:
        raise DispatchError("Debe escanear un codigo de producto.")

    items = get_dispatch_items(dispatch_id)
    matching = [
        item
        for item in items
        if normalize_code(item.product_code) == main_code
        or resolve_main_code(item.product_code) == main_code
    ]
    if not matching:
        raise DispatchError("El producto no pertenece a esta factura.")

    pending = [item for item in matching if remaining_amount(item) > QTY_EPSILON]
    if not pending:
        raise DispatchError("Este producto ya fue despachado por completo.")

    item = pending[0]
    return item, main_code, remaining_amount(item)


def confirm_dispatch_quantity(dispatch_id, item_id, quantity, user_code):
    dispatch = get_dispatch(dispatch_id)
    if not dispatch:
        raise DispatchError("No se encontro el despacho.")

    if not (user_code or "").strip():
        raise DispatchError("No se pudo identificar el usuario que despacha.")

    item = SalesInvoiceDispatchItem.query.get(item_id)
    if not item or item.dispatch_id != dispatch_id:
        raise DispatchError("No se encontro el producto en esta factura.")

    qty = _as_float(quantity)
    remaining = remaining_amount(item)
    if qty <= QTY_EPSILON:
        raise DispatchError("La cantidad a despachar debe ser mayor a cero.")
    if qty > remaining + QTY_EPSILON:
        raise DispatchError(
            f"La cantidad supera lo pendiente por entregar ({remaining:.2f})."
        )

    now = datetime.now()
    item.dispatched_amount = _as_float(item.dispatched_amount) + qty
    if item.dispatched_amount > _as_float(item.invoiced_amount):
        item.dispatched_amount = _as_float(item.invoiced_amount)
    item.status = derive_line_status(item.invoiced_amount, item.dispatched_amount)

    db.session.add(
        SalesInvoiceDispatchEvent(
            dispatch_id=dispatch_id,
            item_id=item.correlative,
            user_code=user_code.strip(),
            quantity=qty,
            created_at=now,
        )
    )

    items = get_dispatch_items(dispatch_id)
    dispatch.status = derive_header_status(items)
    dispatch.updated_at = now
    db.session.commit()
    return dispatch, item


def get_dispatch_participants(dispatch_id):
    first_at = func.min(SalesInvoiceDispatchEvent.created_at)
    rows = db.session.execute(
        select(
            SalesInvoiceDispatchEvent.item_id,
            SalesInvoiceDispatchEvent.user_code,
            User.description,
            func.sum(SalesInvoiceDispatchEvent.quantity).label("quantity"),
            first_at.label("first_at"),
        )
        .join(User, User.code == SalesInvoiceDispatchEvent.user_code)
        .where(SalesInvoiceDispatchEvent.dispatch_id == dispatch_id)
        .group_by(
            SalesInvoiceDispatchEvent.item_id,
            SalesInvoiceDispatchEvent.user_code,
            User.description,
        )
        .order_by(first_at.asc())
    ).all()

    participants = {}
    for row in rows:
        label = (row.description or "").strip() or row.user_code
        participants.setdefault(row.item_id, []).append((label, float(row.quantity)))
    return participants


def list_pending_dispatches(query_text="", status_filter="open"):
    remaining_expr = func.coalesce(
        SalesInvoiceDispatchItem.invoiced_amount
        - SalesInvoiceDispatchItem.dispatched_amount,
        0,
    )
    pending_lines_expr = func.sum(
        case((remaining_expr > QTY_EPSILON, 1), else_=0)
    )
    pending_qty_expr = func.sum(
        case((remaining_expr > 0, remaining_expr), else_=0)
    )

    stmt = (
        select(
            SalesInvoiceDispatch.correlative,
            SalesInvoiceDispatch.document_no,
            SalesInvoiceDispatch.client_code,
            SalesInvoiceDispatch.client_name,
            SalesInvoiceDispatch.emission_date,
            SalesInvoiceDispatch.status,
            SalesInvoiceDispatch.loaded_at,
            SalesInvoiceDispatch.updated_at,
            pending_lines_expr.label("pending_lines"),
            pending_qty_expr.label("pending_qty"),
            func.count(SalesInvoiceDispatchItem.correlative).label("total_lines"),
        )
        .select_from(SalesInvoiceDispatch)
        .outerjoin(
            SalesInvoiceDispatchItem,
            SalesInvoiceDispatchItem.dispatch_id == SalesInvoiceDispatch.correlative,
        )
        .group_by(
            SalesInvoiceDispatch.correlative,
            SalesInvoiceDispatch.document_no,
            SalesInvoiceDispatch.client_code,
            SalesInvoiceDispatch.client_name,
            SalesInvoiceDispatch.emission_date,
            SalesInvoiceDispatch.status,
            SalesInvoiceDispatch.loaded_at,
            SalesInvoiceDispatch.updated_at,
        )
        .order_by(SalesInvoiceDispatch.loaded_at.desc())
    )

    if status_filter == "open" or not status_filter:
        stmt = stmt.where(SalesInvoiceDispatch.status.in_(OPEN_STATUSES))
    elif status_filter in ALL_STATUSES:
        stmt = stmt.where(SalesInvoiceDispatch.status == status_filter)

    search = (query_text or "").strip()
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                SalesInvoiceDispatch.document_no.ilike(like),
                SalesInvoiceDispatch.client_name.ilike(like),
                SalesInvoiceDispatch.client_code.ilike(like),
            )
        )

    return db.session.execute(stmt).all()
