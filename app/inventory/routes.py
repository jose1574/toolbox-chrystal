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
)
import json
from io import BytesIO
from flask_login import login_required, current_user
from datetime import datetime
from uuid import uuid4
from app import db
from sqlalchemy import select, case, func, text
from sqlalchemy.orm import aliased, joinedload
from app.inventory import inventory_bp
import pandas as pd
import xlwt
from app.models import (
    Store,
    Product,
    ProductsUnit,
    Department,
    Unit,
    Mark,
    ProductsFailure,
    ProductsStock,
    Tax,
    InventoryOperation,
    InventoryOperationDetail,
    ProductsCode,
    ProductsCounterHistory,
)

from app.reports.utils import render_pdf, generate_barcode


@inventory_bp.route("/")
@login_required
def index():
    return render_template("index.html")


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _resolve_main_code(code: str) -> str:
    normalized = _normalize_code(code)
    mapping = (
        ProductsCode.query.filter(
            func.upper(func.trim(ProductsCode.other_code)) == normalized
        )
        .first()
    )
    return _normalize_code(mapping.main_code) if mapping else normalized


def _find_detail_by_codes(order_id, codes):
    normalized_codes = {_normalize_code(code) for code in codes if code}
    if not normalized_codes:
        return None
    return (
        InventoryOperationDetail.query.filter(
            InventoryOperationDetail.main_correlative == order_id,
            func.upper(func.trim(InventoryOperationDetail.code_product)).in_(
                normalized_codes
            ),
        )
        .options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(
                ProductsUnit.unit1
            ),
        )
        .first()
    )


def _build_products_list_df():
    stmt = (
        select(
            Product.code.label("code"),
            Product.description.label("description"),
            Product.referenc.label("referenc"),
            Product.mark.label("mark"),
            Product.model.label("model"),
            Product.department.label("department"),
            Product.buy_tax.label("buy_tax"),
            Product.sale_tax.label("sale_tax"),
            Product.coin.label("coin"),
            Product.serialized.label("serialized"),
            Product.use_lots.label("use_lots"),
            ProductsUnit.unit.label("unit"),
            ProductsUnit.unitary_cost.label("unitary_cost"),
            ProductsUnit.maximum_price.label("maximum_price"),
            ProductsUnit.offer_price.label("offer_price"),
            ProductsUnit.higher_price.label("higher_price"),
            ProductsUnit.minimum_price.label("minimum_price"),
        )
        .join(ProductsUnit, ProductsUnit.product_code == Product.code)
        .where(ProductsUnit.main_unit.is_(True))
        .order_by(Product.code.asc())
    )
    rows = db.session.execute(stmt).mappings().all()
    return pd.DataFrame(rows)


