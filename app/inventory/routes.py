from flask import render_template, request, flash, redirect, url_for, Response, make_response
import json
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
    ProductsCode,
)

from app.reports.utils import render_pdf, generate_barcode


@inventory_bp.route("/")
@login_required
def index():
    return render_template("index.html")


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

        # HTMX: devolver la vista limpia y disparar un evento para abrir el PDF en nueva pestaña
        if request.headers.get("HX-Request"):
            resp = make_response(
                render_template(
                    "auto_order_collection.html",
                    store_origin=None,
                    store_dst=None,
                    store_origin_name="",
                    store_dst_name="",
                    products=[],
                    departments=[],
                    marks=[],
                    stores=Store.query.all(),
                    new_order_id=document_no,
                )
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
        return redirect(url_for("inventory.order_collection_report", order_id=document_no))

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
            error=error
        )

    return render_template("check_order_collection.html", order=None, details=[], error=None)


@inventory_bp.route("/search_product", methods=["GET"])
@login_required
def search_product():
    code_product = request.args.get("code-product")
    order_id = request.args.get("order_id", type=int)
    
    if not code_product or not order_id:
        return render_template("partials/check_order_product_modal.html", item=None, product_description="", unit_description="", order=None)
    
    # Buscar el código principal del producto usando products_codes
    products_code = ProductsCode.query.filter_by(other_code=code_product).first()
    main_code = products_code.main_code if products_code else code_product
    
    # Buscar el producto en los detalles de la orden usando el código principal
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=order_id, code_product=main_code
    ).first()
    
    if not detail:
        # Producto no encontrado en la orden, validar existencia en catálogo
        product = Product.query.filter_by(code=main_code).first()
        if not product:
            error_payload = {
                "product-error": {
                    "message": "El producto ingresado no existe en la base de datos.",
                    "focus_id": "code-product",
                }
            }
            return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"})
        
        # Obtener la orden
        order = InventoryOperation.query.get(order_id)
        if not order:
            return render_template("partials/check_order_product_modal.html", item=None, product_description="Orden no encontrada.", unit_description="", order=None, is_new=False)
        
        # Obtener unidad principal
        pu = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()
        if not pu:
            return render_template("partials/check_order_product_modal.html", item=None, product_description="Unidad principal no encontrada para el producto.", unit_description="", order=None, is_new=False)
        
        unit = Unit.query.filter_by(code=pu.unit).first()
        
        # Obtener cantidad en depósito origen
        stock = ProductsStock.query.filter_by(product_code=main_code, store=order.store).first()
        stock_amount = stock.stock if stock else 0.0
        
        # Renderizar modal para agregar
        return render_template("partials/check_order_product_modal.html", 
                               item=None, 
                               product_description=product.description,
                               unit_description=unit.description if unit else "Desconocida",
                               order=order,
                               is_new=True,
                               main_code=main_code,
                               stock_amount=stock_amount)
    
    # Obtener descripción del producto y unidad
    product = Product.query.filter_by(code=main_code).first()
    unit = Unit.query.join(ProductsUnit).filter(ProductsUnit.correlative == detail.unit).first()

    # Obtener cantidad en depósito origen para validación de conteo
    stock = ProductsStock.query.filter_by(product_code=main_code, store=detail.store).first()
    stock_amount = stock.stock if stock else 0.0
    
    # Renderizar el modal con datos
    return render_template("partials/check_order_product_modal.html", 
                           item=detail, 
                           product_description=product.description if product else "Desconocido",
                           unit_description=unit.description if unit else "Desconocida",
                           order=InventoryOperation.query.get(order_id),
                           stock_amount=stock_amount)


