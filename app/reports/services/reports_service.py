from sqlalchemy import func, select, true

from app import db
from app.models import (
    Department,
    Mark,
    Product,
    ProductsCode,
    ProductsFailure,
    ProductsStock,
    ProductsUnit,
    Store,
    Unit,
)

PRODUCT_LOCATIONS_PER_PAGE = 50
PRODUCT_LOCATIONS_PDF_LIMIT = 5000
PRODUCT_LOCATIONS_EXCEL_LIMIT = 65000
PRODUCT_LOCATIONS_ACTIVE_STATUS = "01"


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def resolve_main_code(code: str) -> str:
    normalized = normalize_code(code)
    mapping = ProductsCode.query.filter(
        func.upper(func.trim(ProductsCode.other_code)) == normalized
    ).first()
    return normalize_code(mapping.main_code) if mapping else normalized


def get_product_info(main_code):
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


def get_stock_by_store(main_code):
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


def search_products_for_stock_report(query, page=1, per_page=10):
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
        clean_query = query.replace('*', ' ')
        tokens = [token for token in clean_query.split() if token]

        for token in tokens:
            search_value = f"%{token}%"
            token_filter = (
                (Product.code.ilike(search_value))
                | (Product.description.ilike(search_value))
                | (Product.referenc.ilike(search_value))
                | (ProductsCode.other_code.ilike(search_value))
            )
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


def build_product_location_query_filters(filters, stock_by_store):
    filters_sql = []
    query = filters["q"]
    if query:
        clean_query = query.replace("*", " ")
        for token in [token for token in clean_query.split() if token]:
            search_value = f"%{token}%"
            filters_sql.append(
                (Product.code.ilike(search_value))
                | (Product.description.ilike(search_value))
                | (Product.referenc.ilike(search_value))
                | select(ProductsCode.other_code)
                .where(
                    ProductsCode.main_code == Product.code,
                    ProductsCode.other_code.ilike(search_value),
                )
                .exists()
            )

    if filters["mark_codes"]:
        filters_sql.append(
            func.upper(func.trim(Product.mark)).in_(filters["mark_codes"])
        )

    if filters["department_codes"]:
        filters_sql.append(
            func.upper(func.trim(Product.department)).in_(
                filters["department_codes"]
            )
        )

    if filters["product_status"] == "active":
        filters_sql.append(Product.status == PRODUCT_LOCATIONS_ACTIVE_STATUS)

    if filters["store_codes"]:
        filters_sql.append(
            func.upper(func.trim(Store.code)).in_(filters["store_codes"])
        )

    if filters["location_state"] == "with":
        filters_sql.append(func.coalesce(func.trim(ProductsFailure.location), "") != "")
    elif filters["location_state"] == "without":
        filters_sql.append(func.coalesce(func.trim(ProductsFailure.location), "") == "")

    if filters["stock_state"] == "with":
        filters_sql.append(func.coalesce(stock_by_store.c.stock, 0) > 0)
    elif filters["stock_state"] == "without":
        filters_sql.append(func.coalesce(stock_by_store.c.stock, 0) <= 0)

    return filters_sql


def get_product_location_stock_subquery():
    return (
        select(
            ProductsStock.product_code.label("product_code"),
            ProductsStock.store.label("store_code"),
            func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock"),
        )
        .group_by(ProductsStock.product_code, ProductsStock.store)
        .subquery()
    )


def _apply_product_location_joins(stmt, stock_by_store):
    return (
        stmt.select_from(Product)
        .join(Store, true())
        .outerjoin(
            stock_by_store,
            (stock_by_store.c.product_code == Product.code)
            & (stock_by_store.c.store_code == Store.code),
        )
        .outerjoin(
            ProductsFailure,
            (ProductsFailure.product_code == Product.code)
            & (ProductsFailure.store_code == Store.code),
        )
    )


def get_product_location_rows_query(filters):
    stock_by_store = get_product_location_stock_subquery()
    filters_sql = build_product_location_query_filters(filters, stock_by_store)

    stmt = select(
        Product.code,
        Product.description,
        Mark.description.label("mark_description"),
        Department.description.label("department_description"),
        Store.code.label("store_code"),
        Store.description.label("store_description"),
        func.coalesce(stock_by_store.c.stock, 0).label("stock"),
        ProductsFailure.location.label("location"),
    )
    stmt = _apply_product_location_joins(stmt, stock_by_store)

    return (
        stmt.outerjoin(Mark, Mark.code == Product.mark)
        .outerjoin(Department, Department.code == Product.department)
        .where(*filters_sql)
        .order_by(Product.code.asc(), Store.code.asc())
    )


def get_product_location_totals(filters):
    stock_by_store = get_product_location_stock_subquery()
    filters_sql = build_product_location_query_filters(filters, stock_by_store)

    stmt = select(
        func.count().label("total_rows"),
        func.count(func.distinct(Product.code)).label("total_products"),
    )
    stmt = _apply_product_location_joins(stmt, stock_by_store)
    totals = db.session.execute(stmt.where(*filters_sql)).first()

    if not totals:
        return 0, 0
    return totals.total_products or 0, totals.total_rows or 0
