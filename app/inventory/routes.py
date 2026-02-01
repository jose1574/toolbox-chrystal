from flask import render_template, request, flash, redirect, url_for, Response
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from sqlalchemy import select, case, func, text
from sqlalchemy.orm import aliased, joinedload
from app.inventory import inventory_bp
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
)

from app.reports.utils import render_pdf, generate_barcode


@inventory_bp.route("/")
@login_required
def index():
    return render_template("index.html")


@inventory_bp.route("/auto_order_collection/select_stores", methods=["GET", "POST"])
@login_required
def select_stores():
    stores = Store.query.all()
    error = None
    # Correlativo de la última orden guardada (si aplica)
    new_order_id = request.args.get("new_order_id")

    if request.method == "POST":
        store_origin = request.form.get("store_origin")
        store_dst = request.form.get("store_dst")

        if not store_origin or not store_dst:
            error = "Por favor, selecciona ambos depósitos."
            return render_template("select_stores.html", stores=stores, error=error)
        if store_origin == store_dst:
            error = "El depósito de origen y destino no pueden ser el mismo."
            return render_template("select_stores.html", stores=stores, error=error)

        return redirect(
            url_for(
                "inventory.auto_order_collection",
                store_origin=store_origin,
                store_dst=store_dst,
            )
        )
    return render_template(
        "select_stores.html", stores=stores, error=error, new_order_id=new_order_id
    )


@inventory_bp.route("/auto_order_collection", methods=["GET", "POST"])
@login_required
def auto_order_collection():
    if request.method == "POST":
        # Procesar los productos seleccionados
        # Los productos vienen como 'codigo': 'selected' y las cantidades como 'qty_codigo'
        store_origin = request.form.get("store_origin")
        store_dst = request.form.get("store_dst")

        selected_items = []
        for key, value in request.form.items():
            if value == "selected":
                product_code = key
                quantity = request.form.get(f"qty_{product_code}", 0, type=float)
                if quantity > 0:
                    selected_items.append({"code": product_code, "quantity": quantity})

        if not selected_items:
            flash("No se seleccionaron productos o cantidades válidas.", "warning")
            return redirect(
                url_for(
                    "inventory.auto_order_collection",
                    store_origin=store_origin,
                    store_dst=store_dst,
                )
            )

        # Aquí iría la lógica para crear el documento de transferencia
        # Por ahora simulamos éxito
        flash(
            f"Se han procesado {len(selected_items)} productos para transferencia.",
            "success",
        )
        return redirect(url_for("inventory.index"))

    store_origin = request.args.get("store_origin")
    store_dst = request.args.get("store_dst")
    stock_orig = aliased(ProductsStock)
    stock_dst = aliased(ProductsStock)
    pf = aliased(ProductsFailure)
    m = aliased(Mark)
    d = aliased(Department)
    u = aliased(Unit)
    pu = aliased(ProductsUnit)

    # Definir lógica de cálculo para evitar repetición
    needed = pf.maximum_stock - func.coalesce(stock_dst.stock, 0)

    stmt = (
        select(
            Product.code,
            Product.description,
            Product.mark.label("mark_code"),
            Product.department.label("department_code"),
            m.description.label("mark_description"),
            d.description.label("department_description"),
            u.description.label("unit_description"),
            stock_orig.stock.label("stock_origin"),
            func.coalesce(stock_dst.stock, 0).label("stock_destination"),
            pf.minimal_stock.label("minimum_stock"),
            pf.maximum_stock.label("maximum_stock"),
            case((needed > stock_orig.stock, stock_orig.stock), else_=needed).label(
                "to_transfer"
            ),
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

    # Obtenemos todas las filas. No usamos .scalars() porque queremos todas las columnas.
    results = db.session.execute(stmt).all()

    # Extraer departamentos y marcas únicos presentes en los resultados para los filtros
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
        products=results,
        departments=unique_depts,
        marks=unique_marks,
    )


@inventory_bp.route("/auto_order_collection/save", methods=["POST"])
@login_required
def save_auto_order_collection():
    store_origin = request.form.get("store_origin")
    store_dst = request.form.get("store_dst")

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
        flash("No se han seleccionado productos válidos.", "warning")
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
            "p_description": f"Transferencia Auto {store_origen_obj.description} -> {store_dst_obj.description}",
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
        # Volver a la selección de depósitos y abrir el PDF en nueva pestaña
        return redirect(url_for("inventory.select_stores", new_order_id=document_no))

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