@inventory_bp.route("/add_product_to_order", methods=["POST"])
@login_required
def add_product_to_order():
    order_id = request.form.get("order_id", type=int)
    code_product = request.form.get("code_product")
    
    print(f"Agregando producto: order_id={order_id}, code_product={code_product}")
    
    if not order_id or not code_product:
        print("Datos incompletos")
        error_payload = {
            "product-error": {
                "message": "Error: datos incompletos para agregar el producto.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})
    
    # Buscar el código principal
    products_code = ProductsCode.query.filter_by(other_code=code_product).first()
    main_code = products_code.main_code if products_code else code_product
    
    print(f"Main code: {main_code}")
    
    # Verificar si ya existe
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=order_id, code_product=main_code
    ).first()
    
    if detail:
        print("Producto ya agregado")
        error_payload = {
            "product-error": {
                "message": "Producto ya agregado en la orden.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=409, headers={"HX-Trigger": json.dumps(error_payload)})
    
    # Obtener datos
    product = Product.query.filter_by(code=main_code).first()
    order = InventoryOperation.query.get(order_id)
    pu = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()
    
    if not product:
        error_payload = {
            "product-error": {
                "message": "El producto ingresado no existe en la base de datos.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload)})

    if not order:
        error_payload = {
            "product-error": {
                "message": "Orden no encontrada. Vuelve a cargar el correlativo.",
                "focus_id": "order_id",
            }
        }
        return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload)})

    if not pu:
        error_payload = {
            "product-error": {
                "message": "Unidad principal no encontrada para el producto.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})

    tax = Tax.query.filter_by(code=product.buy_tax).first() if product.buy_tax else None
    
    print(f"Product: {product}, Order: {order}, PU: {pu}, Tax: {tax}")

    # Validar stock en depósito de origen
    stock = ProductsStock.query.filter_by(product_code=main_code, store=order.store).first()
    stock_amount = stock.stock if stock else 0.0
    if stock_amount <= 0:
        error_payload = {
            "product-error": {
                "message": "No hay stock disponible en el depósito de origen para este producto.",
                "focus_id": "code-product",
            }
        }
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})
    
    try:
        # Calcular siguiente línea respetando la restricción unique de la columna line (es global, no por orden)
        max_line_global = db.session.query(func.max(InventoryOperationDetail.line)).scalar()
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
            locations='00',
            destination_store=order.destination_store,
            destination_location='00',
            unit=pu.correlative,
            conversion_factor=0.0,
            unit_type=0,
            unitary_cost=0.0,
            buy_tax=product.buy_tax,
            aliquot=tax.aliquot if tax else 0.0,
            total_cost=0.0,
            total_tax=0.0,
            total=0.0,
            coin_code='02',
            change_price=False
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
        return Response("", status=500, headers={"HX-Trigger": json.dumps(error_payload)})


@inventory_bp.route("/update_counted_amount", methods=["POST"])
@login_required
def update_counted_amount():
    order_id = request.form.get("order_id", type=int)
    code_product = request.form.get("code_product")
    counted_amount = request.form.get("counted_amount", type=float)
    
    if not order_id or not code_product or counted_amount is None:
        return "Error: Datos incompletos."
    
    # Actualizar el detalle (por ahora, solo en memoria, pero luego en BD)
    # Para simplificar, devolver HTML actualizado para la fila
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=order_id, code_product=code_product
    ).first()
    
    if not detail:
        return "Producto no encontrado."

    # Validar stock en depósito de origen
    stock = ProductsStock.query.filter_by(product_code=code_product, store=detail.store).first()
    stock_amount = stock.stock if stock else 0.0
    if counted_amount > stock_amount:
        error_payload = {
            "counted-error": {
                "message": f"La cantidad contada no puede ser mayor que el stock en el depósito de origen ({stock_amount:.2f}).",
                "focus_id": "counted-amount",
            }
        }
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})
    
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
    code_product = request.form.get("code_product")
    
    if not order_id or not code_product:
        return "Error: Datos incompletos.", 400
    
    # Eliminar de la BD
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=order_id, code_product=code_product
    ).first()
    
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
            code_product = key[8:]  # Remove "counted_"
            counted_amount = float(value) if value else 0
            
            detail = InventoryOperationDetail.query.filter_by(
                main_correlative=order_id, code_product=code_product
            ).first()
            
            if detail:
                # Actualizar amount con la cantidad contada
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
            return render_template("check_transfer_operation.html", show_products=False, error_message="No se encontró una operación de traslado procesado con ese correlativo.")
        
        # Obtener detalles con productos
        details = InventoryOperationDetail.query.filter_by(
            main_correlative=operation.correlative
        ).options(
            joinedload(InventoryOperationDetail.product),
            joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1)
        ).all()
        
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


