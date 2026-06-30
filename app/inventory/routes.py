from flask import (
    render_template,
    request,
    flash,
    redirect,
    url_for,
    Response,
    make_response,
    session,
    send_file,
    jsonify,
)
import json
import math
from io import BytesIO
from flask_login import login_required, current_user
from datetime import datetime
from app.inventory import inventory_bp
import pandas as pd
import xlwt

from app.reports.utils import render_pdf, generate_barcode
from app.inventory.services import inventory_service


@inventory_bp.route("/")
@login_required
def index():
    return render_template("index.html")


def _build_transfer_guide_steps():
    return [
        {
            "id": "select_order_type",
            "phase": "origin",
            "mode": "both",
            "title": "Definir el tipo de orden",
            "summary": "Selecciona si el traslado inicia con orden automática o manual.",
            "objective": "Elegir el flujo correcto según urgencia y disponibilidad del catálogo.",
            "actions": [
                "Usa orden automática cuando el sistema ya recomienda cantidades.",
                "Usa orden manual cuando necesites agregar productos específicos uno por uno.",
                "Verifica depósito origen y depósito destino antes de continuar.",
            ],
            "checkpoint": "Depósitos y motivo del traslado confirmados.",
            "screen_url": "inventory.index",
            "screen_label": "Panel de inventario",
        },
        {
            "id": "create_collection_order",
            "phase": "origin",
            "mode": "both",
            "title": "Emitir orden de recolección",
            "summary": "Genera la orden con los productos y cantidades a trasladar.",
            "objective": "Crear un documento de trabajo para el equipo de despacho.",
            "actions": [
                "En automática, revisa sugerencias de stock y confirma líneas.",
                "En manual, agrega códigos y ajusta cantidades antes de emitir.",
                "Guarda la orden y registra el correlativo para seguimiento.",
            ],
            "checkpoint": "Orden emitida en estado RECOLLECTION_ISSUED.",
            "screen_url": "inventory.auto_order_collection",
            "screen_label": "Orden automática",
        },
        {
            "id": "check_collection_order",
            "phase": "origin",
            "mode": "both",
            "title": "Chequear la recolección",
            "summary": "Confirma físicamente lo recolectado y corrige diferencias.",
            "objective": "Asegurar que la carga coincida con la orden emitida.",
            "actions": [
                "Escanea o busca cada producto de la orden.",
                "Ajusta cantidades contadas y documenta cualquier variación.",
                "Cierra el chequeo para dejar la operación lista para transporte.",
            ],
            "checkpoint": "Orden en estado RECOLLECTION_CHECKED.",
            "screen_url": "inventory.check_order",
            "screen_label": "Chequeo de orden",
        },
        {
            "id": "start_transfer",
            "phase": "transit",
            "mode": "both",
            "title": "Iniciar traslado",
            "summary": "Registra responsable de carga y salida de mercancía.",
            "objective": "Dejar trazabilidad del despacho y pasar a estado en tránsito.",
            "actions": [
                "Valida datos de la orden chequeada.",
                "Captura firma digital o responsable autorizado.",
                "Confirma inicio para mover la operación a IN_TRANSIT.",
            ],
            "checkpoint": "Traslado en estado IN_TRANSIT.",
            "screen_url": "inventory.start_transfer_operation",
            "screen_label": "Inicio de traslado",
        },
        {
            "id": "receive_transfer",
            "phase": "destination",
            "mode": "both",
            "title": "Recepcionar en depósito destino",
            "summary": "Cuenta lo recibido y procesa diferencias de recepción.",
            "objective": "Cerrar el ciclo del traslado con inventario actualizado.",
            "actions": [
                "Busca el correlativo en Recepción de traslado.",
                "Cuenta productos recibidos y registra diferencias cuando existan.",
                "Cierra la recepción para procesar inventario en destino.",
            ],
            "checkpoint": "Traslado en estado RECEIVED y reporte disponible.",
            "screen_url": "inventory.check_transfer_operation",
            "screen_label": "Recepción de traslado",
        },
    ]


@inventory_bp.route("/transfer-guide", methods=["GET"])
@login_required
def transfer_guide():
    guide_steps = _build_transfer_guide_steps()
    return render_template(
        "transfer_guide.html",
        guide_steps=guide_steps,
        flow_steps=TRANSFER_FLOW_STEPS,
        generated_at=datetime.now(),
    )


