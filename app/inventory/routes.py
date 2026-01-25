from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from sqlalchemy import select, case, func, and_
from sqlalchemy.orm import aliased
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
)


@inventory_bp.route("/")
@login_required
def index():
    return render_template("index.html")


@inventory_bp.route("/auto_order_collection/select_stores", methods=["GET", "POST"])
@login_required
def select_stores():
    stores = Store.query.all()
    error = None

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

    return render_template("select_stores.html", stores=stores, error=error)


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
                    selected_items.append({
                        "code": product_code,
                        "quantity": quantity
                    })
        
        if not selected_items:
            flash("No se seleccionaron productos o cantidades válidas.", "warning")
            return redirect(url_for('inventory.auto_order_collection', store_origin=store_origin, store_dst=store_dst))

        # Aquí iría la lógica para crear el documento de transferencia
        # Por ahora simulamos éxito
        flash(f"Se han procesado {len(selected_items)} productos para transferencia.", "success")
        return redirect(url_for('inventory.index'))

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
            case(
                (needed > stock_orig.stock, stock_orig.stock),
                else_=needed
            ).label("to_transfer")
        )
        .join(stock_orig, (Product.code == stock_orig.product_code) & (stock_orig.store == store_origin))
        .outerjoin(stock_dst, (Product.code == stock_dst.product_code) & (stock_dst.store == store_dst))
        .outerjoin(pf, (Product.code == pf.product_code) & (pf.store_code == store_dst))
        .join(pu, (Product.code == pu.product_code) & (pu.main_unit == True))
        .join(u, pu.unit == u.code)
        .join(d, Product.department == d.code)
        .outerjoin(m, Product.mark == m.code)
        .where(
            (stock_orig.stock > 0) &
            (func.coalesce(stock_dst.stock, 0) < pf.minimal_stock) &
            (needed > 0)
        )
    )

    # Obtenemos todas las filas. No usamos .scalars() porque queremos todas las columnas.
    results = db.session.execute(stmt).all()

    # Extraer departamentos y marcas únicos presentes en los resultados para los filtros
    unique_depts = sorted(list(set(row.department_description for row in results if row.department_description)))
    unique_marks = sorted(list(set(row.mark_description for row in results if row.mark_description)))

    return render_template(
        "auto_order_collection.html",
        store_origin=store_origin,
        store_dst=store_dst,
        products=results,
        departments=unique_depts,
        marks=unique_marks
    )