@inventory_bp.route("/check_transfer_operation/search_product/<int:operation_id>")
@login_required
def search_product_in_transfer(operation_id):
    product_code = request.args.get("product_code")
    if not product_code:
        error_payload = {
            "search-error": {
                "message": "Código de producto requerido.",
                "focus_id": "product_code",
            }
        }
        return Response("", status=400, headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"})
    
    # Buscar el producto en la operación
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=operation_id,
        code_product=product_code
    ).options(
        joinedload(InventoryOperationDetail.product),
        joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1)
    ).first()
    
    if not detail:
        error_payload = {
            "search-error": {
                "message": "Producto no encontrado en esta operación.",
                "focus_id": "product_code",
            }
        }
        return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"})
    
    ##busca parametros de existencia minimia y maxima en el deposito de destino 
    failure_info = ProductsFailure.query.filter_by(product_code=product_code, store_code=detail.destination_store).first()

    
    # Devolver el modal renderizado
    # return render_template("partials/product_modal.html", 
    #                      detail=detail, 
    #                      operation_id=operation_id,
    #                      destination_store=detail.destination_store,
    #                      product_failure=failure_info)
    return redirect(url_for("inventory.product_modal", operation_id=operation_id, product_code=product_code))


@inventory_bp.route("/check_transfer_operation/modal/<int:operation_id>/<product_code>", methods=["GET"])
@login_required
def product_modal(operation_id, product_code):
    # Buscar el producto en la operación
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=operation_id,
        code_product=product_code
    ).options(
        joinedload(InventoryOperationDetail.product),
        joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1)
    ).first()
    
    if not detail:
        return "Producto no encontrado", 404
    
    failure_info = ProductsFailure.query.filter_by(product_code=product_code, store_code=detail.destination_store).first()
    
    return render_template("partials/product_modal.html", 
                         detail=detail, 
                         operation_id=operation_id,
                         product_failure=failure_info,
                         destination_store=detail.destination_store
                         )


@inventory_bp.route("/check_transfer_operation/update_count/<int:operation_id>/<path:product_code>/<destination_store>", methods=["POST"])
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
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})
    
    # Verificar que el producto existe en la operación
    detail = InventoryOperationDetail.query.filter_by(
        main_correlative=operation_id,
        code_product=product_code
    ).first()
    
    if not detail:
        error_payload = {
            "counted-error": {
                "message": "Producto no encontrado en esta operación.",
                "focus_id": "countedAmount",
            }
        }
        return Response("", status=422, headers={"HX-Trigger": json.dumps(error_payload)})
    
    ##actualiza products_failures 
    failure_info = ProductsFailure.query.filter_by(product_code=product_code, store_code=destination_store).first()

    if not failure_info:
        failure_info = ProductsFailure(
            product_code=product_code,
            store_code=destination_store,
            minimal_stock=minimal_stock or 0,
            maximum_stock=maximum_stock or 0,
            location=""
        )
        db.session.add(failure_info)
    else:
        failure_info.minimal_stock = minimal_stock or 0
        failure_info.maximum_stock = maximum_stock or 0

    db.session.commit()

    # Como es solo informativo, no guardamos en BD
    # Si no hay diferencia, devolvemos vacío para eliminar la fila
    if counted_amount == detail.amount:
        return ""

    # Si hay diferencia, devolvemos la fila actualizada con fondo rojo
    return render_template(
        "partials/table_row.html",
        detail=detail,
        counted_amount=counted_amount,
    )