@inventory_bp.route("/listado-productos", methods=["GET"])
@login_required
def listado_productos():
    df = _build_products_list_df()
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
    df = _build_products_list_df()

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

    header_style = xlwt.easyxf("font: bold on; pattern: pattern solid, fore_colour gray25;")
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
    stores = Store.query.all()
    new_order_id = request.args.get("new_order_id")
    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")

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
            stores=stores,
            new_order_id=new_order_id,
        )

    store_origin_obj = (
        Store.query.filter_by(code=store_origin).first() if store_origin else None
    )
    store_dst_obj = Store.query.filter_by(code=store_dst).first() if store_dst else None

    # Si no hay selección de depósitos, solo mostramos el formulario
    if not store_origin or not store_dst:
        return render_template(
            "auto_order_collection.html",
            store_origin=store_origin,
            store_dst=store_dst,
            store_origin_name=store_origin_obj.description if store_origin_obj else "",
            store_dst_name=store_dst_obj.description if store_dst_obj else "",
            products=[],
            departments=[],
            marks=[],
            stores=stores,
            new_order_id=new_order_id,
        )

    stock_orig = aliased(ProductsStock)
    stock_dst = aliased(ProductsStock)
    pf = aliased(ProductsFailure)
    m = aliased(Mark)
    d = aliased(Department)
    u = aliased(Unit)
    pu = aliased(ProductsUnit)

    needed = pf.maximum_stock - func.coalesce(stock_dst.stock, 0)
    to_transfer = func.least(
        func.coalesce(stock_orig.stock, 0), func.greatest(needed, 0)
    ).label("to_transfer")

    stmt = (
        select(
            Product.code,
            Product.description,
            Product.mark.label("mark_code"),
            Product.department.label("department_code"),
            m.description.label("mark_description"),
            d.description.label("department_description"),
            func.coalesce(stock_orig.stock, 0).label("stock_origin"),
            pf.minimal_stock.label("minimum_stock"),
            pf.maximum_stock.label("maximum_stock"),
            func.coalesce(stock_dst.stock, 0).label("stock_destination"),
            u.description.label("unit_description"),
            to_transfer,
        )
        .join(
            stock_orig,
            (Product.code == stock_orig.product_code)
            & (stock_orig.store == store_origin),
        )
        .outerjoin(
            stock_dst,
            (Product.code == stock_dst.product_code) & (stock_dst.store == store_dst),
        )
        .outerjoin(pf, (Product.code == pf.product_code) & (pf.store_code == store_dst))
        .join(pu, (Product.code == pu.product_code) & (pu.main_unit == True))
        .join(u, pu.unit == u.code)
        .join(d, Product.department == d.code)
        .outerjoin(m, Product.mark == m.code)
        .where(
            (stock_orig.stock > 0)
            & (func.coalesce(stock_dst.stock, 0) < pf.minimal_stock)
            & (needed > 0)
        )
    )

    results = db.session.execute(stmt).all()

    unique_depts = sorted(
        list(
            set(
                row.department_description
                for row in results
                if row.department_description
            )
        )
    )
    unique_marks = sorted(
        list(set(row.mark_description for row in results if row.mark_description))
    )

    return render_template(
        "auto_order_collection.html",
        store_origin=store_origin,
        store_dst=store_dst,
        store_origin_name=store_origin_obj.description if store_origin_obj else "",
        store_dst_name=store_dst_obj.description if store_dst_obj else "",
        products=results,
        departments=unique_depts,
        marks=unique_marks,
        stores=stores,
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

    store_origen_obj = Store.query.filter_by(code=store_origin).first()
    store_dst_obj = Store.query.filter_by(code=store_dst).first()

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
        # 1. Cabecera: Parámetros nombrados para compatibilidad con SQLAlchemy
        header_params = {
            "p_correlative": None,
            "p_operation_type": "TRANSFER",
            "p_document_no": None,
            "p_emission_date": datetime.now().date(),
            "p_wait": True,
            "p_description": f"Traslado Automatico {store_origen_obj.description} -> {store_dst_obj.description}",
            "p_user_code": current_user.code,
            "p_station": "00",
            "p_store": store_origin,
            "p_locations": "00",
            "p_destination_store": store_dst,
            "p_destination_location": "00",
            "p_operation_comments": "Generado desde Toolbox Auto Order",
            "p_total_amount": 0.0,
            "p_total_net": 0.0,
            "p_total_tax": 0.0,
            "p_total": 0.0,
            "p_coin_code": "02",
            "p_internal_use": False,
        }

        sql_header = text(
            """
            SELECT set_inventory_operation(:p_correlative, :p_operation_type, :p_document_no, 
            :p_emission_date, :p_wait, :p_description, :p_user_code, :p_station, :p_store, :p_locations, 
            :p_destination_store, :p_destination_location, :p_operation_comments, :p_total_amount, 
            :p_total_net, :p_total_tax, :p_total, :p_coin_code, :p_internal_use)
        """
        )

        document_no = db.session.execute(sql_header, header_params).scalar()
        if not document_no:
            raise Exception("La DB no devolvió ID de operación.")

        print(f"Nuevo ID de operación: {document_no}")
        # 2. Detalles
        sql_detail = text(
            """
            SELECT set_inventory_operation_details(:p_main_correlative, :p_line, :p_code_product, 
            :p_description_product, :p_referenc, :p_mark, :p_model, :p_amount, :p_store, :p_locations, 
            :p_destination_store, :p_destination_location, :p_unit, :p_conversion_factor, :p_unit_type, 
            :p_unitary_cost, :p_buy_tax, :p_aliquot, :p_total_cost, :p_total_tax, :p_total, :p_coin_code, 
            :p_change_price)
        """
        )

        for item in selected_items:
            # Obtener datos: Unidad Principal, Producto, Impuesto
            data_row = (
                db.session.query(ProductsUnit, Product, Tax)
                .join(Product, ProductsUnit.product_code == Product.code)
                .outerjoin(Tax, Product.buy_tax == Tax.code)
                .filter(
                    ProductsUnit.product_code == item["code"],
                    ProductsUnit.main_unit == True,
                )
                .first()
            )

            if not data_row:
                print(f"OMITIDO: {item['code']} falta info maestra.")
                continue

            pu, prod, tax = data_row

            detail_params = {
                "p_main_correlative": document_no,
                "p_line": 0,  # INOUT Integer (Enviar 0 para evitar error de tipos)
                "p_code_product": item["code"],
                "p_description_product": "comentario automatico, ToolBox",
                "p_referenc": prod.referenc,
                "p_mark": prod.mark,
                "p_model": prod.model,
                "p_amount": float(item["quantity"]),
                "p_store": store_origin,
                "p_locations": "00",
                "p_destination_store": store_dst,
                "p_destination_location": "00",
                "p_unit": int(pu.correlative),
                "p_conversion_factor": 0.0,
                "p_unit_type": 0,  # Integer requerido (antes 0.0)
                "p_unitary_cost": 0.0,
                "p_buy_tax": prod.buy_tax,
                "p_aliquot": tax.aliquot if tax else 0.0,
                "p_total_cost": 0.0,
                "p_total_tax": 0.0,
                "p_total": 0.0,
                "p_coin_code": "02",
                "p_change_price": False,
            }
            db.session.execute(sql_detail, detail_params)

        db.session.commit()
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
        db.session.rollback()
        print(f"Error crítico: {e}")
        flash(f"Error: {str(e)}", "error")
        return redirect(
            url_for(
                "inventory.auto_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )


@inventory_bp.route("/order_collection/report/<int:order_id>")
@login_required
def order_collection_report(order_id):
    user = current_user
    order = InventoryOperation.query.options(
        joinedload(InventoryOperation.store1),
        joinedload(InventoryOperation.store2),
        joinedload(InventoryOperation.user),
        joinedload(InventoryOperation.details).options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(
                ProductsUnit.unit1
            ),
            # Aquí cargamos la información del esquema toolbox
            joinedload(InventoryOperationDetail.failure_info),
        ),
    ).get_or_404(order_id)

    barcode_base64 = generate_barcode(order.correlative)

    return Response(
        render_pdf(
            "reports/order_collection_pdf.html",
            {
                "order": order,
                "title": f"Orden de Recolección Automatica {order.correlative}",
                "now": datetime.now(),
                "barcode_base64": barcode_base64,
                "user": user,
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=orden_{order.correlative}.pdf"
        },
    )


@inventory_bp.route("/check_order", methods=["GET", "POST"])
@login_required
def check_order():
    order_details = None
    error = None

    io = aliased(InventoryOperation)
    iod = aliased(InventoryOperationDetail)
    pu = aliased(ProductsUnit)
    p = aliased(Product)
    u = aliased(Unit)
    store_dst = aliased(Store)
    store_origin = aliased(Store)

    if request.method == "POST":
        order_id = request.form.get("order_id", type=int)
        if not order_id:
            error = "Debe ingresar un ID de orden válido."
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        # Buscar la operación y validar que sea un traslado procesado
        order_entity = InventoryOperation.query.filter_by(
            correlative=order_id, operation_type="TRANSFER", wait=True
        ).first()

        if not order_entity:
            error = f"No se encontró la orden con ID {order_id}"
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        stmt = (
            select(
                io.correlative,
                io.document_no,
                io.emission_date,
                io.store,
                io.destination_store,
                io.description,
                io.operation_comments,
                io.user_code,
                io.total_amount,
                iod.code_product,
                p.description.label("product_description"),
                iod.amount,
                u.description.label("unit_description"),
                store_origin.description.label("store_origin_description"),
                store_dst.description.label("store_dst_description"),
            )
            .join(iod, iod.main_correlative == io.correlative)
            .join(p, p.code == iod.code_product)
            .join(pu, pu.correlative == iod.unit)
            .join(u, u.code == pu.unit)
            .join(store_origin, store_origin.code == io.store)
            .join(store_dst, store_dst.code == io.destination_store)
            .where(
                io.correlative == order_id,
                io.operation_type == "TRANSFER",
                io.wait.is_(True),
            )
        )

        results = db.session.execute(stmt).all()

        if not results:
            error = f"No se encontró la orden con ID {order_id} o no contiene detalles."
            return render_template(
                "check_order_collection.html", order=None, details=[], error=error
            )

        # El primer resultado contiene la información de cabecera
        order_header = results[0]
        order_details = results

        return render_template(
            "check_order_collection.html",
            order=order_header,
            details=order_details,
            error=error,
        )

    return render_template(
        "check_order_collection.html", order=None, details=[], error=None
    )


@inventory_bp.route("/search_product", methods=["GET"])
@login_required
def search_product():
    code_product = _normalize_code(request.args.get("code-product"))
    order_id = request.args.get("order_id", type=int)

    if not code_product or not order_id:
        return render_template(
            "partials/check_order_product_modal.html",
            item=None,
            product_description="",
            unit_description="",
            order=None,
        )

    main_code = _resolve_main_code(code_product)

    detail = _find_detail_by_codes(order_id, [main_code])

    if not detail:
        # Producto no encontrado en la orden, validar existencia en catálogo
        product = (
            Product.query.filter(func.upper(func.trim(Product.code)) == main_code).first()
        )
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
        order = InventoryOperation.query.get(order_id)
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
        pu = (
            ProductsUnit.query.filter(
                func.upper(func.trim(ProductsUnit.product_code)) == main_code,
                ProductsUnit.main_unit.is_(True),
            )
            .options(joinedload(ProductsUnit.unit1))
            .first()
        )
        if not pu:
            return render_template(
                "partials/check_order_product_modal.html",
                item=None,
                product_description="Unidad principal no encontrada para el producto.",
                unit_description="",
                order=None,
                is_new=False,
            )

        unit = Unit.query.filter_by(code=pu.unit).first()

        # Obtener cantidad en depósito origen
        stock = ProductsStock.query.filter(
            func.upper(func.trim(ProductsStock.product_code)) == main_code,
            ProductsStock.store == order.store,
        ).first()
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
    actual_code = _normalize_code(detail.code_product)
    product = Product.query.filter(
        func.upper(func.trim(Product.code)) == actual_code
    ).first()
    unit = (
        Unit.query.join(ProductsUnit)
        .filter(ProductsUnit.correlative == detail.unit)
        .first()
    )

    # Obtener cantidad en depósito origen para validación de conteo
    stock = ProductsStock.query.filter(
        func.upper(func.trim(ProductsStock.product_code)) == actual_code,
        ProductsStock.store == detail.store,
    ).first()
    stock_amount = stock.stock if stock else 0.0

    # Renderizar el modal con datos
    return render_template(
        "partials/check_order_product_modal.html",
        item=detail,
        product_description=product.description if product else "Desconocido",
        unit_description=unit.description if unit else "Desconocida",
        order=InventoryOperation.query.get(order_id),
        stock_amount=stock_amount,
    )


@inventory_bp.route("/add_product_to_order", methods=["POST"])
@login_required
def add_product_to_order():
    order_id = request.form.get("order_id", type=int)
    code_product = _normalize_code(request.form.get("code_product"))

    print(f"Agregando producto: order_id={order_id}, code_product={code_product}")

    if not order_id or not code_product:
        print("Datos incompletos")
        error_payload = {
            "product-error": {
                "message": "Error: datos incompletos para agregar el producto.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    main_code = _resolve_main_code(code_product)

    print(f"Main code: {main_code}")

    # Verificar si ya existe
    detail = _find_detail_by_codes(order_id, [main_code, code_product])

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

    # Obtener datos
    product = Product.query.filter(
        func.upper(func.trim(Product.code)) == main_code
    ).first()
    order = InventoryOperation.query.get(order_id)
    pu = (
        ProductsUnit.query.filter(
            func.upper(func.trim(ProductsUnit.product_code)) == main_code,
            ProductsUnit.main_unit.is_(True),
        )
        .options(joinedload(ProductsUnit.unit1))
        .first()
    )

    if not product:
        error_payload = {
            "product-error": {
                "message": "El producto ingresado no existe en la base de datos.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=404, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    if not order:
        error_payload = {
            "product-error": {
                "message": "Orden no encontrada. Vuelve a cargar el correlativo.",
                "focus_id": "order_id",
            }
        }
        return Response(
            "", status=404, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    if not pu:
        error_payload = {
            "product-error": {
                "message": "Unidad principal no encontrada para el producto.",
                "focus_id": "code-product",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    tax = Tax.query.filter_by(code=product.buy_tax).first() if product.buy_tax else None

    print(f"Product: {product}, Order: {order}, PU: {pu}, Tax: {tax}")

    # Validar stock en depósito de origen
    stock = ProductsStock.query.filter(
        func.upper(func.trim(ProductsStock.product_code)) == main_code,
        ProductsStock.store == order.store,
    ).first()
    stock_amount = stock.stock if stock else 0.0
    if stock_amount <= 0:
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
        # Calcular siguiente línea respetando la restricción unique de la columna line (es global, no por orden)
        max_line_global = db.session.query(
            func.max(InventoryOperationDetail.line)
        ).scalar()
        next_line = (max_line_global or 0) + 1

        # Crear detalle
        new_detail = InventoryOperationDetail(
            main_correlative=order_id,
            line=next_line,
            code_product=main_code,
            description_product=product.description,
            referenc=product.referenc,
            mark=product.mark,
            model=product.model,
            amount=0.0,
            store=order.store,
            locations="00",
            destination_store=order.destination_store,
            destination_location="00",
            unit=pu.correlative,
            conversion_factor=0.0,
            unit_type=0,
            unitary_cost=0.0,
            buy_tax=product.buy_tax,
            aliquot=tax.aliquot if tax else 0.0,
            total_cost=0.0,
            total_tax=0.0,
            total=0.0,
            coin_code="02",
            change_price=False,
        )

        db.session.add(new_detail)
        db.session.commit()

        print("Producto agregado exitosamente")

        # Obtener unidad para descripción
        unit = Unit.query.filter_by(code=pu.unit).first()

        # Renderizar la fila y devolver, notificando al cliente vía HX-Trigger
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
        db.session.rollback()
        print(f"Error al agregar producto: {e}")
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
    code_product = _normalize_code(request.form.get("code_product"))
    counted_amount = request.form.get("counted_amount", type=float)

    if not order_id or not code_product or counted_amount is None:
        return "Error: Datos incompletos."

    # Actualizar el detalle (por ahora, solo en memoria, pero luego en BD)
    # Para simplificar, devolver HTML actualizado para la fila
    detail = _find_detail_by_codes(order_id, [code_product])

    if not detail:
        error_payload = {
            "counted-error": {
                "message": "Producto no encontrado en la orden.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload)})

    # Validar stock en depósito de origen
    stock = ProductsStock.query.filter(
        func.upper(ProductsStock.product_code) == _normalize_code(detail.code_product),
        ProductsStock.store == detail.store,
    ).first()
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

    expected = detail.amount
    diff = counted_amount - expected

    status_html = '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 border border-green-200">Contado</span>'

    trigger_payload = {
        "counted-updated": {
            "code_product": code_product,
            "counted_amount": f"{counted_amount:.2f}",
            "status_html": status_html,
        }
    }

    # Notificar al cliente vía evento htmx sin insertar <script> repetido
    return Response("", status=204, headers={"HX-Trigger": json.dumps(trigger_payload)})


@inventory_bp.route("/delete_product_from_order", methods=["POST"])
@login_required
def delete_product_from_order():
    order_id = request.form.get("order_id", type=int)
    code_product = _normalize_code(request.form.get("code_product"))

    if not order_id or not code_product:
        return "Error: Datos incompletos.", 400

    # Eliminar de la BD
    detail = _find_detail_by_codes(order_id, [code_product])

    if detail:
        db.session.delete(detail)
        db.session.commit()

    # Responder vacío para hx-swap=delete
    return ""


@inventory_bp.route("/save_order_check", methods=["POST"])
@login_required
def save_order_check():
    order_id = request.form.get("order_id", type=int)
    # Validar orden
    if not order_id:
        flash("ID de orden inválido.", "error")
        return redirect(url_for("inventory.check_order"))

    order = InventoryOperation.query.get(order_id)
    if not order:
        flash("Orden no encontrada.", "error")
        return redirect(url_for("inventory.check_order"))

    # Actualizar las cantidades contadas en la BD para los productos restantes
    for key, value in request.form.items():
        if key.startswith("counted_"):
            code_product = _normalize_code(key[8:])  # Remove "counted_"
            counted_amount = float(value) if value else 0

            detail = _find_detail_by_codes(order_id, [code_product])

            if detail:
                detail.amount = counted_amount

    # Actualizar descripción de cabecera para reflejar el chequeo
    order.description = "orden de recoleccion chequeada"

    db.session.commit()

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

        # Buscar la operación de traslado procesada
        operation = InventoryOperation.query.filter_by(
            correlative=int(correlative),
            operation_type="TRANSFER",  # Tipo de operación para traslados
            wait=False,
        ).first()

        if not operation:
            return render_template(
                "check_transfer_operation.html",
                show_products=False,
                error_message="No se encontró una operación de traslado procesado con ese correlativo.",
            )

        # Obtener detalles con productos
        details = (
            InventoryOperationDetail.query.filter_by(
                main_correlative=operation.correlative
            )
            .options(
                joinedload(InventoryOperationDetail.product),
                joinedload(InventoryOperationDetail.products_unit).joinedload(
                    ProductsUnit.unit1
                ),
            )
            .all()
        )

        return render_template(
            "check_transfer_operation.html",
            operation=operation,
            details=details,
            show_products=True,
            message=message,
        )

    return render_template(
        "check_transfer_operation.html",
        show_products=False,
        message=message,
    )


@inventory_bp.route("/check_transfer_operation/search_product/<int:operation_id>", methods=["GET", "POST"])
@login_required
def search_product_in_transfer(operation_id):
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
    products_code = ProductsCode.query.filter_by(other_code=product_code_input).first()
    main_code = (products_code.main_code if products_code else product_code_input).strip().upper()

    # Buscar el producto en la operación usando código principal o alterno
    detail = (
        InventoryOperationDetail.query.filter(
            InventoryOperationDetail.main_correlative == operation_id,
            InventoryOperationDetail.code_product == main_code,
        )
        .options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(
                ProductsUnit.unit1
            ),
        )
        .first()
    )

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
    "/check_transfer_operation/modal/<int:operation_id>/<product_code>", methods=["GET"]
)
@login_required
def product_modal(operation_id, product_code):
    # Buscar el producto en la operación
    detail = (
        InventoryOperationDetail.query.filter_by(
            main_correlative=operation_id, code_product=product_code
        )
        .options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(
                ProductsUnit.unit1
            ),
        )
        .first()
    )

    if not detail:
        return "Producto no encontrado", 404

    failure_info = ProductsFailure.query.filter_by(
        product_code=product_code, store_code=detail.destination_store
    ).first()

    return render_template(
        "partials/product_modal.html",
        detail=detail,
        operation_id=operation_id,
        product_failure=failure_info,
        destination_store=detail.destination_store,
    )


@inventory_bp.route(
    "/check_transfer_operation/update_count/<int:operation_id>/<path:product_code>/<destination_store>",
    methods=["POST"],
)
@login_required
def update_count(operation_id, product_code, destination_store):
    counted_amount = request.form.get("counted_amount", type=float, default=0)
    minimal_stock = request.form.get("minimal_stock", type=float, default=0)
    maximum_stock = request.form.get("maximum_stock", type=float, default=0)

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

    # Verificar que el producto existe en la operación
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=operation_id, code_product=product_code
    ).first()

    if not detail:
        error_payload = {
            "counted-error": {
                "message": "Producto no encontrado en esta operación.",
                "focus_id": "countedAmount",
            }
        }
        return Response(
            "", status=422, headers={"HX-Trigger": json.dumps(error_payload)}
        )

    ##actualiza products_failures
    failure_info = ProductsFailure.query.filter_by(
        product_code=product_code, store_code=destination_store
    ).first()

    if not failure_info:
        failure_info = ProductsFailure(
            product_code=product_code,
            store_code=destination_store,
            minimal_stock=minimal_stock or 0,
            maximum_stock=maximum_stock or 0,
            location="",
        )
        db.session.add(failure_info)
    else:
        failure_info.minimal_stock = minimal_stock or 0
        failure_info.maximum_stock = maximum_stock or 0

    db.session.commit()

    # Devolver siempre la fila actualizada (aunque no haya diferencia) para permitir re-conteos posteriores
    return render_template(
        "partials/table_row.html",
        detail=detail,
        counted_amount=counted_amount,
    )


@inventory_bp.route("/product_params", methods=["GET", "POST"])
@login_required
def product_params():
    stores = Store.query.all()

    if request.method == "POST":
        store_code = request.form.get("store_code")
        code_product = request.form.get("code-product")

        if store_code and not code_product:
            selected_store = Store.query.filter_by(code=store_code).first()
            return render_template(
                "product_params.html", stores=stores, selected_store=selected_store
            )

        if code_product and store_code:
            # Buscar código principal si es código alterno
            products_code = ProductsCode.query.filter_by(
                other_code=code_product
            ).first()
            main_code = products_code.main_code if products_code else code_product

            product = Product.query.filter_by(code=main_code).first()
            if not product:
                flash("Producto no encontrado.", "error")
                selected_store = Store.query.filter_by(code=store_code).first()
                return render_template(
                    "product_params.html", stores=stores, selected_store=selected_store
                )

            product_failure = ProductsFailure.query.filter_by(
                product_code=main_code, store_code=store_code
            ).first()
            product_stock = ProductsStock.query.filter_by(
                product_code=main_code, store=store_code
            ).first()

            product_params = {
                "code": main_code,
                "description": product.description,
                "referenc": product.referenc,
                "mark": product.mark,
                "model": product.model,
                "stock": product_stock.stock if product_stock else 0,
                "minimal_stock": (
                    product_failure.minimal_stock
                    if product_failure and product_failure.minimal_stock is not None
                    else 0
                ),
                "maximum_stock": (
                    product_failure.maximum_stock
                    if product_failure and product_failure.maximum_stock is not None
                    else 0
                ),
                "location": (
                    product_failure.location
                    if product_failure
                    and product_failure.location
                    and product_failure.location
                    else ""
                ),
            }
            selected_store = Store.query.filter_by(code=store_code).first()
            return render_template(
                "product_params.html",
                product_params=product_params,
                selected_store=selected_store,
                stores=stores,
            )

    return render_template("product_params.html", stores=stores, selected_store=None)


@inventory_bp.route("/product_params/save", methods=["POST"])
@login_required
def save_product_params():
    store_code = request.form.get("store_code")
    code_product = request.form.get("code-product")

    if not store_code or not code_product:
        flash("Datos incompletos.", "error")
        return redirect(url_for("inventory.product_params"))

    # Buscar código principal si es código alterno
    products_code = ProductsCode.query.filter_by(other_code=code_product).first()
    main_code = products_code.main_code if products_code else code_product

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
        # Recargar la página con los datos actuales
        product = Product.query.filter_by(code=main_code).first()
        product_failure = ProductsFailure.query.filter_by(
            product_code=main_code, store_code=store_code
        ).first()
        product_stock = ProductsStock.query.filter_by(
            product_code=main_code, store=store_code
        ).first()

        product_params = {
            "code": main_code,
            "description": product.description if product else "",
            "referenc": product.referenc if product else "",
            "mark": product.mark if product else "",
            "model": product.model if product else "",
            "stock": product_stock.stock if product_stock else 0,
            "minimal_stock": min_stock,  # Usar los valores enviados para mostrar errores
            "maximum_stock": max_stock,
            "location": location,
        }
        selected_store = Store.query.filter_by(code=store_code).first()
        stores = Store.query.all()
        return render_template(
            "product_params.html",
            stores=stores,
            selected_store=selected_store,
            product_params=product_params,
        )

    if min_stock > max_stock:
        flash("El stock mínimo no puede ser mayor que el máximo.", "error")
        # Recargar la página con los datos actuales
        product = Product.query.filter_by(code=main_code).first()
        product_failure = ProductsFailure.query.filter_by(
            product_code=main_code, store_code=store_code
        ).first()
        product_stock = ProductsStock.query.filter_by(
            product_code=main_code, store=store_code
        ).first()

        product_params = {
            "code": main_code,
            "description": product.description if product else "",
            "referenc": product.referenc if product else "",
            "mark": product.mark if product else "",
            "model": product.model if product else "",
            "stock": product_stock.stock if product_stock else 0,
            "minimal_stock": min_stock,
            "maximum_stock": max_stock,
            "location": location,
        }
        selected_store = Store.query.filter_by(code=store_code).first()
        stores = Store.query.all()
        return render_template(
            "product_params.html",
            stores=stores,
            selected_store=selected_store,
            product_params=product_params,
        )

    pf = ProductsFailure.query.filter_by(
        product_code=main_code, store_code=store_code
    ).first()

    if pf:
        pf.minimal_stock = min_stock
        pf.maximum_stock = max_stock
        pf.location = location
    else:
        pf = ProductsFailure(
            product_code=main_code,
            store_code=store_code,
            minimal_stock=min_stock,
            maximum_stock=max_stock,
            location=location,
        )
        db.session.add(pf)

    db.session.commit()
    flash("Parámetros del producto guardados correctamente.", "success")

    # Limpiar la búsqueda y mostrar solo el input para buscar otro producto
    selected_store = Store.query.filter_by(code=store_code).first()
    stores = Store.query.all()
    return render_template(
        "product_params.html", stores=stores, selected_store=selected_store
    )


## reporte de traslado PDF
@inventory_bp.route("/transfer_operation/report/<int:order_id>")
@login_required
def transfer_operation_report(order_id):
    user = current_user
    order = InventoryOperation.query.options(
        joinedload(InventoryOperation.store1),
        joinedload(InventoryOperation.store2),
        joinedload(InventoryOperation.user),
        joinedload(InventoryOperation.details).options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(
                ProductsUnit.unit1
            ),
            # Aquí cargamos la información del esquema toolbox
            joinedload(InventoryOperationDetail.failure_info),
        ),
    ).get_or_404(order_id)

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
            },
            paper_format="Letter",
            orientation="Portrait",
        ),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=chequeo_traslado_{order.correlative}.pdf"
        },
    )


@inventory_bp.route("/products_locations", methods=["GET", "POST"])
@login_required
def products_locations():

    stores = Store.query.all()

    store_code = request.values.get("store_code")
    location = request.values.get("location")

    if store_code:
        store_obj = Store.query.filter_by(code=store_code).first()

        if not store_obj:
            flash("Depósito no válido.", "error")
            return render_template("products_locations.html", stores=stores)

        if location:
            return render_template(
                "products_locations.html",
                stores=stores,
                store=store_obj,
                location=location,
            )

        return render_template(
            "products_locations.html",
            stores=stores,
            store=store_obj,
        )

    return render_template("products_locations.html", stores=stores)


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

    products_count = 0
    try:
        for code in products:
            pf = ProductsFailure.query.filter_by(
                product_code=code, store_code=store_code
            ).first()

            # actualiza la ubicación del producto en products_failure
            if pf:
                pf.location = location
            else:
                pf = ProductsFailure(
                    product_code=code,
                    store_code=store_code,
                    minimal_stock=0,
                    maximum_stock=0,
                    location=location,
                )
                db.session.add(pf)
            products_count += 1

        db.session.commit()
        # Redirigir con los parámetros de GET para mantener el estado
        return redirect(
            url_for(
                "inventory.products_locations", store_code=store_code, location=location
            )
        )
    except Exception as e:
        db.session.rollback()
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

    # Resolver código alterno a código principal
    products_code = ProductsCode.query.filter_by(other_code=product_code).first()
    main_code = products_code.main_code if products_code else product_code

    product = Product.query.filter_by(code=main_code).first()

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

    # Obtener ubicación actual si existe
    store_code = request.args.get("store_code")

    pf = None
    if store_code:
        pf = ProductsFailure.query.filter_by(
            product_code=main_code, store_code=store_code
        ).first()

    return render_template("partials/product_row_location.html", product=product, pf=pf)


@inventory_bp.route("/product_counter", methods=["GET", "POST"])
@login_required
def product_counter():
    stores = Store.query.all()
    store_code = request.values.get("store_code")
    store = Store.query.filter_by(code=store_code).first() if store_code else None

    # Reconstruir filas desde sesión para el usuario actual y el depósito seleccionado
    counter_rows_html = ""
    if store:
        user_code = current_user.code
        all_counters = session.get("product_counter", {}) or {}
        user_counters = all_counters.get(user_code, {}) or {}
        store_counters = user_counters.get(store.code, {}) or {}

        rows = []
        for code, item in store_counters.items():
            product_row = Product.query.filter_by(code=code).first()
            if not product_row:
                continue

            unit_rel = ProductsUnit.query.filter_by(product_code=code, main_unit=True).first()

            if isinstance(item, dict):
                qty = float(item.get("counted", 0))
                sys_q = float(item.get("system_qty", 0))
                diff = float(item.get("difference", qty - sys_q))
            else:
                qty = float(item)
                sys_q = 0.0
                diff = qty - sys_q

            rows.append(
                render_template(
                    "partials/product_counter_row.html",
                    product=product_row,
                    system_qty=sys_q,
                    unit=unit_rel.unit1 if unit_rel else None,
                    counted_amount=qty,
                    difference=diff,
                    store_code=store.code,
                )
            )

        counter_rows_html = "".join(rows)

    return render_template(
        "product_counter.html",
        stores=stores,
        store=store,
        store_code=store_code,
        counter_rows_html=counter_rows_html,
    )


@inventory_bp.route("/product_counter/search_product_counter/<store_code>")
@login_required
def search_product_counter(store_code):
    product_code = request.args.get("product_code", "").strip()

    # Resolver código alterno a código principal    
    products_code = ProductsCode.query.filter_by(other_code=product_code).first()
    main_code = products_code.main_code if products_code else product_code  

    product_info = Product.query.filter_by(code=main_code).first() 
    
    store = Store.query.filter_by(code=store_code).first()

    stock = ProductsStock.query.filter_by(product_code=main_code, store=store_code).first()
    unit = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()

    unit_value = unit.unit1 if unit is not None else None
    return render_template("partials/product_counter_modal.html", product=product_info, stock=stock, unit=unit_value, store=store)

    
    
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

    # Obtener datos de producto (no necesitamos volver a leer el stock)
    product_info = Product.query.filter_by(code=product_code).first()
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

    # Reconstruir todas las filas para ese depósito a partir de la sesión
    rows = []
    for code, item in store_counters.items():
        product_row = Product.query.filter_by(code=code).first()
        if not product_row:
            continue

        unit_rel = ProductsUnit.query.filter_by(product_code=code, main_unit=True).first()

        # Compatibilidad: si todavía hay datos antiguos (solo cantidad), recalcular
        if isinstance(item, dict):
            qty = float(item.get("counted", 0))
            sys_q = float(item.get("system_qty", 0))
            diff = float(item.get("difference", qty - sys_q))
        else:
            qty = float(item)
            sys_q = 0.0
            diff = qty - sys_q

        rows.append(
            render_template(
                "partials/product_counter_row.html",
                product=product_row,
                system_qty=sys_q,
                unit=unit_rel.unit1 if unit_rel else None,
                counted_amount=qty,
                difference=diff,
                store_code=store_code,
            )
        )

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


@inventory_bp.route("/product_counter/clear_counter", methods=["POST"])
@login_required
def clear_product_counter():
    """Limpia todos los contadores de productos en sesión."""
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    if user_code in all_counters:
        all_counters.pop(user_code, None)
        session["product_counter"] = all_counters
    return ""


@inventory_bp.route("/product_counter/save_counter/<store_code>", methods=["POST"])
@login_required 
def save_products_counter(store_code):
    """Guarda el conteo de productos en la base de datos o lo procesa según la lógica de negocio."""
    user_code = current_user.code
    all_counters = session.get("product_counter", {}) or {}
    user_counters = all_counters.get(user_code, {}) or {}
    store_counters = user_counters.get(store_code, {}) or {}

    # Agrupar por tipo de diferencia para el usuario actual en este depósito
    positive_diffs = {}  # diferencia > 0 (sobrante)
    negative_diffs = {}  # diferencia < 0 (faltante)
    zero_diffs = {}      # diferencia == 0 (sin ajuste)

    print(f"Guardando conteo para depósito {store_code} (usuario {user_code}):")
    for code, item in store_counters.items():
        if isinstance(item, dict):
            system_qty = float(item.get("system_qty", 0) or 0)
            counted = float(item.get("counted", 0) or 0)
            difference = float(item.get("difference", counted - system_qty) or 0)
        else:
            # Compatibilidad con datos antiguos: solo cantidad contada
            counted = float(item or 0)
            system_qty = 0.0
            difference = counted - system_qty

        # Clasificar por signo de la diferencia
        if difference > 0:
            positive_diffs[code] = {
                "system_qty": system_qty,
                "counted": counted,
                "difference": difference,
            }



        elif difference < 0:
            negative_diffs[code] = {
                "system_qty": system_qty,
                "counted": counted,
                "difference": difference,
            }
        else:
            zero_diffs[code] = {
                "system_qty": system_qty,
                "counted": counted,
                "difference": difference,
            }

        print(
            f" - Producto {code}: inventario={system_qty}, contada={counted}, diferencia={difference}"
        )

    # Si no hay diferencias, no generamos operaciones
    if not positive_diffs and not negative_diffs:
        flash("No hay diferencias de inventario para procesar.", "info")
        return redirect(url_for("inventory.product_counter"))

    store = Store.query.filter_by(code=store_code).first()

    # Preparar SQL para cabecera y detalle (mismo patrón que auto_order_collection)
    sql_header = text(
        """
        SELECT set_inventory_operation(:p_correlative, :p_operation_type, :p_document_no, 
        :p_emission_date, :p_wait, :p_description, :p_user_code, :p_station, :p_store, :p_locations, 
        :p_destination_store, :p_destination_location, :p_operation_comments, :p_total_amount, 
        :p_total_net, :p_total_tax, :p_total, :p_coin_code, :p_internal_use)
        """
    )

    sql_detail = text(
        """
        SELECT set_inventory_operation_details(:p_main_correlative, :p_line, :p_code_product, 
        :p_description_product, :p_referenc, :p_mark, :p_model, :p_amount, :p_store, :p_locations, 
        :p_destination_store, :p_destination_location, :p_unit, :p_conversion_factor, :p_unit_type, 
        :p_unitary_cost, :p_buy_tax, :p_aliquot, :p_total_cost, :p_total_tax, :p_total, :p_coin_code, 
        :p_change_price)
        """
    )

    load_correlative = None
    download_correlative = None

    try:
        # Operación de CARGA (sobrantes)
        if positive_diffs:
            header_params_load = {
                "p_correlative": None,
                "p_operation_type": "LOAD",  # tipo lógico para ajustes de carga
                "p_document_no": None,
                "p_emission_date": datetime.now().date(),
                "p_wait": True,
                "p_description": f"Ajuste de inventario (Sobrantes) {store.description if store else store_code}",
                "p_user_code": user_code,
                "p_station": "00",
                "p_store": store_code,
                "p_locations": "00",
                "p_destination_store": store_code,
                "p_destination_location": "00",
                "p_operation_comments": "Generado desde conteo físico Toolbox (sobrantes)",
                "p_total_amount": 0.0,
                "p_total_net": 0.0,
                "p_total_tax": 0.0,
                "p_total": 0.0,
                "p_coin_code": "02",
                "p_internal_use": False,
            }

            load_correlative = db.session.execute(sql_header, header_params_load).scalar()
            if not load_correlative:
                raise Exception("La DB no devolvió ID de operación de carga.")

            for code, data in positive_diffs.items():
                # Obtener datos maestros del producto
                data_row = (
                    db.session.query(ProductsUnit, Product, Tax)
                    .join(Product, ProductsUnit.product_code == Product.code)
                    .outerjoin(Tax, Product.buy_tax == Tax.code)
                    .filter(ProductsUnit.product_code == code, ProductsUnit.main_unit == True)
                    .first()
                )

                if not data_row:
                    print(f"OMITIDO (carga): {code} falta info maestra.")
                    continue

                pu, prod, tax = data_row

                detail_params = {
                    "p_main_correlative": load_correlative,
                    "p_line": 0,
                    "p_code_product": code,
                    "p_description_product": prod.description,
                    "p_referenc": prod.referenc,
                    "p_mark": prod.mark,
                    "p_model": prod.model,
                    "p_amount": float(data["difference"]),  # sobrante > 0
                    "p_store": store_code,
                    "p_locations": "00",
                    "p_destination_store": store_code,
                    "p_destination_location": "00",
                    "p_unit": int(pu.correlative),
                    "p_conversion_factor": 0.0,
                    "p_unit_type": 0,
                    "p_unitary_cost": 0.0,
                    "p_buy_tax": prod.buy_tax,
                    "p_aliquot": tax.aliquot if tax else 0.0,
                    "p_total_cost": 0.0,
                    "p_total_tax": 0.0,
                    "p_total": 0.0,
                    "p_coin_code": "02",
                    "p_change_price": False,
                }
                db.session.execute(sql_detail, detail_params)

        # Operación de DESCARGA (faltantes)
        if negative_diffs:
            header_params_down = {
                "p_correlative": None,
                "p_operation_type": "DOWNLOAD",  # tipo lógico para ajustes de descarga
                "p_document_no": None,
                "p_emission_date": datetime.now().date(),
                "p_wait": True,
                "p_description": f"Ajuste de inventario (Faltantes) {store.description if store else store_code}",
                "p_user_code": user_code,
                "p_station": "00",
                "p_store": store_code,
                "p_locations": "00",
                "p_destination_store": store_code,
                "p_destination_location": "00",
                "p_operation_comments": "Generado desde conteo físico Toolbox (faltantes)",
                "p_total_amount": 0.0,
                "p_total_net": 0.0,
                "p_total_tax": 0.0,
                "p_total": 0.0,
                "p_coin_code": "02",
                "p_internal_use": False,
            }

            download_correlative = db.session.execute(sql_header, header_params_down).scalar()
            if not download_correlative:
                raise Exception("La DB no devolvió ID de operación de descarga.")

            for code, data in negative_diffs.items():
                data_row = (
                    db.session.query(ProductsUnit, Product, Tax)
                    .join(Product, ProductsUnit.product_code == Product.code)
                    .outerjoin(Tax, Product.buy_tax == Tax.code)
                    .filter(ProductsUnit.product_code == code, ProductsUnit.main_unit == True)
                    .first()
                )

                if not data_row:
                    print(f"OMITIDO (descarga): {code} falta info maestra.")
                    continue

                pu, prod, tax = data_row

                detail_params = {
                    "p_main_correlative": download_correlative,
                    "p_line": 0,
                    "p_code_product": code,
                    "p_description_product": prod.description,
                    "p_referenc": prod.referenc,
                    "p_mark": prod.mark,
                    "p_model": prod.model,
                    "p_amount": abs(float(data["difference"])),  # usar valor absoluto de la diferencia negativa
                    "p_store": store_code,
                    "p_locations": "00",
                    "p_destination_store": store_code,
                    "p_destination_location": "00",
                    "p_unit": int(pu.correlative),
                    "p_conversion_factor": 0.0,
                    "p_unit_type": 0,
                    "p_unitary_cost": 0.0,
                    "p_buy_tax": prod.buy_tax,
                    "p_aliquot": tax.aliquot if tax else 0.0,
                    "p_total_cost": 0.0,
                    "p_total_tax": 0.0,
                    "p_total": 0.0,
                    "p_coin_code": "02",
                    "p_change_price": False,
                }
                db.session.execute(sql_detail, detail_params)

        # Registrar / actualizar historial de conteo por producto
        today = datetime.now().date()
        # Identificador lógico para este conteo (mismo para todos los productos de esta ejecución)
        count_batch_id = str(uuid4())
        for code, item in store_counters.items():
            if isinstance(item, dict):
                system_qty = float(item.get("system_qty", 0) or 0)
                counted = float(item.get("counted", 0) or 0)
                difference = float(item.get("difference", counted - system_qty) or 0)
            else:
                counted = float(item or 0)
                system_qty = 0.0
                difference = counted - system_qty

            history = ProductsCounterHistory.query.filter_by(
                product_code=code, store_code=store_code
            ).first()
            if not history:
                history = ProductsCounterHistory(
                    product_code=code,
                    store_code=store_code,
                    user_code=user_code,
                )
                db.session.add(history)

            history.user_code = user_code
            history.count_batch_id = count_batch_id
            history.count_date = today
            history.system_qty = system_qty
            history.counted_qty = counted
            history.difference = difference

            # Asociar operaciones de carga/descarga según el signo de la diferencia
            if difference > 0 and load_correlative:
                history.operation_correlative_up = load_correlative
                history.operation_correlative_down = None
            elif difference < 0 and download_correlative:
                history.operation_correlative_down = download_correlative
                history.operation_correlative_up = None
            else:
                # Sin ajuste
                history.operation_correlative_up = None
                history.operation_correlative_down = None

        db.session.commit()
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

        # Si la petición viene por HTMX, devolvemos la vista limpia (selector de depósito)
        # y disparamos el evento open-pdf para abrir el reporte del conteo en una nueva pestaña.
        if request.headers.get("HX-Request"):
            resp = make_response(
                render_template(
                    "product_counter.html",
                    stores=Store.query.all(),
                    store=None,
                    store_code=None,
                    counter_rows_html="",
                )
            )
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
            return resp

        # Flujo normal (no HTMX): redirigir directamente al PDF del conteo
        return redirect(
            url_for(
                "inventory.product_counter_report_pdf",
                count_batch_id=count_batch_id,
            )
        )

    except Exception as e:
        db.session.rollback()
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
    items = (
        ProductsCounterHistory.query.filter_by(count_batch_id=count_batch_id)
        .options(
            joinedload(ProductsCounterHistory.product),
            joinedload(ProductsCounterHistory.store),
            joinedload(ProductsCounterHistory.user),
            joinedload(ProductsCounterHistory.load_operation),
            joinedload(ProductsCounterHistory.download_operation),
        )
        .all()
    )

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
    download_op = next((h.download_operation for h in items if h.download_operation), None)

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

    user = current_user
    history_records = ProductsCounterHistory.query.filter_by(count_batch_id=count_batch_id).all()

    if not history_records:
        flash(f"No se encontraron datos de conteo para el ID {count_batch_id}.", "warning")
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

    