@inventory_bp.route("/transfer-guide/pdf", methods=["GET"])
@login_required
def transfer_guide_pdf():
    all_steps = _build_transfer_guide_steps()
    completed_steps_raw = (request.args.get("completed_steps") or "").strip()
    requested_completed_ids = [
        step_id.strip() for step_id in completed_steps_raw.split(",") if step_id.strip()
    ]

    seen_ids = set()
    requested_completed_ids = [
        step_id
        for step_id in requested_completed_ids
        if not (step_id in seen_ids or seen_ids.add(step_id))
    ]

    valid_ids = {step["id"] for step in all_steps}
    requested_completed_ids = [
        step_id for step_id in requested_completed_ids if step_id in valid_ids
    ]

    guide_steps = [
        step for step in all_steps if step["id"] in set(requested_completed_ids)
    ]

    return Response(
        render_pdf(
            "reports/transfer_guide_pdf.html",
            {
                "guide_steps": guide_steps,
                "completed_count": len(guide_steps),
                "total_count": len(all_steps),
                "flow_steps": TRANSFER_FLOW_STEPS,
                "generated_at": datetime.now(),
                "generated_by": current_user,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={"Content-Disposition": "inline; filename=guia_traslados_inventario.pdf"},
    )


def _build_collection_exam_questions():
    return [
        {
            "id": "q1",
            "prompt": "Antes de emitir una orden de recolección, ¿qué validación es obligatoria?",
            "options": [
                {"value": "a", "label": "Solo confirmar el documento de transporte"},
                {"value": "b", "label": "Verificar depósito origen, depósito destino y tipo de orden"},
                {"value": "c", "label": "Imprimir etiquetas de bultos"},
            ],
            "correct_answer": "b",
            "weight": 10,
        },
        {
            "id": "q2",
            "prompt": "¿Qué estado refleja una orden emitida y pendiente de chequeo?",
            "options": [
                {"value": "a", "label": "IN_TRANSIT"},
                {"value": "b", "label": "RECEIVED"},
                {"value": "c", "label": "RECOLLECTION_ISSUED"},
            ],
            "correct_answer": "c",
            "weight": 10,
        },
        {
            "id": "q3",
            "prompt": "Durante el chequeo de recolección, ¿cuál es la acción correcta?",
            "options": [
                {"value": "a", "label": "Ignorar diferencias y cerrar"},
                {"value": "b", "label": "Contar productos y registrar diferencias"},
                {"value": "c", "label": "Cambiar depósitos para cuadrar stock"},
            ],
            "correct_answer": "b",
            "weight": 10,
        },
        {
            "id": "q4",
            "prompt": "¿Cuál es el estado esperado al finalizar correctamente la práctica de orden de recolección?",
            "options": [
                {"value": "a", "label": "RECOLLECTION_CHECKED"},
                {"value": "b", "label": "IN_TRANSIT"},
                {"value": "c", "label": "RECEIVED"},
            ],
            "correct_answer": "a",
            "weight": 10,
        },
    ]


def _to_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _evaluate_collection_practice_exam(form_data):
    questions = _build_collection_exam_questions()

    quiz_points = 0
    quiz_total_points = 0
    quiz_results = []

    for question in questions:
        given_answer = (form_data.get(question["id"]) or "").strip().lower()
        is_correct = given_answer == question["correct_answer"]
        weight = int(question.get("weight", 0))
        quiz_total_points += weight
        if is_correct:
            quiz_points += weight

        quiz_results.append(
            {
                "id": question["id"],
                "prompt": question["prompt"],
                "given_answer": given_answer,
                "correct_answer": question["correct_answer"],
                "is_correct": is_correct,
                "weight": weight,
            }
        )

    order_mode = (form_data.get("order_mode") or "").strip().lower()
    collected_lines = _to_positive_int(form_data.get("collected_lines"))
    checked_lines = _to_positive_int(form_data.get("checked_lines"))
    final_status = (form_data.get("final_status") or "").strip().upper()
    procedure_confirmed = bool(form_data.get("procedure_confirmed"))

    practice_checks = [
        {
            "label": "Seleccionó tipo de orden válido (manual o automática)",
            "ok": order_mode in {"manual", "auto"},
            "weight": 10,
        },
        {
            "label": "Registró líneas recolectadas y chequeadas", 
            "ok": collected_lines > 0 and checked_lines > 0,
            "weight": 10,
        },
        {
            "label": "La cantidad chequeada no supera la recolectada",
            "ok": collected_lines >= checked_lines > 0,
            "weight": 10,
        },
        {
            "label": "Estado final reportado como RECOLLECTION_CHECKED",
            "ok": final_status == FLOW_RECOLLECTION_CHECKED,
            "weight": 10,
        },
        {
            "label": "Confirmó cumplimiento del procedimiento",
            "ok": procedure_confirmed,
            "weight": 10,
        },
    ]

    practice_total_points = sum(item["weight"] for item in practice_checks)
    practice_points = sum(item["weight"] for item in practice_checks if item["ok"])

    total_points = quiz_points + practice_points
    max_points = quiz_total_points + practice_total_points
    score_pct = round((total_points / max_points) * 100, 2) if max_points else 0.0
    is_approved = score_pct >= 75

    return {
        "submitted_at": datetime.now(),
        "trainee_name": (form_data.get("trainee_name") or "").strip(),
        "order_mode": order_mode,
        "collected_lines": collected_lines,
        "checked_lines": checked_lines,
        "differences_detected": (form_data.get("differences_detected") or "").strip().lower(),
        "final_status": final_status,
        "notes": (form_data.get("notes") or "").strip(),
        "quiz_results": quiz_results,
        "practice_checks": practice_checks,
        "quiz_points": quiz_points,
        "practice_points": practice_points,
        "total_points": total_points,
        "max_points": max_points,
        "score_pct": score_pct,
        "approved": is_approved,
    }


@inventory_bp.route("/collection-practice-exam", methods=["GET", "POST"])
@login_required
def collection_practice_exam():
    questions = _build_collection_exam_questions()
    result = None

    if request.method == "POST":
        result = _evaluate_collection_practice_exam(request.form)
        if not result["trainee_name"]:
            result["trainee_name"] = current_user.description or current_user.code

    return render_template(
        "collection_practice_exam.html",
        questions=questions,
        result=result,
        generated_at=datetime.now(),
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

MANUAL_ORDER_CART_SESSION_KEY = "manual_order_cart"


def _get_manual_order_cart_scope(store_origin, store_dst):
    origin_code = inventory_service.normalize_code(store_origin)
    destination_code = inventory_service.normalize_code(store_dst)
    if not origin_code or not destination_code:
        return ""
    return f"{origin_code}::{destination_code}"


def _get_manual_order_cart_map(store_origin, store_dst):
    scope = _get_manual_order_cart_scope(store_origin, store_dst)
    if not scope:
        return {}

    all_carts = session.get(MANUAL_ORDER_CART_SESSION_KEY, {}) or {}
    user_carts = all_carts.get(current_user.code, {}) or {}
    scoped_cart = user_carts.get(scope, {}) or {}

    normalized_cart = {}
    for product_code, quantity in scoped_cart.items():
        normalized_code = inventory_service.normalize_code(product_code)
        try:
            qty_value = float(quantity)
        except (TypeError, ValueError):
            qty_value = 0

        if normalized_code and qty_value > 0:
            normalized_cart[normalized_code] = normalized_cart.get(normalized_code, 0) + qty_value

    return normalized_cart


def _set_manual_order_cart_map(store_origin, store_dst, cart_map):
    scope = _get_manual_order_cart_scope(store_origin, store_dst)
    if not scope:
        return

    clean_cart = {}
    for product_code, quantity in (cart_map or {}).items():
        normalized_code = inventory_service.normalize_code(product_code)
        try:
            qty_value = float(quantity)
        except (TypeError, ValueError):
            qty_value = 0

        if normalized_code and qty_value > 0:
            clean_cart[normalized_code] = qty_value

    all_carts = session.get(MANUAL_ORDER_CART_SESSION_KEY, {}) or {}
    user_carts = all_carts.get(current_user.code, {}) or {}

    if clean_cart:
        user_carts[scope] = clean_cart
    else:
        user_carts.pop(scope, None)

    if user_carts:
        all_carts[current_user.code] = user_carts
    else:
        all_carts.pop(current_user.code, None)

    session[MANUAL_ORDER_CART_SESSION_KEY] = all_carts


def _build_manual_order_cart_context(store_origin, store_dst, message="", message_category="info"):
    cart_map = _get_manual_order_cart_map(store_origin, store_dst)
    cart_context = inventory_service.get_manual_order_cart_context(store_origin, store_dst, cart_map)
    cart_context["store_origin"] = store_origin
    cart_context["store_dst"] = store_dst
    cart_context["message"] = message
    cart_context["message_category"] = message_category
    return cart_context


@inventory_bp.route("/listado-productos", methods=["GET"])
@login_required
def listado_productos():
    df = inventory_service.build_products_list_df()
    columns = [
        "code",
        "description",
        "referenc",
        "mark",
        "model",
        "department",
        "buy_tax",
        "sale_tax",
        "unit",
        "unitary_cost",
        "maximum_price",
        "offer_price",
        "higher_price",
        "minimum_price",
        "coin",
        "serialized",
        "use_lots",
    ]
    if df.empty:
        products = []
    else:
        df = df.reindex(columns=columns)
        products = df.to_dict(orient="records")

    return render_template("inventory/listado.html", products=products, columns=columns)


@inventory_bp.route("/exportar-excel", methods=["GET"])
@login_required
def exportar_excel_productos():
    df = inventory_service.build_products_list_df()

    column_order = [
        "code",
        "description",
        "referenc",
        "mark",
        "model",
        "department",
        "buy_tax",
        "sale_tax",
        "unit",
        "unitary_cost",
        "maximum_price",
        "offer_price",
        "higher_price",
        "minimum_price",
        "coin",
        "serialized",
        "use_lots",
    ]

    if df.empty:
        df = pd.DataFrame(columns=column_order)
    else:
        df = df.reindex(columns=column_order)

    text_cols = [
        "code",
        "description",
        "referenc",
        "mark",
        "model",
        "unit",
        "coin",
        "serialized",
        "use_lots",
        "department",
        "buy_tax",
        "sale_tax",
    ]
    money_cols = [
        "unitary_cost",
        "maximum_price",
        "offer_price",
        "higher_price",
        "minimum_price",
    ]

    df_excel = df.copy()

    for col in text_cols:
        if col in df_excel.columns:
            df_excel[col] = df_excel[col].fillna("").astype(str)
    for col in money_cols:
        if col in df_excel.columns:
            df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce").fillna(0.0)

    # Construcción de XLS (Excel 97-2003) con xlwt
    output = BytesIO()
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Productos")

    header_style = xlwt.easyxf(
        "font: bold on; pattern: pattern solid, fore_colour gray25;"
    )
    text_style = xlwt.easyxf(num_format_str="@")
    number_style = xlwt.easyxf(num_format_str="#,##0.00")

    # Encabezados
    for col_idx, col_name in enumerate(df_excel.columns):
        ws.write(0, col_idx, col_name, header_style)

    col_index = {name: i for i, name in enumerate(df_excel.columns)}
    money_set = set(money_cols)

    # Filas de datos con tipos estrictos
    for row_idx, row in enumerate(df_excel.itertuples(index=False), start=1):
        for col_name, col_idx in col_index.items():
            val = getattr(row, col_name)
            if col_name in money_set:
                num = float(val) if val is not None and val != "" else 0.0
                ws.write(row_idx, col_idx, num, number_style)
            else:
                s = "" if val is None else str(val)
                ws.write(row_idx, col_idx, s, text_style)

    # Autoajuste básico de ancho
    for i, col in enumerate(df_excel.columns):
        values = [str(v) for v in df_excel[col].head(500).tolist()]
        max_len = max([len(str(col))] + [len(v) for v in values])
        ws.col(i).width = min(max_len + 2, 60) * 256

    wb.save(output)
    output.seek(0)
    filename = "PRODUCTS.xls"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.ms-excel",
    )


@inventory_bp.route("/auto_order_collection", methods=["GET"])
@login_required
def auto_order_collection():
    new_order_id = request.args.get("new_order_id")
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")

    data = inventory_service.get_auto_order_collection_data(store_origin, store_dst)

    if store_origin and store_dst and store_origin == store_dst:
        flash("El depósito origen y destino no pueden ser el mismo.", "warning")
        return render_template(
            "auto_order_collection.html",
            store_origin=None,
            store_dst=None,
            store_origin_name="",
            store_dst_name="",
            products=[],
            departments=[],
            marks=[],
            stores=data["stores"],
            new_order_id=new_order_id,
        )

    # Si no hay selección de depósitos, solo mostramos el formulario
    if not store_origin or not store_dst:
        return render_template(
            "auto_order_collection.html",
            store_origin=store_origin,
            store_dst=store_dst,
            store_origin_name=data["store_origin_obj"].description if data["store_origin_obj"] else "",
            store_dst_name=data["store_dst_obj"].description if data["store_dst_obj"] else "",
            products=[],
            departments=[],
            marks=[],
            stores=data["stores"],
            new_order_id=new_order_id,
        )

    return render_template(
        "auto_order_collection.html",
        store_origin=store_origin,
        store_dst=store_dst,
        store_origin_name=data["store_origin_obj"].description if data["store_origin_obj"] else "",
        store_dst_name=data["store_dst_obj"].description if data["store_dst_obj"] else "",
        products=data["products"],
        departments=data["departments"],
        marks=data["marks"],
        stores=data["stores"],
        new_order_id=new_order_id,
    )


@inventory_bp.route("/auto_order_collection/save", methods=["POST"])
@login_required
def save_auto_order_collection():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")

    if not store_origin or not store_dst:
        flash("Debes seleccionar depósito origen y destino.", "warning")
        return redirect(url_for("inventory.auto_order_collection"))

    if store_origin == store_dst:
        flash("El depósito origen y destino no pueden ser el mismo.", "warning")
        return redirect(
            url_for(
                "inventory.auto_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )

    store_origen_obj = inventory_service.get_store_by_code(store_origin)
    store_dst_obj = inventory_service.get_store_by_code(store_dst)

    if not store_origen_obj or not store_dst_obj:
        flash("Depósitos inválidos.", "error")
        return redirect(url_for("inventory.index"))

    selected_items = []
    # Recopilar items seleccionados de forma compacta
    for key, value in request.form.items():
        if value == "selected":
            try:
                qty = float(request.form.get(f"qty_{key}", 0))
                if qty > 0:
                    selected_items.append({"code": key, "quantity": qty})
            except ValueError:
                continue

    if not selected_items:
        flash("No se han seleccionado productos", "warning")
        return redirect(
            url_for(
                "inventory.auto_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )

    try:
        document_no = inventory_service.create_order_collection_operation(
            store_origin, store_dst, selected_items, "Automatico", current_user.code
        )
        inventory_service.commit_session()
        inventory_service.register_flow_step1(document_no, current_user.code)
        flash(f"Operación #{document_no} guardada correctamente.", "success")

        # HTMX: redirigir a la vista y abrir el PDF en nueva pestaña
        if request.headers.get("HX-Request"):
            resp = make_response("", 200)
            resp.headers["HX-Redirect"] = url_for(
                "inventory.auto_order_collection", new_order_id=document_no
            )
            resp.headers["HX-Trigger"] = json.dumps(
                {
                    "open-pdf": {
                        "url": url_for(
                            "inventory.order_collection_report", order_id=document_no
                        )
                    }
                }
            )
            return resp

        # Flujo normal: redirigir directamente al PDF (abre en nueva pestaña por target del navegador)
        return redirect(
            url_for("inventory.order_collection_report", order_id=document_no)
        )

    except Exception as e:
        inventory_service.rollback_session()
        print(f"Error crítico: {e}")
        flash(f"Error: {str(e)}", "error")
        return redirect(
            url_for(
                "inventory.auto_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )


@inventory_bp.route("/manual_order_collection", methods=["GET"])
@login_required
def manual_order_collection():
    stores = inventory_service.get_stores_ordered_by_description()
    new_order_id = request.args.get("new_order_id")
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    selected_mark = request.args.get("mark", "")
    selected_department = request.args.get("department", "")
    selected_stock_filter = request.args.get("stock", "with_stock")
    selected_product_code = request.args.get("product_code", "")

    if store_origin and store_dst and store_origin == store_dst:
        flash("El depósito origen y destino no pueden ser el mismo.", "warning")
        store_origin = None
        store_dst = None

    store_origin_obj = inventory_service.get_store_by_code(store_origin) if store_origin else None
    store_dst_obj = inventory_service.get_store_by_code(store_dst) if store_dst else None

    products = []
    total_products = 0
    total_pages = 1
    current_page = 1
    marks = []
    departments = []

    if store_origin and store_dst:
        marks, departments = inventory_service.get_manual_order_filter_options(store_origin)
        products, total_products, total_pages, current_page = inventory_service.search_products_for_manual_order(
            store_origin=store_origin,
            query=query,
            page=page,
            per_page=10,
            mark_code=selected_mark,
            department_code=selected_department,
            stock_filter=selected_stock_filter,
            store_dst=store_dst,
        )

    selected_product_detail = inventory_service.get_manual_order_product_detail_data(
        selected_product_code,
        store_origin,
        store_dst,
    )
    if selected_product_detail is None and products:
        selected_product_detail = inventory_service.get_manual_order_product_detail_data(
            products[0].code,
            store_origin,
            store_dst,
        )

    manual_order_cart_context = _build_manual_order_cart_context(store_origin, store_dst)

    return render_template(
        "manual_order_collection.html",
        stores=stores,
        store_origin=store_origin,
        store_dst=store_dst,
        products=products,
        total_products=total_products,
        total_pages=total_pages,
        page=current_page,
        query=query,
        selected_mark=selected_mark,
        selected_department=selected_department,
        selected_stock_filter=selected_stock_filter,
        marks=marks,
        departments=departments,
        selected_product_detail=selected_product_detail,
        store_origin_name=store_origin_obj.description if store_origin_obj else "",
        store_dst_name=store_dst_obj.description if store_dst_obj else "",
        new_order_id=new_order_id,
        manual_order_cart_context=manual_order_cart_context,
    )


@inventory_bp.route("/manual_order_collection/cart", methods=["GET"])
@login_required
def manual_order_cart():
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    cart_context = _build_manual_order_cart_context(store_origin, store_dst)
    return render_template("partials/manual_order_cart.html", **cart_context)


@inventory_bp.route("/manual_order_collection/cart/add", methods=["POST"])
@login_required
def manual_order_cart_add():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")
    product_code = request.form.get("product_code")
    quantity = request.form.get("quantity", type=float)

    if not store_origin or not store_dst:
        cart_context = _build_manual_order_cart_context(
            store_origin,
            store_dst,
            message="Selecciona depósitos origen y destino antes de agregar productos.",
            message_category="warning",
        )
        return render_template("partials/manual_order_cart.html", **cart_context)

    if not product_code:
        cart_context = _build_manual_order_cart_context(
            store_origin,
            store_dst,
            message="Selecciona un producto válido para agregar.",
            message_category="warning",
        )
        return render_template("partials/manual_order_cart.html", **cart_context)

    if quantity is None or quantity <= 0:
        cart_context = _build_manual_order_cart_context(
            store_origin,
            store_dst,
            message="La cantidad debe ser mayor a cero.",
            message_category="warning",
        )
        return render_template("partials/manual_order_cart.html", **cart_context)

    main_code = inventory_service.resolve_main_code(product_code)
    cart_map = _get_manual_order_cart_map(store_origin, store_dst)
    cart_map[main_code] = float(cart_map.get(main_code, 0)) + float(quantity)
    _set_manual_order_cart_map(store_origin, store_dst, cart_map)

    cart_context = _build_manual_order_cart_context(
        store_origin,
        store_dst,
        message="Producto agregado a la orden.",
        message_category="success",
    )
    return render_template("partials/manual_order_cart.html", **cart_context)


@inventory_bp.route("/manual_order_collection/cart/update", methods=["POST"])
@login_required
def manual_order_cart_update():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")
    product_code = inventory_service.resolve_main_code(request.form.get("product_code"))
    quantity = request.form.get("quantity", type=float)

    cart_map = _get_manual_order_cart_map(store_origin, store_dst)
    if product_code in cart_map:
        if quantity is None or quantity <= 0:
            cart_map.pop(product_code, None)
        else:
            cart_map[product_code] = float(quantity)
        _set_manual_order_cart_map(store_origin, store_dst, cart_map)

    cart_context = _build_manual_order_cart_context(store_origin, store_dst)
    return render_template("partials/manual_order_cart.html", **cart_context)


@inventory_bp.route("/manual_order_collection/cart/remove", methods=["POST"])
@login_required
def manual_order_cart_remove():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")
    product_code = inventory_service.resolve_main_code(request.form.get("product_code"))

    cart_map = _get_manual_order_cart_map(store_origin, store_dst)
    cart_map.pop(product_code, None)
    _set_manual_order_cart_map(store_origin, store_dst, cart_map)

    cart_context = _build_manual_order_cart_context(store_origin, store_dst)
    return render_template("partials/manual_order_cart.html", **cart_context)


@inventory_bp.route("/manual_order_collection/cart/clear", methods=["POST"])
@login_required
def manual_order_cart_clear():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")
    _set_manual_order_cart_map(store_origin, store_dst, {})

    cart_context = _build_manual_order_cart_context(
        store_origin,
        store_dst,
        message="Orden manual limpiada.",
        message_category="info",
    )
    return render_template("partials/manual_order_cart.html", **cart_context)


@inventory_bp.route("/manual_order_collection/search_results", methods=["GET"])
@login_required
def manual_order_search_results():
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    selected_mark = request.args.get("mark", "")
    selected_department = request.args.get("department", "")
    selected_stock_filter = request.args.get("stock", "with_stock")

    products, total_products, total_pages, current_page = inventory_service.search_products_for_manual_order(
        store_origin=store_origin,
        query=query,
        page=page,
        per_page=10,
        mark_code=selected_mark,
        department_code=selected_department,
        stock_filter=selected_stock_filter,
        store_dst=store_dst,
    )

    return render_template(
        "partials/manual_order_search_results.html",
        products=products,
        total_products=total_products,
        total_pages=total_pages,
        page=current_page,
        query=query,
        selected_mark=selected_mark,
        selected_department=selected_department,
        selected_stock_filter=selected_stock_filter,
        store_origin=store_origin,
        store_dst=store_dst,
    )


@inventory_bp.route("/manual_order_collection/product_lookup", methods=["GET"])
@login_required
def manual_order_product_lookup():
    store_origin = request.args.get("store_origin")
    code = request.args.get("code")
    entered_code = inventory_service.normalize_code(code)
    main_code = inventory_service._resolver_main_code(code)
    product = inventory_service.get_product_for_manual_order(main_code, store_origin)

    if not product or float(product.stock_origin or 0) <= 0:
        return jsonify({"ok": False, "message": "Producto no encontrado o sin stock en origen."}), 404

    return jsonify(
        {
            "ok": True,
            "product": {
                "code": product.code,
                "entered_code": entered_code,
                "main_code": main_code,
                "resolved_from_alternate": bool(entered_code and entered_code != main_code),
                "description": product.description or "",
                "unit_description": product.unit_description or "",
                "mark_description": product.mark_description or "",
                "department_description": product.department_description or "",
                "stock_origin": float(product.stock_origin or 0),
            },
        }
    )


@inventory_bp.route("/manual_order_collection/products", methods=["GET"])
@login_required
def manual_order_products_modal():
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)
    products, total_products, total_pages, current_page = inventory_service.search_products_for_manual_order(
        store_origin, query, page=page, per_page=10
    )
    return render_template(
        "partials/manual_order_product_modal.html",
        products=products,
        query=query,
        store_origin=store_origin,
        store_dst=store_dst,
        page=current_page,
        total_pages=total_pages,
        total_products=total_products,
    )


@inventory_bp.route("/manual_order_collection/product_detail", methods=["GET"])
@login_required
def manual_order_product_detail():
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    product_code = request.args.get("product_code")

    detail_data = inventory_service.get_manual_order_product_detail_data(
        product_code, store_origin, store_dst
    )

    if detail_data is None:
        has_product_code = bool((product_code or "").strip())
        message = (
            "Producto no encontrado para el código leído."
            if has_product_code
            else "Selecciona un producto para ver su detalle."
        )
        if has_product_code:
            flash(message, "warning")

        return render_template(
            "partials/manual_order_product_detail.html",
            product_detail=None,
            error_message=(None if has_product_code else message),
            store_origin=store_origin,
            store_dst=store_dst,
            store_origin_code=store_origin,
            store_dst_code=store_dst,
        )

    store_origin_obj = inventory_service.get_store_by_code(store_origin) if store_origin else None
    store_dst_obj = inventory_service.get_store_by_code(store_dst) if store_dst else None

    return render_template(
        "partials/manual_order_product_detail.html",
        product_detail=detail_data,
        store_origin=store_origin_obj,
        store_dst=store_dst_obj,
        store_origin_code=store_origin,
        store_dst_code=store_dst,
    )


@inventory_bp.route("/manual_order_collection/save", methods=["POST"])
@login_required
def save_manual_order_collection():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")
    product_codes = request.form.getlist("product_code[]")
    quantities = request.form.getlist("quantity[]")

    if not product_codes or not quantities:
        cart_map = _get_manual_order_cart_map(store_origin, store_dst)
        product_codes = list(cart_map.keys())
        quantities = [str(cart_map[code]) for code in product_codes]

    selected_items = [
        {"code": code, "quantity": quantity}
        for code, quantity in zip(product_codes, quantities)
    ]

    try:
        document_no = inventory_service.create_order_collection_operation(
            store_origin, store_dst, selected_items, "Manual", current_user.code
        )
        inventory_service.commit_session()
        inventory_service.register_flow_step1(document_no, current_user.code)
        _set_manual_order_cart_map(store_origin, store_dst, {})
        flash(f"Orden manual #{document_no} guardada correctamente.", "success")

        if request.headers.get("HX-Request"):
            resp = make_response("", 200)
            resp.headers["HX-Redirect"] = url_for(
                "inventory.manual_order_collection", new_order_id=document_no
            )
            resp.headers["HX-Trigger"] = json.dumps(
                {
                    "open-pdf": {
                        "url": url_for(
                            "inventory.order_collection_report", order_id=document_no
                        )
                    }
                }
            )
            return resp

        return redirect(
            url_for("inventory.order_collection_report", order_id=document_no)
        )
    except Exception as e:
        inventory_service.rollback_session()
        flash(f"Error: {str(e)}", "error")
        return redirect(
            url_for(
                "inventory.manual_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )


@inventory_bp.route("/order_collection/report/<int:order_id>")
@login_required
def order_collection_report(order_id):
    flow = inventory_service.get_inventory_operation_flow(order_id)
    is_checked = bool(flow and flow.get("current_status") == FLOW_RECOLLECTION_CHECKED)

    user = current_user
    order = inventory_service.get_order_for_report(order_id)
    sorted_details = inventory_service.sort_details_by_location(order.inventory_operation_details)
    package_count = len(inventory_service.get_operation_packages(order.correlative))

    barcode_base64 = generate_barcode(order.correlative)

    template_path = "reports/checked_order_collection_pdf.html" if is_checked else "reports/order_collection_pdf.html"
    filename = f"orden_chequeada_{order.correlative}.pdf" if is_checked else f"orden_{order.correlative}.pdf"

    return Response(
        render_pdf(
            template_path,
            {
                "order": order,
                "title": f"Orden de Recolección Automatica {order.correlative}",
                "now": datetime.now(),
                "barcode_base64": barcode_base64,
                "user": user,
                "sorted_details": sorted_details,
                "package_count": package_count,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={filename}"
        },
    )


@inventory_bp.route("/order_collection/checked_report/<int:order_id>")
@login_required
def checked_order_collection_report(order_id):
    user = current_user
    order = inventory_service.get_order_for_report(order_id)
    sorted_details = inventory_service.sort_details_by_location(order.inventory_operation_details)
    package_count = len(inventory_service.get_operation_packages(order.correlative))

    barcode_base64 = generate_barcode(order.correlative)

    return Response(
        render_pdf(
            "reports/checked_order_collection_pdf.html",
            {
                "order": order,
                "title": f"Orden de Recoleccion Chequeada {order.correlative}",
                "now": datetime.now(),
                "barcode_base64": barcode_base64,
                "user": user,
                "sorted_details": sorted_details,
                "package_count": package_count,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=orden_chequeada_{order.correlative}.pdf"
        },
    )


@inventory_bp.route("/check_order", methods=["GET", "POST"])
@login_required
def check_order():
    order_details = None
    error = None

    if request.method == "POST":
        order_id = request.form.get("order_id", type=int)
        if not order_id:
            error = "Debe ingresar un ID de orden válido."
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        # Buscar la operación y validar que sea un traslado procesado
        order_entity = inventory_service.get_order_by_id(order_id)
        if not order_entity or order_entity.operation_type != "TRANSFER" or not order_entity.wait:
            error = f"No se encontró la orden con ID {order_id}"
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        flow = inventory_service.get_inventory_operation_flow(order_id)
        if not flow:
            error = f"La orden {order_id} no tiene bitácora de flujo registrada."
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )
        if flow["current_status"] != FLOW_RECOLLECTION_ISSUED:
            error = (
                f"La orden {order_id} no está disponible para chequeo. "
                f"Estado actual: {flow['current_status']}."
            )
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        results = inventory_service.get_check_order_rows(order_id)

        if not results:
            error = f"No se encontró la orden con ID {order_id} o no contiene detalles."
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        # El primer resultado contiene la información de cabecera
        order_header = results[0]
        order_details = results

        persisted_counts = inventory_service.get_user_checking_progress_map(
            order_id,
            current_user.code,
        )
        counted_by_code = {}
        for row in order_details:
            normalized_code = inventory_service.normalize_code(row.code_product)
            if normalized_code in persisted_counts:
                counted_by_code[normalized_code] = float(persisted_counts[normalized_code])

        # Abrir automaticamente un bulto inicial para evitar friccion al comenzar el chequeo.
        open_package = inventory_service.get_open_package(order_id)
        if not open_package:
            try:
                inventory_service.open_package_for_operation(order_id, current_user.code)
                inventory_service.commit_session()
                flash("Se abrió automáticamente un bulto para iniciar el chequeo.", "info")
            except Exception as exc:
                inventory_service.rollback_session()
                flash(f"No se pudo abrir el bulto inicial automáticamente: {exc}", "warning")

        return render_template(
            "check_order_collection.html",
            order=order_header,
            details=order_details,
            counted_by_code=counted_by_code,
            error=error,
        )

    return render_template(
        "check_order_collection.html", order=None, details=[], counted_by_code={}, error=None
    )


@inventory_bp.route("/search_product", methods=["GET"])
@login_required
def search_product():
    code_product = inventory_service.normalize_code(request.args.get("code-product"))
    order_id = request.args.get("order_id", type=int)

    if not code_product or not order_id:
        return render_template(
            "partials/check_order_product_modal.html",
            item=None,
            product_description="",
            unit_description="",
            order=None,
        )

    main_code = inventory_service.resolve_main_code(code_product)

    detail = inventory_service.find_detail_by_codes(order_id, [main_code])

    if not detail:
        # Producto no encontrado en la orden, validar existencia en catálogo
        product = inventory_service.get_product_by_code(main_code)
        if not product:
            error_payload = {
                "product-error": {
                    "message": "El producto ingresado no existe en la base de datos.",
                    "focus_id": "code-product",
                }
            }
            return Response(
                "",
                status=404,
                headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
            )

        # Obtener la orden
        order = inventory_service.get_order_by_id(order_id)
        if not order:
            return render_template(
                "partials/check_order_product_modal.html",
                item=None,
                product_description="Orden no encontrada.",
                unit_description="",
                order=None,
                is_new=False,
            )

        # Obtener unidad principal
        pu = inventory_service.get_main_unit_for_product(main_code)
        if not pu:
            return render_template(
                "partials/check_order_product_modal.html",
                item=None,
                product_description="Unidad principal no encontrada para el producto.",
                unit_description="",
                order=None,
                is_new=False,
            )

        unit = inventory_service.get_unit_by_code(pu.unit)

        # Obtener cantidad en depósito origen
        stock = inventory_service.get_stock_for_product_store(main_code, order.store)
        stock_amount = stock.stock if stock else 0.0

        # Renderizar modal para agregar
        return render_template(
            "partials/check_order_product_modal.html",
            item=None,
            product_description=product.description,
            unit_description=unit.description if unit else "Desconocida",
            order=order,
            is_new=True,
            main_code=main_code,
            stock_amount=stock_amount,
        )

    # Obtener descripción del producto y unidad
    actual_code = inventory_service.normalize_code(detail.code_product)
    product = inventory_service.get_product_by_code(actual_code)
    unit = inventory_service.get_unit_by_correlative(detail.unit)

    # Obtener cantidad en depósito origen para validación de conteo
    stock = inventory_service.get_stock_for_product_store(actual_code, detail.store)
    stock_amount = stock.stock if stock else 0.0

    # Renderizar el modal con datos
    return render_template(
        "partials/check_order_product_modal.html",
        item=detail,
        product_description=product.description if product else "Desconocido",
        unit_description=unit.description if unit else "Desconocida",
        order=inventory_service.get_order_by_id(order_id),
        stock_amount=stock_amount,
    )


@inventory_bp.route("/add_product_to_order", methods=["POST"])
@login_required
def add_product_to_order():
    order_id = request.form.get("order_id", type=int)
    code_product = inventory_service.normalize_code(request.form.get("code_product"))


    if not order_id or not code_product:
    
        error_payload = {
            "product-error": {
                "message": "Error: datos incompletos para agregar el producto.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    main_code = inventory_service.resolve_main_code(code_product)

    

    # Verificar si ya existe
    detail = inventory_service.find_detail_by_codes(order_id, [main_code, code_product])

    if detail:
        print("Producto ya agregado")
        error_payload = {
            "product-error": {
                "message": "Producto ya agregado en la orden.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=409, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    product, order, pu, created_payload, error_code = inventory_service.add_product_to_order(
        order_id, main_code
    )

    if error_code == "PRODUCT_NOT_FOUND":
        error_payload = {
            "product-error": {
                "message": "El producto ingresado no existe en la base de datos.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=404, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    if error_code == "ORDER_NOT_FOUND":
        error_payload = {
            "product-error": {
                "message": "Orden no encontrada. Vuelve a cargar el correlativo.",
                "focus_id": "order_id",
            }
        }
        return Response(
            "", status=404, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    if error_code == "MAIN_UNIT_NOT_FOUND":
        error_payload = {
            "product-error": {
                "message": "Unidad principal no encontrada para el producto.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )
    if error_code == "NO_STOCK":
        error_payload = {
            "product-error": {
                "message": "No hay stock disponible en el depósito de origen para este producto.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )
    try:
        if error_code:
            raise RuntimeError(error_code)
        unit = created_payload["unit"] if created_payload else None
        new_detail = created_payload["detail"] if created_payload else None

        trigger_payload = {"product-added": {"code_product": main_code}}
        return Response(
            render_template(
                "partials/product_row.html",
                item=new_detail,
                product_description=product.description,
                unit_description=unit.description if unit else "Desconocida",
                order=order,
            ),
            headers={"HX-Trigger": json.dumps(trigger_payload)},
        )

    except Exception as e:
        inventory_service.rollback_session()
        error_payload = {
            "product-error": {
                "message": "Error al agregar producto. Intente nuevamente.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=500, headers={"HX-Trigger": json.dumps(error_payload)}
        )


@inventory_bp.route("/update_counted_amount", methods=["POST"])
@login_required
def update_counted_amount():
    order_id = request.form.get("order_id", type=int)
    code_product = inventory_service.normalize_code(request.form.get("code_product"))
    counted_amount = request.form.get("counted_amount", type=float)

    if not order_id or not code_product or counted_amount is None:
        return "Error: Datos incompletos."

    # Actualizar el detalle (por ahora, solo en memoria, pero luego en BD)
    # Para simplificar, devolver HTML actualizado para la fila
    detail = inventory_service.find_detail_by_codes(order_id, [code_product])

    if not detail:
        error_payload = {
            "counted-error": {
                "message": "Producto no encontrado en la orden.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=404, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    open_package = inventory_service.get_open_package(order_id)
    if not open_package:
        error_payload = {
            "counted-error": {
                "message": "Debe abrir un bulto antes de contar productos.",
                "focus_id": "code-product",
                "can_open_package": True,
                "order_id": order_id,
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    # Validar stock en depósito de origen
    stock = inventory_service.get_stock_for_product_store(detail.code_product, detail.store)
    stock_amount = stock.stock if stock else 0.0
    if counted_amount > stock_amount:
        error_payload = {
            "counted-error": {
                "message": f"La cantidad contada no puede ser mayor que el stock en el depósito de origen ({stock_amount:.2f}).",
                "focus_id": "counted-amount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    expected = float(detail.amount or 0)
    diff = float(counted_amount) - expected
    has_difference = abs(diff) > 1e-9

    try:
        inventory_service.upsert_user_checking_progress(
            order_id,
            current_user.code,
            code_product,
            float(counted_amount),
        )
        inventory_service.upsert_open_package_product(
            order_id,
            code_product,
            float(counted_amount),
            current_user.code,
        )
        inventory_service.commit_session()
    except Exception as exc:
        inventory_service.rollback_session()
        error_payload = {
            "counted-error": {
                "message": f"No se pudo actualizar el bulto abierto: {exc}",
                "focus_id": "counted-amount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    if has_difference:
        status_html = (
            '<span class="d-inline-flex align-items-center px-2 py-0 rounded-pill small fw-semibold '
            'bg-warning-subtle text-warning-emphasis border border-warning-subtle">'
            f'Contado (Dif. {diff:.2f})</span>'
        )
    else:
        status_html = (
            '<span class="d-inline-flex align-items-center px-2 py-0 rounded-pill small fw-semibold '
            'bg-success-subtle text-success-emphasis border border-success-subtle">Contado</span>'
        )

    trigger_payload = {
        "counted-updated": {
            "code_product": code_product,
            "counted_amount": f"{counted_amount:.2f}",
            "status_html": status_html,
            "has_difference": has_difference,
        }
    }

    # Notificar al cliente vía evento htmx sin insertar <script> repetido
    return Response("", status=204, headers={"HX-Trigger": json.dumps(trigger_payload)})


@inventory_bp.route("/delete_product_from_order", methods=["POST"])
@login_required
def delete_product_from_order():
    order_id = request.form.get("order_id", type=int)
    code_product = inventory_service.normalize_code(request.form.get("code_product"))

    if not order_id or not code_product:
        return "Error: Datos incompletos.", 400

    inventory_service.delete_detail_from_order(order_id, code_product)
    inventory_service.delete_user_checking_progress_item(order_id, current_user.code, code_product)
    inventory_service.commit_session()

    # Responder vacío para hx-swap=delete
    return ""


@inventory_bp.route("/package/open", methods=["POST"])
@login_required
def open_package():
    order_id = request.form.get("order_id", type=int)
    if not order_id:
        return "Error: Datos incompletos.", 400

    try:
        package = inventory_service.open_package_for_operation(order_id, current_user.code)
        inventory_service.commit_session()
        return (
            f'<div class="alert alert-warning small mb-0">Bulto abierto: Bulto {package.package_number}</div>'
        )
    except ValueError as exc:
        inventory_service.rollback_session()
        return (
            f'<div class="alert alert-danger small mb-0">{exc}</div>',
            200,
        )
    except Exception as exc:
        inventory_service.rollback_session()
        return (
            f'<div class="alert alert-danger small mb-0">Error al abrir bulto: {exc}</div>',
            500,
        )


@inventory_bp.route("/package/close", methods=["POST"])
@login_required
def close_package():
    order_id = request.form.get("order_id", type=int)
    if not order_id:
        return "Error: Datos incompletos.", 400

    try:
        package = inventory_service.close_open_package_for_operation(order_id, current_user.code)
        inventory_service.commit_session()
    except ValueError as exc:
        inventory_service.rollback_session()
        return (
            f'<div class="alert alert-danger small mb-0">{exc}</div>',
            200,
        )
    except Exception as exc:
        inventory_service.rollback_session()
        return (
            f'<div class="alert alert-danger small mb-0">Error al cerrar bulto: {exc}</div>',
            500,
        )

    trigger_payload = {
        "open-pdf": {
            "url": url_for("inventory.package_label_report", package_id=package.correlative)
        },
        "package-closed": {
            "order_id": order_id,
            "package_id": package.correlative,
            "package_number": package.package_number,
        },
    }
    return Response(
        f'<div class="alert alert-success small mb-0">Bulto cerrado: Bulto {package.package_number}. Etiqueta generada.</div>',
        status=200,
        headers={"HX-Trigger": json.dumps(trigger_payload)},
    )


@inventory_bp.route("/package/report/<int:package_id>")
@login_required
def package_label_report(package_id):
    package = inventory_service.get_package_by_id(package_id)
    if not package:
        return "Bulto no encontrado.", 404

    barcode_base64 = generate_barcode(f"PKG-{package.correlative}")
    details = package.package_details or []

    # Estimate real row height considering wrapped description text in 80mm paper.
    estimated_line_units = 0
    for item in details:
        description = (item.product.description if item.product else "") or ""
        estimated_line_units += max(1, math.ceil(len(description) / 22))

    # Thermal continuous roll: fixed width (80mm) and dynamic height.
    # Tuned to avoid blank trailing paper while keeping enough room for wrapping.
    page_height_mm = max(95, 66 + (estimated_line_units * 6))

    return Response(
        render_pdf(
            "reports/package_label_pdf.html",
            {
                "package": package,
                "order": package.inventory_operation,
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
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=bulto_{package.package_number}_orden_{package.operation_correlative}.pdf"
        },
    )


@inventory_bp.route("/package/progress", methods=["GET"])
@login_required
def package_progress():
    order_id = request.args.get("order_id", type=int)
    if not order_id:
        return (
            '<div class="alert alert-danger small mb-0 py-2" role="alert">'
            "No se pudo cargar el estado del bulto."
            "</div>",
            400,
        )

    progress = inventory_service.get_open_package_progress(order_id)
    if not progress:
        return (
            '<div class="alert alert-secondary small mb-0 py-2" role="status" data-open-package="0">'
            "No hay bulto abierto."
            "</div>"
        )

    return (
        '<div class="alert alert-warning small mb-0 py-2" role="status" data-open-package="1">'
        f"Bulto {progress['package_number']} abierto: "
        f"{progress['product_lines']} producto(s), "
        f"{progress['total_units']:.2f} unidad(es) embaladas."
        "</div>"
    )


@inventory_bp.route("/save_order_check", methods=["POST"])
@login_required
def save_order_check():
    order_id = request.form.get("order_id", type=int)
    # Validar orden
    if not order_id:
        flash("ID de orden inválido.", "error")
        return redirect(url_for("inventory.check_order"))

    order = inventory_service.get_order_by_id(order_id)
    if not order:
        flash("Orden no encontrada.", "error")
        return redirect(url_for("inventory.check_order"))

    progress_map = inventory_service.get_user_checking_progress_map(order_id, current_user.code)
    uncounted_products = []
    details = inventory_service.get_order_details(order_id)

    for detail in details:
        code_product = inventory_service.normalize_code(detail.code_product)
        if code_product not in progress_map:
            uncounted_products.append(code_product)
            continue

        detail.amount = float(progress_map[code_product])

    if uncounted_products:
        inventory_service.delete_details_from_order(order_id, uncounted_products)

    try:
        inventory_service.close_all_open_packages_for_operation(order_id, current_user.code)
    except ValueError as exc:
        inventory_service.rollback_session()
        flash(str(exc), "error")
        return redirect(url_for("inventory.check_order"))
    except Exception as exc:
        inventory_service.rollback_session()
        flash(f"No se pudieron cerrar los bultos abiertos: {exc}", "error")
        return redirect(url_for("inventory.check_order"))

    packing_validation = inventory_service.validate_packing_matches_counted(order_id)

    if packing_validation["mismatches"]:
        preview = ", ".join(
            [
                (
                    f"{item['product_code']} (contado {item['counted_amount']:.2f} / "
                    f"embalado {item['packed_amount']:.2f})"
                )
                for item in packing_validation["mismatches"][:5]
            ]
        )
        extra = "" if len(packing_validation["mismatches"]) <= 5 else " ..."
        flash(
            "No se puede confirmar el chequeo porque hay diferencias entre contado y embalado por producto: "
            + preview
            + extra,
            "error",
        )
        return redirect(url_for("inventory.check_order"))

    # Update operation description to include route context after checking.
    origin_name = order.store2.description if getattr(order, "store2", None) else order.store
    destination_name = (
        order.store1.description if getattr(order, "store1", None) else order.destination_store
    )
    order.description = (
        "Orden de recoleccion chequeada del deposito de origen "
        f"{origin_name} a destino {destination_name}"
    )

    try:
        inventory_service.register_flow_step2(order_id, current_user.code)
        inventory_service.lock_packages_for_operation(order_id)
        inventory_service.clear_user_checking_progress(order_id, current_user.code)
    except Exception as exc:
        inventory_service.rollback_session()
        flash(f"No se pudo registrar el chequeo de recolección: {exc}", "error")
        return redirect(url_for("inventory.check_order"))

    inventory_service.commit_session()

    flash("Orden de recolección chequeada correctamente.", "success")

    # Respuesta HTMX: limpiar la vista y disparar evento para abrir el PDF en nueva pestaña
    if request.headers.get("HX-Request"):
        trigger_payload = {
            "open-pdf": {
                "url": url_for("inventory.order_collection_report", order_id=order_id)
            }
        }

        resp = make_response(
            render_template(
                "check_order_collection.html",
                order=None,
                details=[],
                error=None,
            )
        )

        resp.headers["HX-Trigger"] = json.dumps(trigger_payload)

        return resp

    # Fallback no HTMX
    return order_collection_report(order_id)


@inventory_bp.route("/checked_order_packages", methods=["GET"])
@login_required
def checked_order_packages():
    operation = None
    flow = None
    packages = []
    error_message = None
    correlative = request.args.get("correlative", type=int)

    if correlative:
        operation = inventory_service.get_transfer_operation_by_correlative(correlative)
        if not operation:
            error_message = "No se encontró una operación de traslado con ese correlativo."
        else:
            flow = inventory_service.get_inventory_operation_flow(operation.correlative)
            if not flow:
                error_message = "La operación no tiene bitácora de flujo registrada."
            elif flow["current_status"] not in [
                FLOW_RECOLLECTION_ISSUED,
                FLOW_RECOLLECTION_CHECKED,
            ]:
                error_message = (
                    "La operación no está en estado de chequeo de recolección. "
                    f"Estado actual: {flow['current_status']}."
                )
            else:
                packages = inventory_service.get_operation_packages(operation.correlative)

    return render_template(
        "checked_order_packages.html",
        operation=operation,
        flow=flow,
        packages=packages,
        error_message=error_message,
        correlative=correlative,
    )


@inventory_bp.route("/check_transfer_operation", methods=["GET", "POST"])
@login_required
def check_transfer_operation():
    message = request.args.get("message")
    if request.method == "POST":
        correlative = request.form.get("correlative")
        if not correlative:
            return render_template(
                "check_transfer_operation.html",
                error_message="Por favor, ingrese un correlativo válido.",
                message=message,
            )

        operation = inventory_service.get_transfer_operation_by_correlative(int(correlative))

        if not operation:
            return render_template(
                "check_transfer_operation.html",
                show_products=False,
                error_message="No se encontró una operación de traslado con ese correlativo.",
            )

        flow = inventory_service.get_inventory_operation_flow(operation.correlative)
        if not flow:
            return render_template(
                "check_transfer_operation.html",
                show_products=False,
                error_message="La operación no tiene bitácora de flujo registrada.",
            )

        if flow["current_status"] != FLOW_IN_TRANSIT:
            return render_template(
                "check_transfer_operation.html",
                show_products=False,
                error_message=(
                    "La operación no está lista para recepción. "
                    f"Estado actual: {flow['current_status']}."
                ),
            )

        # Obtener detalles con productos
        details = inventory_service.get_transfer_operation_details(operation.correlative)
        reception_differences = inventory_service.get_reception_difference_map(operation.correlative)
        reception_progress_map = inventory_service.get_user_transfer_reception_progress_map(
            operation.correlative,
            current_user.code,
        )

        return render_template(
            "check_transfer_operation.html",
            operation=operation,
            details=details,
            reception_differences=reception_differences,
            reception_progress_map=reception_progress_map,
            flow=flow,
            flow_status=flow["current_status"],
            show_products=True,
            message=message,
        )

    return render_template(
        "check_transfer_operation.html",
        show_products=False,
        message=message,
    )


@inventory_bp.route("/start_transfer_operation", methods=["GET", "POST"])
@login_required
def start_transfer_operation():
    operation = None
    details = []
    packages_count = 0
    flow = None
    error_message = None
    correlative = request.values.get("correlative", type=int)

    if request.method == "POST":
        action = request.form.get("action", "search")
        correlative = request.form.get("correlative", type=int)

        if not correlative:
            error_message = "Por favor, ingrese un correlativo válido."
        else:
            operation = inventory_service.get_transfer_operation_by_correlative(correlative)

            if not operation:
                error_message = "No se encontró una operación de traslado con ese correlativo."
            else:
                flow = inventory_service.get_inventory_operation_flow(operation.correlative)
                if not flow:
                    error_message = "La operación no tiene bitácora de flujo registrada."
                elif flow["current_status"] != FLOW_RECOLLECTION_CHECKED:
                    error_message = (
                        "La operación no está lista para iniciar traslado. "
                        f"Estado actual: {flow['current_status']}."
                    )
                elif action == "start":
                    responsible_user, validation_error = inventory_service.validate_transfer_responsible(
                        request.form.get("responsible_user"),
                        request.form.get("responsible_password"),
                        current_user.code,
                    )
                    if validation_error:
                        error_message = validation_error
                    else:
                        try:
                            inventory_service.register_flow_step3(operation.correlative, responsible_user)
                            flash(
                                f"Traslado #{operation.correlative} iniciado correctamente.",
                                "success",
                            )
                            return redirect(
                                url_for(
                                    "inventory.check_transfer_operation",
                                    message=f"Traslado #{operation.correlative} en tránsito.",
                                )
                            )
                        except Exception as exc:
                            error_message = f"No se pudo iniciar el traslado: {exc}"

    elif correlative:
        operation = inventory_service.get_transfer_operation_by_correlative(correlative)
        flow = inventory_service.get_inventory_operation_flow(correlative) if operation else None

    if operation:
        details = inventory_service.get_transfer_operation_details(operation.correlative)
        packages_count = len(inventory_service.get_operation_packages(operation.correlative))

    return render_template(
        "start_transfer_operation.html",
        operation=operation,
        details=details,
        packages_count=packages_count,
        flow=flow,
        error_message=error_message,
        correlative=correlative,
    )


@inventory_bp.route("/transfer_operation/<int:operation_id>/receive", methods=["POST"])
@login_required
def receive_transfer_operation(operation_id):
    operation = inventory_service.get_transfer_operation_by_correlative(operation_id)
    if not operation:
        flash("No se encontró la operación de traslado.", "error")
        return redirect(url_for("inventory.check_transfer_operation"))

    if operation.wait is False:
        flash("La operación de traslado ya fue procesada.", "warning")
        return redirect(url_for("inventory.check_transfer_operation"))

    counted_codes_raw = (request.form.get("counted_codes") or "").strip()
    counted_codes = {
        inventory_service.normalize_code(code)
        for code in counted_codes_raw.split(",")
        if code and code.strip()
    }
    persisted_counted = set(
        inventory_service.get_user_transfer_reception_progress_map(
            operation_id,
            current_user.code,
        ).keys()
    )
    counted_codes.update(persisted_counted)

    try:
        inventory_service.register_missing_reception_differences(
            operation_id,
            counted_codes,
            current_user.code,
        )
        inventory_service.register_flow_step4(operation_id, current_user.code)
        inventory_service.process_inventory_operation(operation_id)
        inventory_service.clear_transfer_reception_progress(operation_id)
        operation.wait = False
        inventory_service.commit_session()
        has_reception_differences = inventory_service.count_reception_differences(operation_id) > 0
        flash("Traslado recepcionado y procesado correctamente.", "success")
    except Exception as exc:
        inventory_service.rollback_session()
        flash(f"No se pudo recepcionar o procesar el traslado: {exc}", "error")
        return redirect(url_for("inventory.check_transfer_operation"))

    if request.headers.get("HX-Request"):
        trigger_payload = {
            "open-pdf": {
                "url": url_for(
                    "inventory.transfer_operation_report", order_id=operation_id
                )
            },
            "redirect-transfer-check": {
                "url": url_for("inventory.check_transfer_operation")
            },
        }
        if has_reception_differences:
            trigger_payload["open-differences-pdf"] = {
                "url": url_for(
                    "reports.transfer_reception_differences_report",
                    order_id=operation_id,
                )
            }
        resp = make_response("", 200)
        resp.headers["HX-Trigger"] = json.dumps(trigger_payload)
        resp.headers["HX-Reswap"] = "none"
        return resp

    return redirect(url_for("inventory.check_transfer_operation"))


@inventory_bp.route(
    "/check_transfer_operation/search_product/<int:operation_id>",
    methods=["GET", "POST"],
)
@login_required
def search_product_in_transfer(operation_id):
    flow = inventory_service.get_inventory_operation_flow(operation_id)
    if not flow or flow["current_status"] != FLOW_IN_TRANSIT:
        error_payload = {
            "search-error": {
                "message": "La operación debe estar en tránsito para contar recepción.",
                "focus_id": "product_code",
            }
        }
        return Response(
            "",
            status=409,
            headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
        )

    product_code_input = (request.values.get("product_code") or "").strip().upper()
    if not product_code_input:
        error_payload = {
            "search-error": {
                "message": "Código de producto requerido.",
                "focus_id": "product_code",
            }
        }
        return Response(
            "",
            status=400,
            headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
        )

    # Resolver código alterno a código principal
    products_code = inventory_service.get_products_code_mapping(product_code_input)
    main_code = (
        (products_code.main_code if products_code else product_code_input)
        .strip()
        .upper()
    )

    # Buscar el producto en la operación usando código principal o alterno
    detail = inventory_service.get_operation_detail_by_code(operation_id, main_code)

    if not detail:
        error_payload = {
            "search-error": {
                "message": "Producto no encontrado en esta operación.",
                "focus_id": "product_code",
            }
        }
        return Response(
            "",
            status=404,
            headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
        )

    return redirect(
        url_for(
            "inventory.product_modal",
            operation_id=operation_id,
            product_code=main_code,
        )
    )


@inventory_bp.route(
    "/check_transfer_operation/modal/<int:operation_id>/<path:product_code>", methods=["GET"]
)
@login_required
def product_modal(operation_id, product_code):
    flow = inventory_service.get_inventory_operation_flow(operation_id)
    if not flow or flow["current_status"] != FLOW_IN_TRANSIT:
        return "La operación debe estar en tránsito para contar recepción.", 409

    product_code = inventory_service.normalize_code(product_code)
    detail = inventory_service.get_operation_detail_by_code(operation_id, product_code)

    if not detail:
        return "Producto no encontrado", 404

    reception_difference = inventory_service.get_reception_difference(operation_id, detail.line)
    expected_amount = (
        reception_difference.original_amount if reception_difference else detail.amount
    )

    failure_info = inventory_service.get_failure_info(product_code, detail.destination_store)

    return render_template(
        "partials/product_modal.html",
        detail=detail,
        expected_amount=expected_amount,
        operation_id=operation_id,
        product_failure=failure_info,
        destination_store=detail.destination_store,
    )


@inventory_bp.route(
    "/check_transfer_operation/update_count/<int:operation_id>",
    methods=["POST"],
)
@inventory_bp.route(
    "/check_transfer_operation/update_count/<int:operation_id>/<path:product_code>/<path:destination_store>",
    methods=["POST"],
)
@login_required
def update_count(operation_id, product_code=None, destination_store=None):
    flow = inventory_service.get_inventory_operation_flow(operation_id)
    if not flow or flow["current_status"] != FLOW_IN_TRANSIT:
        error_payload = {
            "counted-error": {
                "message": "La operación debe estar en tránsito para actualizar recepción.",
                "focus_id": "countedAmount",
            }
        }
        return Response(
            "", status=409, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    product_code = inventory_service.normalize_code(product_code or request.form.get("product_code"))
    destination_store = (destination_store or request.form.get("destination_store") or "").strip()
    counted_amount = request.form.get("counted_amount", type=float, default=0)
    minimal_stock = request.form.get("minimal_stock", type=float, default=0)
    maximum_stock = request.form.get("maximum_stock", type=float, default=0)

    if not product_code or not destination_store:
        error_payload = {
            "counted-error": {
                "message": "Datos incompletos para actualizar el producto.",
                "focus_id": "countedAmount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    # Validaciones
    if counted_amount < 0:
        error_payload = {
            "counted-error": {
                "message": "La cantidad contada no puede ser negativa.",
                "focus_id": "countedAmount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    payload, error_code = inventory_service.apply_transfer_reception_count(
        operation_id=operation_id,
        product_code=product_code,
        destination_store=destination_store,
        counted_amount=counted_amount,
        minimal_stock=minimal_stock,
        maximum_stock=maximum_stock,
        user_code=current_user.code,
    )

    if error_code == "PRODUCT_NOT_FOUND":
        error_payload = {
            "counted-error": {
                "message": "Producto no encontrado en esta operación.",
                "focus_id": "countedAmount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    detail = payload["detail"]
    original_amount = payload["expected_amount"]
    difference_amount = payload["difference_amount"]
    counted_amount = payload["counted_amount"]

    trigger_payload = {
        "transfer-counted-updated": {
            "code_product": detail.code_product,
            "counted_amount": float(counted_amount),
            "expected_amount": float(original_amount),
            "difference_amount": float(difference_amount),
        }
    }
    return Response(
        "",
        status=204,
        headers={"HX-Trigger": json.dumps(trigger_payload)},
    )





@inventory_bp.route("/product_params", methods=["GET", "POST"])
@login_required
def product_params():
    stores = inventory_service.get_all_stores()
    store_code = request.form.get("store_code") 
    code_product = request.form.get("code-product") 

    if request.method == "POST":
        if store_code and not code_product:
            selected_store = inventory_service.get_store_by_code(store_code)
            return render_template(
                "product_params.html", stores=stores, selected_store=selected_store
            )

        if code_product and store_code:
            product_params, _main_code = inventory_service.build_product_params_payload(
                store_code, code_product
            )
            if not product_params:
                flash("Producto no encontrado.", "error")
                selected_store = inventory_service.get_store_by_code(store_code)
                return render_template(
                    "product_params.html", stores=stores, selected_store=selected_store
                )

            selected_store = inventory_service.get_store_by_code(store_code)
            return render_template(
                "product_params.html",
                product_params=product_params,
                selected_store=selected_store,
                stores=stores,
            )

    return render_template("product_params.html", stores=stores, selected_store=store_code)


@inventory_bp.route("/product_params/save", methods=["POST"])
@login_required
def save_product_params():
    store_code = request.form.get("store_code")
    code_product = request.form.get("code-product")

    if not store_code or not code_product:
        flash("Datos incompletos.", "error")
        return redirect(url_for("inventory.product_params"))

    main_code = inventory_service.resolve_main_code_by_other_code(code_product)

    # Guardar parámetros para el producto específico
    min_stock = request.form.get("minimal_stock", "0").strip()
    max_stock = request.form.get("maximum_stock", "0").strip()
    location = request.form.get("location", "").strip()

    try:
        min_stock = int(min_stock) if min_stock else 0
        max_stock = int(max_stock) if max_stock else 0
    except ValueError:
        min_stock = 0
        max_stock = 0

    # Validaciones
    if min_stock < 0 or max_stock < 0:
        flash("Los valores de stock deben ser números positivos.", "error")
        product_params, _ = inventory_service.build_product_params_payload(
            store_code, main_code
        )
        if not product_params:
            product_params = {"code": main_code, "location": location}
        product_params["minimal_stock"] = min_stock
        product_params["maximum_stock"] = max_stock
        product_params["location"] = location

        selected_store = inventory_service.get_store_by_code(store_code)
        stores = inventory_service.get_all_stores()
        return render_template(
            "product_params.html",
            stores=stores,
            selected_store=selected_store,
            product_params=product_params,
        )

    if min_stock > max_stock:
        flash("El stock mínimo no puede ser mayor que el máximo.", "error")
        product_params, _ = inventory_service.build_product_params_payload(
            store_code, main_code
        )
        if not product_params:
            product_params = {"code": main_code, "location": location}
        product_params["minimal_stock"] = min_stock
        product_params["maximum_stock"] = max_stock
        product_params["location"] = location

        selected_store = inventory_service.get_store_by_code(store_code)
        stores = inventory_service.get_all_stores()
        return render_template(
            "product_params.html",
            stores=stores,
            selected_store=selected_store,
            product_params=product_params,
        )

    inventory_service.upsert_product_params(
        store_code, main_code, min_stock, max_stock, location
    )
    flash("Parámetros del producto guardados correctamente.", "success")

    # Limpiar la búsqueda y mostrar solo el input para buscar otro producto
    selected_store = inventory_service.get_store_by_code(store_code)
    stores = inventory_service.get_all_stores()
    return render_template(
        "product_params.html", stores=stores, selected_store=selected_store
    )


## reporte de traslado PDF
@inventory_bp.route("/transfer_operation/report/<int:order_id>")
@login_required
def transfer_operation_report(order_id):
    user = current_user
    order = inventory_service.get_transfer_operation_report_data(order_id)
    sorted_details = inventory_service.sort_details_by_location(order.inventory_operation_details)

    barcode_base64 = generate_barcode(order.correlative)

    return Response(
        render_pdf(
            "reports/transfer_operation_pdf.html",
            {
                "order": order,
                "title": f"chequeo de recepción de traslado {order.correlative}",
                "now": datetime.now(),
                "barcode_base64": barcode_base64,
                "user": user,
                "sorted_details": sorted_details,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=chequeo_traslado_{order.correlative}.pdf"
        },
    )


@inventory_bp.route("/transfer_operation/reception_differences_report/<int:order_id>")
@login_required
def transfer_reception_differences_report(order_id):
    user = current_user
    order, differences = inventory_service.get_transfer_reception_differences_report_data(order_id)

    barcode_base64 = generate_barcode(order.correlative)

    return Response(
        render_pdf(
            "reports/transfer_reception_differences_pdf.html",
            {
                "order": order,
                "differences": differences,
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


@inventory_bp.route("/products_locations", methods=["GET", "POST"])
@login_required
def products_locations():
    store_code = request.values.get("store_code")
    location = request.values.get("location")
    data = inventory_service.get_products_locations_view_data(store_code, location)

    if store_code and not data["store"]:
        flash("Depósito no válido.", "error")
        return render_template("products_locations.html", stores=data["stores"])

    return render_template(
        "products_locations.html",
        stores=data["stores"],
        store=data["store"],
        location=location,
    )


@inventory_bp.route("/update_product_location", methods=["POST"])
@login_required
def update_product_location():
    store_code = request.form.get("store_code")
    location = request.form.get("location")

    products = request.form.getlist("products_codes")

    # validaciones
    if not store_code:
        flash("Depósito no válido.", "error")
        return redirect(url_for("inventory.products_locations"))

    if not location:
        flash("Ubicación no válida.", "error")
        return redirect(url_for("inventory.products_locations"))

    if not products:
        flash("No se seleccionaron productos para actualizar.", "error")
        return redirect(url_for("inventory.products_locations"))

    try:
        products_count = inventory_service.bulk_update_product_location(
            store_code, location, products
        )
        # Redirigir con los parámetros de GET para mantener el estado
        flash(f"Ubicación actualizada los productos seleccionados: {products_count}", "success")
        return redirect(
            url_for(
                "inventory.products_locations", store_code=store_code, location=location
            )
        )
    except Exception as e:
        inventory_service.rollback_session()
        flash("Error al actualizar ubicaciones. Intente nuevamente.", "error")
        print(f"Error updating product locations: {e}")
        return redirect(
            url_for(
                "inventory.products_locations", store_code=store_code, location=location
            )
        )


## buscador de productos para asignar ubicación en masa
@inventory_bp.route("/search_products_for_location", methods=["GET"])
@login_required
def search_products_for_location():
    product_code = request.args.get("product_code", "").strip()

    if not product_code:
        error_payload = {
            "search-error": {
                "message": "Por favor, ingrese un código de producto.",
                "focus_id": "product_code",
            }
        }
        return Response(
            "",
            status=400,
            headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
        )

    product, pf = inventory_service.get_search_product_for_location_data(
        product_code, request.args.get("store_code")
    )

    if not product:
        error_payload = {
            "search-error": {
                "message": "Producto no encontrado. Verifique el código e intente nuevamente.",
                "focus_id": "product_code",
            }
        }
        return Response(
            "",
            status=404,
            headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"},
        )

    return render_template("partials/product_row_location.html", product=product, pf=pf)


@inventory_bp.route("/product_counter", methods=["GET", "POST"])
@login_required
def product_counter():
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    user_counters = all_counters.get(user_code, {}) or {}

    store_code = request.values.get("store_code")
    context = inventory_service.get_product_counter_context(
        user_code=user_code,
        store_code=store_code,
        counters_by_user=user_counters,
    )

    rows = [
        render_template(
            "partials/product_counter_row.html",
            product=item["product"],
            system_qty=item["system_qty"],
            unit=item["unit"],
            counted_amount=item["counted_amount"],
            difference=item["difference"],
            store_code=item["store_code"],
        )
        for item in context["rows"]
    ]
    counter_rows_html = "".join(rows)

    return render_template(
        "product_counter.html",
        stores=context["stores"],
        store=context["store"],
        store_code=store_code,
        counter_rows_html=counter_rows_html,
    )


@inventory_bp.route("/product_counter/search_product_counter/<store_code>")
@login_required
def search_product_counter(store_code):
    product_code = request.args.get("product_code", "").strip()
    data = inventory_service.get_search_product_counter_data(store_code, product_code)
    return render_template(
        "partials/product_counter_modal.html",
        product=data["product"],
        stock=data["stock"],
        unit=data["unit"],
        store=data["store"],
    )


@inventory_bp.route("/product_counter/update_count", methods=["POST"])
@login_required
def update_product_counter():

    product_code = request.form.get("product_code")
    store_code = request.form.get("store_code")
    counted_amount = request.form.get("counted_amount", type=float)
    # existencia al momento en que se abrió el modal (snapshot)
    system_qty = request.form.get("system_qty", type=float)

    if not product_code or not store_code or counted_amount is None:
        return "Datos incompletos", 400

    # Si por alguna razón no vino system_qty, usamos 0.0 como base
    if system_qty is None:
        system_qty = 0.0

    difference = float(counted_amount) - float(system_qty)

    # Guardar/actualizar el conteo en sesión por usuario, depósito y producto
    # Estructura:
    #   product_counter[user_code][store_code][product_code] = {
    #       "system_qty": <existencia en inventario>,
    #       "counted": <cantidad contada>,
    #       "difference": <counted - system_qty>,
    #   }
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    user_counters = all_counters.get(user_code, {}) or {}
    store_counters = user_counters.get(store_code, {}) or {}

    store_counters[product_code] = {
        "system_qty": float(system_qty),
        "counted": float(counted_amount),
        "difference": float(difference),
    }
    user_counters[store_code] = store_counters
    all_counters[user_code] = user_counters
    session["product_counter"] = all_counters

    context = inventory_service.get_product_counter_context(
        user_code=user_code,
        store_code=store_code,
        counters_by_user=user_counters,
    )

    rows = [
        render_template(
            "partials/product_counter_row.html",
            product=item["product"],
            system_qty=item["system_qty"],
            unit=item["unit"],
            counted_amount=item["counted_amount"],
            difference=item["difference"],
            store_code=item["store_code"],
        )
        for item in context["rows"]
    ]

    return "".join(rows)


@inventory_bp.route("/product_counter/remove_row", methods=["POST"])
@login_required
def remove_product_counter_row():
    """Quita la fila del contador y actualiza el estado en sesión para el usuario actual."""
    product_code = request.form.get("product_code")
    store_code = request.form.get("store_code")

    if not product_code or not store_code:
        return "", 400

    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    user_counters = all_counters.get(user_code, {}) or {}
    store_counters = user_counters.get(store_code, {}) or {}

    if product_code in store_counters:
        store_counters.pop(product_code, None)

    if store_counters:
        user_counters[store_code] = store_counters
    else:
        user_counters.pop(store_code, None)

    if user_counters:
        all_counters[user_code] = user_counters
    else:
        all_counters.pop(user_code, None)

    session["product_counter"] = all_counters

    # La fila se elimina en el cliente vía hx-swap="outerHTML" con respuesta vacía
    return ""


@inventory_bp.route("/product_counter/clear_counter")
@login_required
def clear_product_counter():
    store_code = request.args.get("store_code")
    """Limpia todos los contadores de productos en sesión."""
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    if user_code in all_counters:
        all_counters.pop(user_code, None)
        session["product_counter"] = all_counters
    return redirect(url_for("inventory.product_counter", store_code=store_code))


@inventory_bp.route("/product_counter/save_counter/<store_code>", methods=["POST"])
@login_required
def save_products_counter(store_code):
    """Guarda el conteo de productos en la base de datos o lo procesa según la lógica de negocio."""
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    user_counters = all_counters.get(user_code, {}) or {}
    store_counters = user_counters.get(store_code, {}) or {}

    positive_diffs, negative_diffs, _ = inventory_service.classify_counter_differences(
        store_counters
    )
    if not positive_diffs and not negative_diffs:
        flash("No hay diferencias de inventario para procesar.", "info")
        return redirect(url_for("inventory.product_counter"))

    try:
        count_batch_id = inventory_service.save_counter_adjustments(
            store_code=store_code,
            user_code=user_code,
            store_counters=store_counters,
        )
        flash("Operaciones de ajuste de inventario generadas correctamente.", "success")

        # Limpiar los contadores de sesión para este usuario y depósito, ya procesados
        all_counters = session.get("product_counter", {}) or {}
        user_counters = all_counters.get(user_code, {}) or {}
        if store_code in user_counters:
            user_counters.pop(store_code, None)

        if user_counters:
            all_counters[user_code] = user_counters
        else:
            all_counters.pop(user_code, None)

        session["product_counter"] = all_counters

        # Si la petición viene por HTMX, abrimos el reporte en una nueva ventana
        # y refrescamos la vista actual para limpiar el conteo.
        if request.headers.get("HX-Request"):
            resp = make_response("", 204)
            resp.headers["HX-Trigger"] = json.dumps(
                {
                    "open-pdf": {
                        "url": url_for(
                            "inventory.product_counter_report_pdf",
                            count_batch_id=count_batch_id,
                        )
                    }
                }
            )
            resp.headers["HX-Refresh"] = "true"
            return resp

        # Flujo normal (no HTMX): redirigir directamente al PDF del conteo
        return redirect(
            url_for(
                "inventory.product_counter_report_pdf",
                count_batch_id=count_batch_id,
            )
        )

    except Exception as e:
        inventory_service.rollback_session()
        print(f"Error al generar operaciones de ajuste: {e}")
        flash("Error al generar las operaciones de ajuste de inventario.", "error")

        return redirect(url_for("inventory.product_counter"))


@inventory_bp.route("/product_counter/report/<count_batch_id>/pdf")
@login_required
def product_counter_report_pdf(count_batch_id):
    """Genera un PDF con el resultado del conteo y las operaciones de carga/descarga asociadas."""

    # Normalizar el ID de batch por si viene con comillas u espacios
    count_batch_id = (count_batch_id or "").strip().strip('"').strip("'")

    download = request.args.get("download", "0") == "1"

    # Traer todas las filas del historial para este conteo, con sus relaciones
    items = inventory_service.get_counter_history_items(count_batch_id)

    if not items:
        return (
            f"No se encontraron datos de conteo para el ID {count_batch_id}.",
            404,
        )

    # Asumimos que todas las filas del mismo batch comparten depósito, usuario y fecha
    first = items[0]
    store = first.store
    user = first.user
    count_date = first.count_date

    # Obtener (si existen) las operaciones de carga y descarga asociadas a este conteo
    load_op = next((h.load_operation for h in items if h.load_operation), None)
    download_op = next(
        (h.download_operation for h in items if h.download_operation), None
    )

    filename = f"conteo_inventario_{store.code if store else 'N/A'}_{count_date.strftime('%Y%m%d') if count_date else '00000000'}.pdf"

    try:
        pdf = render_pdf(
            "reports/product_counter_pdf.html",
            {
                "title": "Resultado de Conteo de Inventario",
                "now": datetime.now,
                "store": store,
                "user": user,
                "count_date": count_date,
                "batch_id": count_batch_id,
                "items": items,
                "load_op": load_op,
                "download_op": download_op,
            },
        )
    except Exception as exc:
        return (
            f"Error generando PDF de conteo: {exc}",
            500,
        )

    disposition = "attachment" if download else "inline"
    headers = {"Content-Disposition": f"{disposition}; filename={filename}"}
    return Response(pdf, mimetype="application/pdf", headers=headers)


##reporte de contero de productos
@inventory_bp.route("/product_counter/report/<count_batch_id>")
@login_required
def product_counter_report(count_batch_id):
    # Normalizar el ID de batch igual que en la versión PDF
    count_batch_id = (count_batch_id or "").strip().strip('"').strip("'")

    history_records = inventory_service.get_counter_history_records(count_batch_id)

    if not history_records:
        flash(
            f"No se encontraron datos de conteo para el ID {count_batch_id}.", "warning"
        )
        return redirect(url_for("inventory.product_counter"))

    # Por ahora solo devolvemos un JSON simple con info básica; se puede mejorar con una plantilla HTML
    # para un reporte en pantalla si lo necesitas.
    data = [
        {
            "product_code": h.product_code,
            "store_code": h.store_code,
            "user_code": h.user_code,
            "count_date": h.count_date.isoformat() if h.count_date else None,
            "system_qty": h.system_qty,
            "counted_qty": h.counted_qty,
            "difference": h.difference,
            "load_operation": h.operation_correlative_up,
            "download_operation": h.operation_correlative_down,
        }
        for h in history_records
    ]

    return {
        "count_batch_id": count_batch_id,
        "records": data,
    }


@inventory_bp.route(
    "/modal_product_params",
    methods=["GET", "POST"],
    defaults={"product_code": None, "store": None},
)
@inventory_bp.route("/modal_product_params/<product_code>/<store>", methods=["GET", "POST"])
@login_required
def modal_product_params(product_code=None, store=None):
    product_code = product_code or request.values.get("product_code")
    store = store or request.values.get("store") or request.values.get("store_code")

    if request.method == "POST":
        form_product_code = inventory_service.normalize_code(request.form.get("product_code") or product_code)
        form_store_code = (request.form.get("store_code") or store or "").strip()

        if not form_product_code or not form_store_code:
            return "Datos incompletos para guardar parametros.", 400

        modal_data = inventory_service.get_modal_product_params_data(
            form_product_code, form_store_code
        )
        main_code = modal_data["main_code"]
        product_info = modal_data["product"]
        store_info = modal_data["store"]
        existing_params = modal_data["product_params"]

        if not product_info:
            return "Producto no encontrado.", 404
        if not store_info:
            return "Deposito no encontrado.", 404

        try:
            minimal_stock = request.form.get("minimal_stock", type=float, default=0)
            maximum_stock = request.form.get("maximum_stock", type=float, default=0)

            if minimal_stock is None:
                minimal_stock = 0
            if maximum_stock is None:
                maximum_stock = 0

            if minimal_stock < 0 or maximum_stock < 0:
                return "Los valores de stock no pueden ser negativos.", 422

            if minimal_stock > maximum_stock:
                return "El stock minimo no puede ser mayor al stock maximo.", 422

            inventory_service.upsert_product_params(
                form_store_code,
                main_code,
                minimal_stock,
                maximum_stock,
                existing_params.location if existing_params and existing_params.location else "",
            )
            return "Parametros guardados correctamente.", 200
        except Exception as exc:
            inventory_service.rollback_session()
            return f"Error al guardar parametros: {exc}", 500

    if not product_code or not store:
        return "Código de producto o depósito no proporcionado.", 400

    modal_data = inventory_service.get_modal_product_params_data(product_code, store)
    product_info = modal_data["product"]

    if not product_info:
        return "Producto no encontrado.", 404

    store_info = modal_data["store"]
    if not store_info:
        return "Depósito no encontrado.", 404

    return render_template(
        "partials/modal_product_params.html",
        product_params=modal_data["product_params"],
        product=product_info,
        store=store_info,
        unit=modal_data["unit"],
    )