@inventory_bp.route("/product_params", methods=["GET", "POST"])
@login_required
def product_params():
    stores = Store.query.all()
    
    if request.method == 'POST':
        store_code = request.form.get('store_code')
        code_product = request.form.get('code-product')

        if store_code and not code_product:
            selected_store = Store.query.filter_by(code=store_code).first()
            return render_template("product_params.html", stores=stores, selected_store=selected_store)
        

        if code_product and store_code:
            # Buscar código principal si es código alterno
            products_code = ProductsCode.query.filter_by(other_code=code_product).first()
            main_code = products_code.main_code if products_code else code_product
            
            product = Product.query.filter_by(code=main_code).first()
            if not product:
                flash("Producto no encontrado.", "error")
                selected_store = Store.query.filter_by(code=store_code).first()
                return render_template("product_params.html", stores=stores, selected_store=selected_store)
            
            product_failure = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()
            product_stock = ProductsStock.query.filter_by(product_code=main_code, store=store_code).first()

            product_params = {
                "code": main_code,
                "description": product.description,
                "referenc": product.referenc,
                "mark": product.mark,
                "model": product.model,
                "stock": product_stock.stock if product_stock else 0,
                "minimal_stock": product_failure.minimal_stock if product_failure and product_failure.minimal_stock is not None else 0,
                "maximum_stock": product_failure.maximum_stock if product_failure and product_failure.maximum_stock is not None else 0,
                "location": product_failure.location if product_failure and product_failure.location and product_failure.location else "",
            }
            selected_store = Store.query.filter_by(code=store_code).first()
            return render_template("product_params.html", product_params=product_params, selected_store=selected_store, stores=stores)

    return render_template("product_params.html", stores=stores, selected_store=None)


@inventory_bp.route("/product_params/save", methods=["POST"])
@login_required
def save_product_params():
    store_code = request.form.get('store_code')
    code_product = request.form.get('code-product')
    
    if not store_code or not code_product:
        flash("Datos incompletos.", "error")
        return redirect(url_for('inventory.product_params'))
    
    # Buscar código principal si es código alterno
    products_code = ProductsCode.query.filter_by(other_code=code_product).first()
    main_code = products_code.main_code if products_code else code_product
    
    # Guardar parámetros para el producto específico
    min_stock = request.form.get('minimal_stock', '0').strip()
    max_stock = request.form.get('maximum_stock', '0').strip()
    location = request.form.get('location', '').strip()
    
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
        product_failure = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()
        product_stock = ProductsStock.query.filter_by(product_code=main_code, store=store_code).first()
        
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
        return render_template("product_params.html", stores=stores, selected_store=selected_store, product_params=product_params)
    
    if min_stock > max_stock:
        flash("El stock mínimo no puede ser mayor que el máximo.", "error")
        # Recargar la página con los datos actuales
        product = Product.query.filter_by(code=main_code).first()
        product_failure = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()
        product_stock = ProductsStock.query.filter_by(product_code=main_code, store=store_code).first()
        
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
        return render_template("product_params.html", stores=stores, selected_store=selected_store, product_params=product_params)
    
    pf = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()
    
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
            location=location
        )
        db.session.add(pf)
    
    db.session.commit()
    flash("Parámetros del producto guardados correctamente.", "success")
    
    # Limpiar la búsqueda y mostrar solo el input para buscar otro producto
    selected_store = Store.query.filter_by(code=store_code).first()
    stores = Store.query.all()
    return render_template("product_params.html", stores=stores, selected_store=selected_store)


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

    #validaciones 
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
            pf = ProductsFailure.query.filter_by(product_code=code, store_code=store_code).first()
            
            #actualiza la ubicación del producto en products_failure    
            if pf:
                pf.location = location
            else:
                pf = ProductsFailure(
                    product_code=code,
                    store_code=store_code,
                    minimal_stock=0,
                    maximum_stock=0,
                    location=location
                )
                db.session.add(pf)
            products_count += 1

        db.session.commit()        
        # Redirigir con los parámetros de GET para mantener el estado
        return redirect(url_for("inventory.products_locations", store_code=store_code, location=location))
    except Exception as e:
        db.session.rollback()
        flash("Error al actualizar ubicaciones. Intente nuevamente.", "error")
        print(f"Error updating product locations: {e}")
        return redirect(url_for("inventory.products_locations", store_code=store_code, location=location))
    


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
        return Response("", status=400, headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"})

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
        return Response("", status=404, headers={"HX-Trigger": json.dumps(error_payload), "HX-Reswap": "none"})
    
    # Obtener ubicación actual si existe
    store_code = request.args.get("store_code")
    
    pf = None
    if store_code:
        pf = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()

    return render_template("partials/product_row_location.html", product=product, pf=pf)
    