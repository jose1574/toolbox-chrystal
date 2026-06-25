from flask import render_template, request
from flask_login import login_required
from sqlalchemy import func, select

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsCode,
    ProductsStock,
    ProductsUnit,
    Store,
    Unit,
)
from app.reports import reports_bp


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _resolve_main_code(code: str) -> str:
    normalized = _normalize_code(code)
    mapping = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == normalized
    ).first()
    return _normalize_code(mapping.main_code) if mapping else normalized


def _get_product_info(main_code):
    if not main_code:
        return None

    stmt = (
        select(
            Product.code,
            Product.description,
            Product.referenc,
            Unit.description.label("unit_description"),
            Mark.description.label("mark_description"),
            Department.description.label("department_description"),
        )
        .join(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .join(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .where(func.upper(func.trim(Product.code)) == main_code)
    )
    return db.session.execute(stmt).first()


def _get_stock_by_store(main_code):
    stock_by_store = (
        select(
            ProductsStock.store.label("store_code"),
            func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock"),
        )
        .where(
            func.upper(func.trim(ProductsStock.product_code)) == main_code,
        )
        .group_by(ProductsStock.store)
        .subquery()
    )

    stmt = (
        select(
            Store.code.label("store_code"),
            Store.description.label("store_description"),
            func.coalesce(stock_by_store.c.stock, 0).label("stock"),
        )
        .outerjoin(stock_by_store, stock_by_store.c.store_code == Store.code)
        .order_by(Store.description.asc())
    )
    return db.session.execute(stmt).all()


def _search_products_for_stock_report(query, page=1, per_page=10):
    query = (query or "").strip()
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    stock_totals = (
        select(
            ProductsStock.product_code.label("product_code"),
            func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
        )
        .group_by(ProductsStock.product_code)
        .subquery()
    )

    filters = []
    if query:
        # 1. Reemplazamos los asteriscos por espacios para normalizar la búsqueda
        # Ejemplo: "*busing*1/4" -> " busing 1/4" -> ["busing", "1/4"]
        clean_query = query.replace('*', ' ')
        tokens = [token for token in clean_query.split() if token]

        # 2. Por cada palabra clave, exigimos que coincida con ALGUNO de los campos (OR)
        for token in tokens:
            search_value = f"%{token}%"
            # Este bloque evalúa una sola palabra contra todas las columnas
            token_filter = (
                (Product.code.ilike(search_value))
                | (Product.description.ilike(search_value))
                | (Product.referenc.ilike(search_value))
                | (ProductsCode.other_code.ilike(search_value))
            )
            # Al hacer append, SQLAlchemy las unirá con AND en el .where()
            filters.append(token_filter)

    base_stmt = (
        select(
            Product.code,
            Product.description,
            Product.referenc,
            Unit.description.label("unit_description"),
            Mark.description.label("mark_description"),
            Department.description.label("department_description"),
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
        )
        .join(
            ProductsUnit,
            (ProductsUnit.product_code == Product.code)
            & (ProductsUnit.main_unit.is_(True)),
        )
        .join(Unit, Unit.code == ProductsUnit.unit)
        .outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    )
    
    if filters:
        # *filters aplicará (FiltroToken1 AND FiltroToken2 AND FiltroToken3...)
        base_stmt = base_stmt.outerjoin(
            ProductsCode, ProductsCode.main_code == Product.code
        ).where(*filters)
        
    base_stmt = base_stmt.distinct(Product.code).order_by(Product.code.asc())

    if filters:
        count_stmt = (
            select(func.count(func.distinct(Product.code)))
            .select_from(Product)
            .join(
                ProductsUnit,
                (ProductsUnit.product_code == Product.code)
                & (ProductsUnit.main_unit.is_(True)),
            )
            .outerjoin(ProductsCode, ProductsCode.main_code == Product.code)
            .where(*filters)
        )
        total = db.session.execute(count_stmt).scalar() or 0
    else:
        total = db.session.execute(select(func.count()).select_from(Product)).scalar() or 0

    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    products = db.session.execute(
        base_stmt.limit(per_page).offset((page - 1) * per_page)
    ).all()
    
    return products, total, total_pages, page


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

    main_code = _resolve_main_code(product_code)
    product = _get_product_info(main_code)
    if not product:
        return render_template(
            "inventory/partials/product_stock_details.html",
            product=None,
            product_stocks=[],
            stock_total=0,
            error="No se encontro el producto indicado.",
        )

    product_stocks = _get_stock_by_store(main_code)
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
        _search_products_for_stock_report(query, page=page, per_page=10)
    )
    return render_template(
        "inventory/partials/modal_producs_stock.html",
        products=products,
        query=query,
        page=current_page,
        total_pages=total_pages,
        total_products=total_products,
    )
