from flask import render_template, request, flash, redirect, url_for, Response
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
                "form_select_order_check_oc.html", order=order_details, error=error
            )
        else:
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
                .where(io.correlative == order_id)
            )
            
            results = db.session.execute(stmt).all()

            if not results:
                error = f"No se encontró la orden con ID {order_id} o no contiene detalles."
                return render_template(
                    "form_select_order_check_oc.html", order=order_details, error=error
                )
            else:
                # El primer resultado contiene la información de cabecera
                order_header = results[0]
                order_details = results

        return render_template(
            "check_order_collection.html", 
            order=order_header, 
            details=order_details, 
            error=error
        )
    return render_template("form_select_order_check_oc.html")


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
    
    if not order_id:
        flash("ID de orden inválido.", "error")
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
    
    db.session.commit()
    
    flash("Orden actualizada con las cantidades contadas.", "success")
    return redirect(url_for("inventory.index"))