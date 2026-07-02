from datetime import datetime
from uuid import uuid4
import pandas as pd
from sqlalchemy import select, func, text
from sqlalchemy.orm import joinedload
from app import db
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
  InventoryOperationDetail,
  InventoryOperationReceptionDifference,
  ProductsCode,
  User,
)
from sqlalchemy import select, func, text
from sqlalchemy.orm import aliased, joinedload
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
  InventoryOperationCheckingProgress,
  InventoryOperationFlow,
  InventoryOperationReceptionProgress,
  InventoryOperationPackage,
  InventoryOperationPackageDetail,
  InventoryOperationReceptionDifference,
  ProductsCode,
  ProductsCounterHistory,
  User,
)


def register_flow_step1(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      INSERT INTO toolbox.inventory_operation_flow (
        operation_correlative,
        current_status,
        recollection_issued_user
      ) VALUES (%s, %s, %s)
    """
    data = (operation_correlative, FLOW_RECOLLECTION_ISSUED, user_code)
    cursor.execute(sql, data)
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step2(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           checking_user = %s,
           checked_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (
      FLOW_RECOLLECTION_CHECKED,
      user_code,
      operation_correlative,
      FLOW_RECOLLECTION_ISSUED,
    )
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("Order is not in recollection issued state.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step3(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           in_transit_user = %s,
           in_transit_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (
      FLOW_IN_TRANSIT,
      user_code,
      operation_correlative,
      FLOW_RECOLLECTION_CHECKED,
    )
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("Order is not checked to start transfer.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step4(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           receiving_user = %s,
           received_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (FLOW_RECEIVED, user_code, operation_correlative, FLOW_IN_TRANSIT)
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("Order is not in transit to receive.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def get_inventory_operation_flow(operation_correlative):
  sql = text(
    """
    SELECT current_status,
         recollection_issued_user,
         recollection_issued_at,
         checking_user,
         checked_at,
         in_transit_user,
         in_transit_at,
         receiving_user,
         received_at
      FROM toolbox.inventory_operation_flow
     WHERE operation_correlative = :operation_correlative
    """
  )
  return db.session.execute(sql, {"operation_correlative": operation_correlative}).mappings().first()


def get_reception_difference_map(operation_correlative):
  differences = InventoryOperationReceptionDifference.query.filter_by(
    operation_correlative=operation_correlative
  ).all()
  return {difference.detail_line: difference for difference in differences}


def get_reception_difference(operation_correlative, detail_line):
  return InventoryOperationReceptionDifference.query.filter_by(
    operation_correlative=operation_correlative, detail_line=detail_line
  ).first()


def normalize_code(code: str) -> str:
  return (code or "").strip().upper()


def _resolver_main_code(code: str) -> str:
  normalized = normalize_code(code)
  mapping = ProductsCode.query.filter(
    func.upper(func.trim(ProductsCode.other_code)) == normalized
  ).first()
  return normalize_code(mapping.main_code) if mapping else normalized


def resolve_main_code(code: str) -> str:
  return _resolver_main_code(code)


def find_detail_by_codes(order_id, codes):
  normalized_codes = {normalize_code(code) for code in codes if code}
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


def sort_details_by_location(details):
  def sort_key(detail):
    location = ""
    if detail.failure_info and detail.failure_info.location:
      location = detail.failure_info.location.strip().upper()

    code_product = normalize_code(detail.code_product)
    return (location == "", location, code_product)

  return sorted(details, key=sort_key)


def build_products_list_df():
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


def get_product_for_manual_order(product_code, store_origin):
  main_code = _resolver_main_code(product_code)
  if not main_code or not store_origin:
    return None

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  stmt = (
    select(
      Product.code,
      Product.description,
      Product.referenc,
      Unit.description.label("unit_description"),
      Mark.description.label("mark_description"),
      Department.description.label("department_description"),
      func.coalesce(stock_totals.c.stock_total, 0).label("stock_origin"),
    )
    .join(ProductsUnit, (ProductsUnit.product_code == Product.code) & (ProductsUnit.main_unit == True))
    .join(Unit, Unit.code == ProductsUnit.unit)
    .outerjoin(Mark, Mark.code == Product.mark)
    .outerjoin(Department, Department.code == Product.department)
    .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    .where(func.upper(func.trim(Product.code)) == main_code)
  )
  return db.session.execute(stmt).first()


def get_manual_order_product_detail_data(product_code, store_origin, store_dst):
  main_code = _resolver_main_code(product_code)
  if not main_code or not store_origin or not store_dst:
    return None

  product = Product.query.filter_by(code=main_code).first()
  if not product:
    return None

  unit_row = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()
  mark_row = Mark.query.filter_by(code=product.mark).first() if product.mark else None
  department_row = Department.query.filter_by(code=product.department).first() if product.department else None
  product_params = ProductsFailure.query.filter_by(
    product_code=main_code,
    store_code=store_dst,
  ).first()

  stock_rows = (
    db.session.query(
      ProductsStock.store.label("store_code"),
      Store.description.label("store_description"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .outerjoin(Store, Store.code == ProductsStock.store)
    .filter(ProductsStock.product_code == main_code)
    .group_by(ProductsStock.store, Store.description)
    .order_by(Store.description.asc())
    .all()
  )

  stock_by_store = [
    {
      "store_code": row.store_code,
      "store_description": row.store_description or row.store_code,
      "stock": float(row.stock_total or 0),
    }
    for row in stock_rows
  ]

  stock_global = sum(row["stock"] for row in stock_by_store)
  stock_origin = next(
    (row["stock"] for row in stock_by_store if normalize_code(row["store_code"]) == normalize_code(store_origin)),
    0,
  )
  stock_destination = next(
    (row["stock"] for row in stock_by_store if normalize_code(row["store_code"]) == normalize_code(store_dst)),
    0,
  )

  return {
    "main_code": main_code,
    "product": product,
    "unit": unit_row.unit1 if unit_row else None,
    "mark_description": mark_row.description if mark_row else "",
    "department_description": department_row.description if department_row else "",
    "stock_global": float(stock_global or 0),
    "stock_origin": float(stock_origin or 0),
    "stock_destination": float(stock_destination or 0),
    "stock_by_store": stock_by_store,
    "minimum_stock": float(product_params.minimal_stock or 0) if product_params else 0,
    "maximum_stock": float(product_params.maximum_stock or 0) if product_params else 0,
    "location": product_params.location if product_params and product_params.location else "",
    "resolved_from_alternate": normalize_code(product_code) != main_code,
  }


def get_manual_order_cart_context(store_origin, store_dst, cart_map):
  if not store_origin or not store_dst:
    return {
      "items": [],
      "total_lines": 0,
      "total_quantity": 0.0,
      "total_units": "",
      "has_items": False,
    }

  normalized_items = {}
  for code, quantity in (cart_map or {}).items():
    main_code = resolve_main_code(code)
    try:
      qty_value = float(quantity)
    except (TypeError, ValueError):
      qty_value = 0

    if main_code and qty_value > 0:
      normalized_items[main_code] = normalized_items.get(main_code, 0) + qty_value

  if not normalized_items:
    return {
      "items": [],
      "total_lines": 0,
      "total_quantity": 0.0,
      "total_units": "",
      "has_items": False,
    }

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  rows = db.session.execute(
    select(
      Product.code,
      Product.description,
      Unit.description.label("unit_description"),
      func.coalesce(stock_totals.c.stock_total, 0).label("stock_origin"),
    )
    .join(ProductsUnit, (ProductsUnit.product_code == Product.code) & (ProductsUnit.main_unit == True))
    .join(Unit, Unit.code == ProductsUnit.unit)
    .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    .where(Product.code.in_(list(normalized_items.keys())))
  ).all()

  row_by_code = {normalize_code(row.code): row for row in rows}
  items = []
  for code in sorted(normalized_items.keys()):
    row = row_by_code.get(code)
    quantity = float(normalized_items[code])
    unit_description = row.unit_description if row else "UND"
    stock_origin = float(row.stock_origin or 0) if row else 0.0
    items.append(
      {
        "code": code,
        "description": row.description if row else "Producto no encontrado",
        "quantity": quantity,
        "unit_description": unit_description,
        "stock_origin": stock_origin,
        "is_over_stock": quantity > stock_origin,
      }
    )

  return {
    "items": items,
    "total_lines": len(items),
    "total_quantity": sum(item["quantity"] for item in items),
    "total_units": items[0]["unit_description"] if items else "",
    "has_items": bool(items),
  }


def get_manual_order_filter_options(store_origin):
  if not store_origin:
    return [], []

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  marks = db.session.execute(
    select(Mark.code, Mark.description)
    .join(Product, Product.mark == Mark.code)
    .join(stock_totals, stock_totals.c.product_code == Product.code)
    .where(func.coalesce(stock_totals.c.stock_total, 0) > 0)
    .group_by(Mark.code, Mark.description)
    .order_by(Mark.description.asc())
  ).all()

  departments = db.session.execute(
    select(Department.code, Department.description)
    .join(Product, Product.department == Department.code)
    .join(stock_totals, stock_totals.c.product_code == Product.code)
    .where(func.coalesce(stock_totals.c.stock_total, 0) > 0)
    .group_by(Department.code, Department.description)
    .order_by(Department.description.asc())
  ).all()

  return marks, departments


def search_products_for_manual_order(
  store_origin,
  query,
  page=1,
  per_page=10,
  mark_code="",
  department_code="",
  stock_filter="with_stock",
  store_dst="",
):
  query = (query or "").strip()
  mark_code = normalize_code(mark_code)
  department_code = normalize_code(department_code)
  stock_filter = (stock_filter or "with_stock").strip().lower()
  store_dst = normalize_code(store_dst)

  if not store_origin:
    return [], 0, 1, 1

  page = max(page or 1, 1)
  per_page = max(min(per_page or 10, 50), 1)

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  destination_params = aliased(ProductsFailure)

  filters = []
  stock_total_expr = func.coalesce(stock_totals.c.stock_total, 0)

  if stock_filter == "all":
    pass
  elif stock_filter == "out_stock":
    filters.append(stock_total_expr <= 0)
  elif stock_filter == "low_stock":
    filters.append(stock_total_expr > 0)
    if store_dst:
      filters.append(stock_total_expr <= func.coalesce(destination_params.minimal_stock, 0))
      filters.append(func.coalesce(destination_params.minimal_stock, 0) > 0)
  else:
    filters.append(stock_total_expr > 0)

  if mark_code:
    filters.append(func.upper(func.trim(Product.mark)) == mark_code)

  if department_code:
    filters.append(func.upper(func.trim(Product.department)) == department_code)

  if query:
    if "*" in query:
      wildcard_pattern = query.replace("\\", "\\\\")
      wildcard_pattern = wildcard_pattern.replace("%", "\\%")
      wildcard_pattern = wildcard_pattern.replace("_", "\\_")
      wildcard_pattern = f"%{wildcard_pattern.replace('*', '%')}%"
      while "%%" in wildcard_pattern:
        wildcard_pattern = wildcard_pattern.replace("%%", "%")
      filters.append(Product.description.ilike(wildcard_pattern, escape="\\"))
    else:
      search_value = f"%{query}%"
      filters.append(
        (Product.code.ilike(search_value))
        | (Product.description.ilike(search_value))
        | (Product.referenc.ilike(search_value))
      )

  base_stmt = (
    select(
      Product.code,
      Product.description,
      Product.referenc,
      Product.mark.label("mark_code"),
      Product.department.label("department_code"),
      Unit.description.label("unit_description"),
      Mark.description.label("mark_description"),
      Department.description.label("department_description"),
      stock_total_expr.label("stock_origin"),
    )
    .join(ProductsUnit, (ProductsUnit.product_code == Product.code) & (ProductsUnit.main_unit == True))
    .join(Unit, Unit.code == ProductsUnit.unit)
    .outerjoin(Mark, Mark.code == Product.mark)
    .outerjoin(Department, Department.code == Product.department)
    .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    .outerjoin(
      destination_params,
      (destination_params.product_code == Product.code)
      & (destination_params.store_code == store_dst),
    )
    .where(*filters)
    .order_by(Product.code.asc())
  )

  count_stmt = select(func.count()).select_from(base_stmt.alias("manual_products"))
  total = db.session.execute(count_stmt).scalar() or 0
  total_pages = max((total + per_page - 1) // per_page, 1)
  page = min(page, total_pages)
  products = db.session.execute(
    base_stmt.limit(per_page).offset((page - 1) * per_page)
  ).all()
  return products, total, total_pages, page


def create_order_collection_operation(store_origin, store_dst, selected_items, source_label):
  if not store_origin or not store_dst:
    raise ValueError("You must select origin and destination stores.")

  if store_origin == store_dst:
    raise ValueError("Origin and destination stores cannot be the same.")

  store_origen_obj = Store.query.filter_by(code=store_origin).first()
  store_dst_obj = Store.query.filter_by(code=store_dst).first()

  if not store_origen_obj or not store_dst_obj:
    raise ValueError("Invalid stores.")

  normalized_items = {}
  for item in selected_items:
    main_code = resolve_main_code(item.get("code"))
    try:
      quantity = float(item.get("quantity", 0))
    except (TypeError, ValueError):
      quantity = 0

    if main_code and quantity > 0:
      normalized_items[main_code] = normalized_items.get(main_code, 0) + quantity

  if not normalized_items:
    raise ValueError("No products selected.")

  header_params = {
    "p_correlative": None,
    "p_operation_type": "TRANSFER",
    "p_document_no": None,
    "p_emission_date": datetime.now().date(),
    "p_wait": True,
    "p_description": f"Transfer {source_label} {store_origen_obj.description} -> {store_dst_obj.description}",
    "p_user_code": "system",
    "p_station": "00",
    "p_store": store_origin,
    "p_locations": "00",
    "p_destination_store": store_dst,
    "p_destination_location": "00",
    "p_operation_comments": f"Generated from Toolbox {source_label}",
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
    raise RuntimeError("DB did not return operation ID.")

  sql_detail = text(
    """
    SELECT set_inventory_operation_details(:p_main_correlative, :p_line, :p_code_product,
    :p_description_product, :p_referenc, :p_mark, :p_model, :p_amount, :p_store, :p_locations,
    :p_destination_store, :p_destination_location, :p_unit, :p_conversion_factor, :p_unit_type,
    :p_unitary_cost, :p_buy_tax, :p_aliquot, :p_total_cost, :p_total_tax, :p_total, :p_coin_code,
    :p_change_price)
  """
  )

  for code, quantity in normalized_items.items():
    data_row = (
      db.session.query(ProductsUnit, Product, Tax)
      .join(Product, ProductsUnit.product_code == Product.code)
      .outerjoin(Tax, Product.buy_tax == Tax.code)
      .filter(ProductsUnit.product_code == code, ProductsUnit.main_unit == True)
      .first()
    )

    if not data_row:
      raise ValueError(f"Product {code} has no main unit configured.")

    product_stock = (
      db.session.query(func.sum(func.coalesce(ProductsStock.stock, 0)))
      .filter(ProductsStock.product_code == code, ProductsStock.store == store_origin)
      .scalar()
      or 0
    )
    if float(quantity) > float(product_stock):
      raise ValueError(f"Product {code} exceeds available stock in origin ({product_stock}).")

    pu, prod, tax = data_row
    detail_params = {
      "p_main_correlative": document_no,
      "p_line": 0,
      "p_code_product": code,
      "p_description_product": prod.description or "Product added from Toolbox",
      "p_referenc": prod.referenc,
      "p_mark": prod.mark,
      "p_model": prod.model,
      "p_amount": float(quantity),
      "p_store": store_origin,
      "p_locations": "00",
      "p_destination_store": store_dst,
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

  return document_no


def process_inventory_operation(operation_correlative):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = "SELECT save_inventory_operation(%s)"
    data = (operation_correlative,)
    cursor.execute(sql, data)
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()

FLOW_RECOLLECTION_ISSUED = "RECOLLECTION_ISSUED"
FLOW_RECOLLECTION_CHECKED = "RECOLLECTION_CHECKED"
FLOW_IN_TRANSIT = "IN_TRANSIT"
FLOW_RECEIVED = "RECEIVED"

TRANSFER_STATUS_LABELS = {
    FLOW_RECOLLECTION_ISSUED: "Orden emitida",
    FLOW_RECOLLECTION_CHECKED: "Orden chequeada",
    FLOW_IN_TRANSIT: "En tránsito",
    FLOW_RECEIVED: "Recepcionado y procesado",
}


def parse_date_filter(value: str):
    """Parse a date string (YYYY-MM-DD) into a datetime.date or return None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_transfer_traceability_rows(filters: dict):
    """Return transfer traceability rows using raw SQL. Expects a dict with keys:
    status, date_from_value, date_to_value, q
    """
    sql = text(
        """
        SELECT f.operation_correlative,
               f.current_status,
               f.recollection_issued_user,
               issued_user.description AS recollection_issued_user_name,
               f.recollection_issued_at,
               f.checking_user,
               checking_user.description AS checking_user_name,
               f.checked_at,
               f.in_transit_user,
               transit_user.description AS in_transit_user_name,
               f.in_transit_at,
               f.receiving_user,
               receiving_user.description AS receiving_user_name,
               f.received_at,
               io.document_no,
               io.emission_date,
               io.description,
               io.store,
               origin_store.description AS store_description,
               io.destination_store,
               destination_store.description AS destination_store_description,
               io.wait
          FROM toolbox.inventory_operation_flow f
          JOIN public.inventory_operation io
            ON io.correlative = f.operation_correlative
          LEFT JOIN public.store origin_store
            ON origin_store.code = io.store
          LEFT JOIN public.store destination_store
            ON destination_store.code = io.destination_store
          LEFT JOIN public.users issued_user
            ON issued_user.code = f.recollection_issued_user
          LEFT JOIN public.users checking_user
            ON checking_user.code = f.checking_user
          LEFT JOIN public.users transit_user
            ON transit_user.code = f.in_transit_user
          LEFT JOIN public.users receiving_user
            ON receiving_user.code = f.receiving_user
         WHERE io.operation_type = 'TRANSFER'
           AND (:status = '' OR f.current_status = :status)
           AND (:date_from IS NULL OR io.emission_date >= :date_from)
           AND (:date_to IS NULL OR io.emission_date <= :date_to)
           AND (
                :q = ''
                OR CAST(f.operation_correlative AS VARCHAR) ILIKE :q_like
                OR COALESCE(io.document_no, '') ILIKE :q_like
                OR COALESCE(io.description, '') ILIKE :q_like
                OR COALESCE(origin_store.description, '') ILIKE :q_like
                OR COALESCE(destination_store.description, '') ILIKE :q_like
           )
         ORDER BY io.emission_date DESC NULLS LAST,
                  f.operation_correlative DESC
        """
    )
    params = {
        "status": filters.get("status", ""),
        "date_from": filters.get("date_from_value"),
        "date_to": filters.get("date_to_value"),
        "q": filters.get("q", ""),
        "q_like": f"%{filters.get('q','')}%",
    }
    return db.session.execute(sql, params).mappings().all()


def build_transfer_traceability_filters(status: str = "", date_from: str = "", date_to: str = "", q: str = ""):
    """Build a filters dict suitable for get_transfer_traceability_rows."""
    status_val = (status or "").strip().upper()
    if status_val not in TRANSFER_STATUS_LABELS:
        status_val = ""
    date_from_value = parse_date_filter((date_from or "").strip())
    date_to_value = parse_date_filter((date_to or "").strip())
    q_val = (q or "").strip()
    return {
        "status": status_val,
        "date_from": (date_from or "").strip(),
        "date_to": (date_to or "").strip(),
        "q": q_val,
        "date_from_value": date_from_value,
        "date_to_value": date_to_value,
    }


def build_transfer_differences_filters(date_from: str = "", date_to: str = "", q: str = ""):
    date_from_value = parse_date_filter((date_from or "").strip())
    date_to_value = parse_date_filter((date_to or "").strip())
    q_val = (q or "").strip()
    return {
        "date_from": (date_from or "").strip(),
        "date_to": (date_to or "").strip(),
        "q": q_val,
        "date_from_value": date_from_value,
        "date_to_value": date_to_value,
    }


def get_transfer_differences_rows(filters: dict):
  sql = text(
    """
    SELECT io.correlative AS operation_correlative,
         io.document_no,
         io.emission_date,
         io.description,
         io.store,
         origin_store.description AS store_description,
         io.destination_store,
         destination_store.description AS destination_store_description,
         COALESCE(f.current_status, 'SIN_FLUJO') AS current_status,
         COUNT(d.correlative) AS difference_lines,
         SUM(d.original_amount) AS expected_total,
         SUM(d.counted_amount) AS counted_total,
         SUM(d.difference) AS difference_total,
         MAX(COALESCE(d.updated_at, d.detected_at)) AS last_difference_at
      FROM toolbox.inventory_operation_reception_differences d
      JOIN public.inventory_operation io
      ON io.correlative = d.operation_correlative
      LEFT JOIN toolbox.inventory_operation_flow f
      ON f.operation_correlative = io.correlative
      LEFT JOIN public.store origin_store
      ON origin_store.code = io.store
      LEFT JOIN public.store destination_store
      ON destination_store.code = io.destination_store
     WHERE io.operation_type = 'TRANSFER'
       AND (:date_from IS NULL OR io.emission_date >= :date_from)
       AND (:date_to IS NULL OR io.emission_date <= :date_to)
       AND (
        :q = ''
        OR CAST(io.correlative AS VARCHAR) ILIKE :q_like
        OR COALESCE(io.document_no, '') ILIKE :q_like
        OR COALESCE(io.description, '') ILIKE :q_like
        OR COALESCE(origin_store.description, '') ILIKE :q_like
        OR COALESCE(destination_store.description, '') ILIKE :q_like
       )
     GROUP BY io.correlative,
          io.document_no,
          io.emission_date,
          io.description,
          io.store,
          origin_store.description,
          io.destination_store,
          destination_store.description,
          f.current_status
     ORDER BY last_difference_at DESC NULLS LAST,
          io.correlative DESC
    """
  )
  params = {
    "date_from": filters.get("date_from_value"),
    "date_to": filters.get("date_to_value"),
    "q": filters.get("q", ""),
    "q_like": f"%{filters.get('q', '')}%",
  }
  return db.session.execute(sql, params).mappings().all()


def register_flow_step1(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      INSERT INTO toolbox.inventory_operation_flow (
        operation_correlative,
        current_status,
        recollection_issued_user
      ) VALUES (%s, %s, %s)
    """
    data = (operation_correlative, FLOW_RECOLLECTION_ISSUED, user_code)
    cursor.execute(sql, data)
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step2(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           checking_user = %s,
           checked_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (
      FLOW_RECOLLECTION_CHECKED,
      user_code,
      operation_correlative,
      FLOW_RECOLLECTION_ISSUED,
    )
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("La orden no esta en estado de recoleccion emitida.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step3(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           in_transit_user = %s,
           in_transit_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (
      FLOW_IN_TRANSIT,
      user_code,
      operation_correlative,
      FLOW_RECOLLECTION_CHECKED,
    )
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("La orden no esta chequeada para iniciar traslado.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def register_flow_step4(operation_correlative, user_code):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = """
      UPDATE toolbox.inventory_operation_flow
         SET current_status = %s,
           receiving_user = %s,
           received_at = CURRENT_TIMESTAMP
       WHERE operation_correlative = %s
         AND current_status = %s
    """
    data = (FLOW_RECEIVED, user_code, operation_correlative, FLOW_IN_TRANSIT)
    cursor.execute(sql, data)
    if cursor.rowcount != 1:
      raise ValueError("La orden no esta en transito para recepcionar.")
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def get_inventory_operation_flow(operation_correlative):
  sql = text(
    """
    SELECT current_status,
         recollection_issued_user,
         recollection_issued_at,
         checking_user,
         checked_at,
         in_transit_user,
         in_transit_at,
         receiving_user,
         received_at
      FROM toolbox.inventory_operation_flow
     WHERE operation_correlative = :operation_correlative
    """
  )
  return db.session.execute(
    sql, {"operation_correlative": operation_correlative}
  ).mappings().first()


def get_reception_difference_map(operation_correlative):
  differences = InventoryOperationReceptionDifference.query.filter_by(
    operation_correlative=operation_correlative
  ).all()
  return {difference.detail_line: difference for difference in differences}


def get_reception_difference(operation_correlative, detail_line):
  return InventoryOperationReceptionDifference.query.filter_by(
    operation_correlative=operation_correlative,
    detail_line=detail_line,
  ).first()


def validate_transfer_responsible(username, password, fallback_user_code):
  username = normalize_code(username)
  password = password or ""

  if not username and not password:
    return fallback_user_code, None
  if not username or not password:
    return None, "Debe ingresar usuario y clave del responsable, o dejar ambos campos vacíos."

  user = User.query.filter_by(code=username).first()
  if not user or user.user_password != password:
    return None, "Usuario o clave del responsable incorrectos."

  return user.code, None


def process_inventory_operation(operation_correlative):
  conn = None
  cursor = None
  try:
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    sql = "SELECT save_inventory_operation(%s)"
    data = (operation_correlative,)
    cursor.execute(sql, data)
    conn.commit()
    return True
  except Exception:
    if conn:
      conn.rollback()
    raise
  finally:
    if cursor:
      cursor.close()
    if conn:
      conn.close()


def normalize_code(code: str) -> str:
  return (code or "").strip().upper()


def resolve_main_code(code: str) -> str:
  return _resolver_main_code(code)


def find_detail_by_codes(order_id, codes):
  normalized_codes = {normalize_code(code) for code in codes if code}
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


def sort_details_by_location(details):
  def sort_key(detail):
    location = ""
    if detail.failure_info and detail.failure_info.location:
      location = detail.failure_info.location.strip().upper()
    code_product = normalize_code(detail.code_product)
    return (location == "", location, code_product)

  return sorted(details, key=sort_key)


def build_products_list_df():
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


def get_product_for_manual_order(product_code, store_origin):
  main_code = _resolver_main_code(product_code)
  if not main_code or not store_origin:
    return None

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  stmt = (
    select(
      Product.code,
      Product.description,
      Product.referenc,
      Unit.description.label("unit_description"),
      Mark.description.label("mark_description"),
      Department.description.label("department_description"),
      func.coalesce(stock_totals.c.stock_total, 0).label("stock_origin"),
    )
    .join(
      ProductsUnit,
      (ProductsUnit.product_code == Product.code) & (ProductsUnit.main_unit == True),
    )
    .join(Unit, Unit.code == ProductsUnit.unit)
    .outerjoin(Mark, Mark.code == Product.mark)
    .outerjoin(Department, Department.code == Product.department)
    .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    .where(func.upper(func.trim(Product.code)) == main_code)
  )
  return db.session.execute(stmt).first()


def search_products_for_manual_order(
  store_origin,
  query,
  page=1,
  per_page=10,
  mark_code="",
  department_code="",
  stock_filter="with_stock",
  store_dst="",
):
  query = (query or "").strip()
  mark_code = normalize_code(mark_code)
  department_code = normalize_code(department_code)
  stock_filter = (stock_filter or "with_stock").strip().lower()
  store_dst = normalize_code(store_dst)

  if not store_origin:
    return [], 0, 1, 1

  page = max(page or 1, 1)
  per_page = max(min(per_page or 10, 50), 1)

  stock_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  destination_params = aliased(ProductsFailure)

  filters = []
  stock_total_expr = func.coalesce(stock_totals.c.stock_total, 0)

  if stock_filter == "all":
    pass
  elif stock_filter == "out_stock":
    filters.append(stock_total_expr <= 0)
  elif stock_filter == "low_stock":
    filters.append(stock_total_expr > 0)
    if store_dst:
      filters.append(stock_total_expr <= func.coalesce(destination_params.minimal_stock, 0))
      filters.append(func.coalesce(destination_params.minimal_stock, 0) > 0)
  else:
    filters.append(stock_total_expr > 0)

  if mark_code:
    filters.append(func.upper(func.trim(Product.mark)) == mark_code)

  if department_code:
    filters.append(func.upper(func.trim(Product.department)) == department_code)

  if query:
    if "*" in query:
      wildcard_pattern = query.replace("\\", "\\\\")
      wildcard_pattern = wildcard_pattern.replace("%", "\\%")
      wildcard_pattern = wildcard_pattern.replace("_", "\\_")
      wildcard_pattern = f"%{wildcard_pattern.replace('*', '%')}%"
      while "%%" in wildcard_pattern:
        wildcard_pattern = wildcard_pattern.replace("%%", "%")
      filters.append(Product.description.ilike(wildcard_pattern, escape="\\"))
    else:
      search_value = f"%{query}%"
      filters.append(
        (Product.code.ilike(search_value))
        | (Product.description.ilike(search_value))
        | (Product.referenc.ilike(search_value))
      )

  base_stmt = (
    select(
      Product.code,
      Product.description,
      Product.referenc,
      Product.mark.label("mark_code"),
      Product.department.label("department_code"),
      Unit.description.label("unit_description"),
      Mark.description.label("mark_description"),
      Department.description.label("department_description"),
      stock_total_expr.label("stock_origin"),
    )
    .join(
      ProductsUnit,
      (ProductsUnit.product_code == Product.code) & (ProductsUnit.main_unit == True),
    )
    .join(Unit, Unit.code == ProductsUnit.unit)
    .outerjoin(Mark, Mark.code == Product.mark)
    .outerjoin(Department, Department.code == Product.department)
    .outerjoin(stock_totals, stock_totals.c.product_code == Product.code)
    .outerjoin(
      destination_params,
      (destination_params.product_code == Product.code)
      & (destination_params.store_code == store_dst),
    )
    .where(*filters)
    .order_by(Product.code.asc())
  )

  count_stmt = select(func.count()).select_from(base_stmt.alias("manual_products"))
  total = db.session.execute(count_stmt).scalar() or 0
  total_pages = max((total + per_page - 1) // per_page, 1)
  page = min(page, total_pages)
  products = db.session.execute(
    base_stmt.limit(per_page).offset((page - 1) * per_page)
  ).all()
  return products, total, total_pages, page


def create_order_collection_operation(
  store_origin, store_dst, selected_items, source_label, user_code
):
  if not store_origin or not store_dst:
    raise ValueError("Debes seleccionar depósito origen y destino.")
  if store_origin == store_dst:
    raise ValueError("El depósito origen y destino no pueden ser el mismo.")

  store_origin_obj = Store.query.filter_by(code=store_origin).first()
  store_dst_obj = Store.query.filter_by(code=store_dst).first()
  if not store_origin_obj or not store_dst_obj:
    raise ValueError("Depósitos inválidos.")

  normalized_items = {}
  for item in selected_items:
    main_code = resolve_main_code(item.get("code"))
    try:
      quantity = float(item.get("quantity", 0))
    except (TypeError, ValueError):
      quantity = 0

    if main_code and quantity > 0:
      normalized_items[main_code] = normalized_items.get(main_code, 0) + quantity

  if not normalized_items:
    raise ValueError("No se han seleccionado productos.")

  operation_description = (
    f"Orden de recoleccion emitida del deposito de origen {store_origin_obj.description} "
    f"a destino {store_dst_obj.description}"
  )

  header_params = {
    "p_correlative": None,
    "p_operation_type": "TRANSFER",
    "p_document_no": None,
    "p_emission_date": datetime.now().date(),
    "p_wait": True,
    "p_description": operation_description,
    "p_user_code": user_code,
    "p_station": "00",
    "p_store": store_origin,
    "p_locations": "00",
    "p_destination_store": store_dst,
    "p_destination_location": "00",
    "p_operation_comments": f"Generado desde Toolbox {source_label}",
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
    raise RuntimeError("La DB no devolvió ID de operación.")

  sql_detail = text(
    """
    SELECT set_inventory_operation_details(:p_main_correlative, :p_line, :p_code_product,
    :p_description_product, :p_referenc, :p_mark, :p_model, :p_amount, :p_store, :p_locations,
    :p_destination_store, :p_destination_location, :p_unit, :p_conversion_factor, :p_unit_type,
    :p_unitary_cost, :p_buy_tax, :p_aliquot, :p_total_cost, :p_total_tax, :p_total, :p_coin_code,
    :p_change_price)
    """
  )

  for code, quantity in normalized_items.items():
    data_row = (
      db.session.query(ProductsUnit, Product, Tax)
      .join(Product, ProductsUnit.product_code == Product.code)
      .outerjoin(Tax, Product.buy_tax == Tax.code)
      .filter(ProductsUnit.product_code == code, ProductsUnit.main_unit == True)
      .first()
    )

    if not data_row:
      raise ValueError(f"El producto {code} no tiene unidad principal configurada.")

    product_stock = (
      db.session.query(func.sum(func.coalesce(ProductsStock.stock, 0)))
      .filter(ProductsStock.product_code == code, ProductsStock.store == store_origin)
      .scalar()
      or 0
    )
    if float(quantity) > float(product_stock):
      raise ValueError(
        f"El producto {code} supera el stock disponible en origen ({product_stock})."
      )

    pu, prod, tax = data_row
    detail_params = {
      "p_main_correlative": document_no,
      "p_line": 0,
      "p_code_product": code,
      "p_description_product": prod.description or "Producto agregado desde Toolbox",
      "p_referenc": prod.referenc,
      "p_mark": prod.mark,
      "p_model": prod.model,
      "p_amount": float(quantity),
      "p_store": store_origin,
      "p_locations": "00",
      "p_destination_store": store_dst,
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

  return document_no


def get_store_by_code(store_code):
  return Store.query.filter_by(code=store_code).first()


def get_all_stores():
  return Store.query.all()


def get_stores_ordered_by_description():
  return Store.query.order_by(Store.description.asc()).all()


def get_auto_order_collection_data(store_origin, store_dst):
  stores = get_all_stores()
  store_origin_obj = get_store_by_code(store_origin) if store_origin else None
  store_dst_obj = get_store_by_code(store_dst) if store_dst else None

  if not store_origin or not store_dst:
    return {
      "stores": stores,
      "store_origin_obj": store_origin_obj,
      "store_dst_obj": store_dst_obj,
      "products": [],
      "departments": [],
      "marks": [],
    }

  stock_orig_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_origin)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  stock_dst_totals = (
    select(
      ProductsStock.product_code.label("product_code"),
      func.sum(func.coalesce(ProductsStock.stock, 0)).label("stock_total"),
    )
    .where(ProductsStock.store == store_dst)
    .group_by(ProductsStock.product_code)
    .subquery()
  )

  checked_embarked_products = (
    select(InventoryOperationPackageDetail.product_code)
    .distinct()
    .join(
      InventoryOperationPackage,
      InventoryOperationPackage.correlative == InventoryOperationPackageDetail.package_correlative,
    )
    .join(
      InventoryOperation,
      InventoryOperation.correlative == InventoryOperationPackage.operation_correlative,
    )
    .join(
      InventoryOperationFlow,
      InventoryOperationFlow.operation_correlative == InventoryOperation.correlative,
    )
    .where(
      InventoryOperation.store == store_origin,
      InventoryOperation.destination_store == store_dst,
      InventoryOperationFlow.current_status == FLOW_RECOLLECTION_CHECKED,
    )
    .subquery()
  )

  pf = aliased(ProductsFailure)
  m = aliased(Mark)
  d = aliased(Department)
  u = aliased(Unit)
  pu = aliased(ProductsUnit)

  needed = pf.maximum_stock - func.coalesce(stock_dst_totals.c.stock_total, 0)
  to_transfer = func.least(
    func.coalesce(stock_orig_totals.c.stock_total, 0), func.greatest(needed, 0)
  ).label("to_transfer")

  stmt = (
    select(
      Product.code,
      Product.description,
      Product.mark.label("mark_code"),
      Product.department.label("department_code"),
      m.description.label("mark_description"),
      d.description.label("department_description"),
      func.coalesce(stock_orig_totals.c.stock_total, 0).label("stock_origin"),
      pf.minimal_stock.label("minimum_stock"),
      pf.maximum_stock.label("maximum_stock"),
      func.coalesce(stock_dst_totals.c.stock_total, 0).label("stock_destination"),
      u.description.label("unit_description"),
      to_transfer,
    )
    .join(stock_orig_totals, Product.code == stock_orig_totals.c.product_code)
    .outerjoin(stock_dst_totals, Product.code == stock_dst_totals.c.product_code)
    .outerjoin(pf, (Product.code == pf.product_code) & (pf.store_code == store_dst))
    .join(pu, (Product.code == pu.product_code) & (pu.main_unit == True))
    .join(u, pu.unit == u.code)
    .join(d, Product.department == d.code)
    .outerjoin(m, Product.mark == m.code)
    .where(
      (func.coalesce(stock_orig_totals.c.stock_total, 0) > 0)
      & (func.coalesce(stock_dst_totals.c.stock_total, 0) < pf.minimal_stock)
      & (needed > 0)
      & (~Product.code.in_(select(checked_embarked_products.c.product_code)))
    )
  )

  results = db.session.execute(stmt).all()
  unique_depts = sorted(
    list(
      set(
        row.department_description for row in results if row.department_description
      )
    )
  )
  unique_marks = sorted(
    list(set(row.mark_description for row in results if row.mark_description))
  )

  return {
    "stores": stores,
    "store_origin_obj": store_origin_obj,
    "store_dst_obj": store_dst_obj,
    "products": results,
    "departments": unique_depts,
    "marks": unique_marks,
  }


def get_order_for_report(order_id):
  return InventoryOperation.query.options(
    joinedload(InventoryOperation.store1),
    joinedload(InventoryOperation.store2),
    joinedload(InventoryOperation.user),
    joinedload(InventoryOperation.details).options(
      joinedload(InventoryOperationDetail.product),
      joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1),
      joinedload(InventoryOperationDetail.failure_info),
    ),
  ).get_or_404(order_id)


def get_order_by_id(order_id):
  return InventoryOperation.query.get(order_id)


def get_order_details(order_id):
  return InventoryOperationDetail.query.filter_by(main_correlative=order_id).all()


def get_user_checking_progress_map(operation_correlative, user_code):
  if not operation_correlative or not user_code:
    return {}

  rows = InventoryOperationCheckingProgress.query.filter_by(
    operation_correlative=operation_correlative,
    user_code=user_code,
  ).all()

  return {
    normalize_code(row.product_code): float(row.counted_amount or 0.0)
    for row in rows
  }


def upsert_user_checking_progress(operation_correlative, user_code, product_code, counted_amount):
  normalized_code = normalize_code(product_code)
  if not operation_correlative or not user_code or not normalized_code:
    raise ValueError("Missing required fields to persist checking progress.")

  existing = InventoryOperationCheckingProgress.query.filter_by(
    operation_correlative=operation_correlative,
    user_code=user_code,
    product_code=normalized_code,
  ).first()

  if existing:
    existing.counted_amount = float(counted_amount)
    existing.updated_at = datetime.now()
    db.session.flush()
    return existing

  record = InventoryOperationCheckingProgress(
    operation_correlative=operation_correlative,
    user_code=user_code,
    product_code=normalized_code,
    counted_amount=float(counted_amount),
    updated_at=datetime.now(),
  )
  db.session.add(record)
  db.session.flush()
  return record


def delete_user_checking_progress_item(operation_correlative, user_code, product_code):
  normalized_code = normalize_code(product_code)
  if not operation_correlative or not user_code or not normalized_code:
    return 0

  deleted = InventoryOperationCheckingProgress.query.filter_by(
    operation_correlative=operation_correlative,
    user_code=user_code,
    product_code=normalized_code,
  ).delete(synchronize_session=False)
  return deleted


def clear_user_checking_progress(operation_correlative, user_code):
  if not operation_correlative or not user_code:
    return 0

  deleted = InventoryOperationCheckingProgress.query.filter_by(
    operation_correlative=operation_correlative,
    user_code=user_code,
  ).delete(synchronize_session=False)
  return deleted


def get_check_order_rows(order_id):
  io = aliased(InventoryOperation)
  iod = aliased(InventoryOperationDetail)
  pu = aliased(ProductsUnit)
  p = aliased(Product)
  u = aliased(Unit)
  store_dst = aliased(Store)
  store_origin = aliased(Store)

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
  return db.session.execute(stmt).all()


def get_product_by_code(code):
  return Product.query.filter(func.upper(func.trim(Product.code)) == normalize_code(code)).first()


def get_main_unit_for_product(code):
  return (
    ProductsUnit.query.filter(
      func.upper(func.trim(ProductsUnit.product_code)) == normalize_code(code),
      ProductsUnit.main_unit.is_(True),
    )
    .options(joinedload(ProductsUnit.unit1))
    .first()
  )


def get_unit_by_code(code):
  return Unit.query.filter_by(code=code).first()


def get_unit_by_correlative(correlative):
  return Unit.query.join(ProductsUnit).filter(ProductsUnit.correlative == correlative).first()


def get_stock_for_product_store(product_code, store_code):
  return ProductsStock.query.filter(
    func.upper(func.trim(ProductsStock.product_code)) == normalize_code(product_code),
    ProductsStock.store == store_code,
  ).first()


def add_product_to_order(order_id, main_code, amount):
  product = get_product_by_code(main_code)
  order = get_order_by_id(order_id)
  pu = get_main_unit_for_product(main_code)

  if not product:
    return None, order, pu, None, "PRODUCT_NOT_FOUND"
  if not order:
    return product, None, pu, None, "ORDER_NOT_FOUND"
  if not pu:
    return product, order, None, None, "MAIN_UNIT_NOT_FOUND"

  tax = Tax.query.filter_by(code=product.buy_tax).first() if product.buy_tax else None
  stock = get_stock_for_product_store(main_code, order.store)
  stock_amount = stock.stock if stock else 0.0
  if stock_amount <= 0:
    return product, order, pu, None, "NO_STOCK"
  if amount is None or float(amount) <= 0:
    return product, order, pu, None, "INVALID_AMOUNT"
  if float(amount) > float(stock_amount):
    return product, order, pu, {"stock_amount": float(stock_amount)}, "INSUFFICIENT_STOCK"

  db.session.execute(
    text(
      """
      SELECT setval(sequence_name::regclass, max_line, true)
      FROM (
        SELECT pg_get_serial_sequence('public.inventory_operation_details', 'line') AS sequence_name,
               COALESCE(MAX(line), 1) AS max_line
          FROM public.inventory_operation_details
      ) sequence_state
      WHERE sequence_name IS NOT NULL
      """
    )
  )

  db.session.execute(
    text(
      """
      SELECT set_inventory_operation_details(:p_main_correlative, :p_line, :p_code_product,
      :p_description_product, :p_referenc, :p_mark, :p_model, :p_amount, :p_store, :p_locations,
      :p_destination_store, :p_destination_location, :p_unit, :p_conversion_factor, :p_unit_type,
      :p_unitary_cost, :p_buy_tax, :p_aliquot, :p_total_cost, :p_total_tax, :p_total, :p_coin_code,
      :p_change_price)
      """
    ),
    {
      "p_main_correlative": order_id,
      "p_line": 0,
      "p_code_product": main_code,
      "p_description_product": product.description,
      "p_referenc": product.referenc,
      "p_mark": product.mark,
      "p_model": product.model,
      "p_amount": float(amount),
      "p_store": order.store,
      "p_locations": "00",
      "p_destination_store": order.destination_store,
      "p_destination_location": "00",
      "p_unit": int(pu.correlative),
      "p_conversion_factor": 0.0,
      "p_unit_type": 0,
      "p_unitary_cost": 0.0,
      "p_buy_tax": product.buy_tax,
      "p_aliquot": tax.aliquot if tax else 0.0,
      "p_total_cost": 0.0,
      "p_total_tax": 0.0,
      "p_total": 0.0,
      "p_coin_code": "02",
      "p_change_price": False,
    },
  )

  new_detail = find_detail_by_codes(order_id, [main_code])
  unit = get_unit_by_code(pu.unit)
  return product, order, pu, {"detail": new_detail, "unit": unit}, None


def delete_detail_from_order(order_id, code_product):
  detail = find_detail_by_codes(order_id, [code_product])
  if detail:
    db.session.delete(detail)
    db.session.commit()
  return True


def delete_details_from_order(order_id, code_products):
  normalized_codes = [normalize_code(code) for code in code_products if code]
  if not normalized_codes:
    return 0

  details = (
    InventoryOperationDetail.query.filter(
      InventoryOperationDetail.main_correlative == order_id,
      func.upper(func.trim(InventoryOperationDetail.code_product)).in_(normalized_codes),
    )
    .all()
  )

  for detail in details:
    db.session.delete(detail)

  return len(details)


def get_transfer_operation_by_correlative(correlative):
  return InventoryOperation.query.filter_by(
    correlative=correlative,
    operation_type="TRANSFER",
  ).first()


def get_transfer_operation_details(correlative):
  return (
    InventoryOperationDetail.query.filter_by(main_correlative=correlative)
    .options(
      joinedload(InventoryOperationDetail.product),
      joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1),
    )
    .all()
  )


def count_reception_differences(operation_id):
  return InventoryOperationReceptionDifference.query.filter_by(
    operation_correlative=operation_id
  ).count()


def get_products_code_mapping(other_code):
  return ProductsCode.query.filter(
    func.upper(func.trim(ProductsCode.other_code)) == normalize_code(other_code)
  ).first()


def get_operation_detail_by_code(operation_id, product_code):
  return (
    InventoryOperationDetail.query.filter(
      InventoryOperationDetail.main_correlative == operation_id,
      func.upper(func.trim(InventoryOperationDetail.code_product)) == normalize_code(product_code),
    )
    .options(
      joinedload(InventoryOperationDetail.product),
      joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1),
    )
    .first()
  )


def register_missing_reception_differences(operation_id, counted_codes, user_code):
  counted_set = {normalize_code(code) for code in (counted_codes or set()) if code}
  details = InventoryOperationDetail.query.filter_by(main_correlative=operation_id).all()

  created = 0
  for detail in details:
    product_code = normalize_code(detail.code_product)
    if product_code in counted_set:
      continue

    existing_difference = get_reception_difference(operation_id, detail.line)
    if existing_difference:
      continue

    original_amount = float(detail.amount or 0.0)
    if abs(original_amount) <= 1e-9:
      continue

    missing_difference = InventoryOperationReceptionDifference(
      operation_correlative=operation_id,
      detail_line=detail.line,
      product_code=detail.code_product,
      original_amount=original_amount,
      counted_amount=0.0,
      difference=-original_amount,
      user_code=user_code,
    )
    db.session.add(missing_difference)
    detail.amount = 0.0
    created += 1

  db.session.flush()
  return created


def get_user_transfer_reception_progress_map(operation_id, user_code):
  if not operation_id or not user_code:
    return {}

  rows = InventoryOperationReceptionProgress.query.filter_by(
    operation_correlative=operation_id,
    user_code=user_code,
  ).all()
  return {
    normalize_code(row.product_code): float(row.counted_amount or 0.0)
    for row in rows
  }


def upsert_user_transfer_reception_progress(operation_id, user_code, product_code, counted_amount):
  normalized_code = normalize_code(product_code)
  if not operation_id or not user_code or not normalized_code:
    raise ValueError("Missing required fields to persist reception progress.")

  existing = InventoryOperationReceptionProgress.query.filter_by(
    operation_correlative=operation_id,
    user_code=user_code,
    product_code=normalized_code,
  ).first()

  if existing:
    existing.counted_amount = float(counted_amount)
    existing.updated_at = datetime.now()
    db.session.flush()
    return existing

  progress = InventoryOperationReceptionProgress(
    operation_correlative=operation_id,
    user_code=user_code,
    product_code=normalized_code,
    counted_amount=float(counted_amount),
    updated_at=datetime.now(),
  )
  db.session.add(progress)
  db.session.flush()
  return progress


def clear_transfer_reception_progress(operation_id):
  if not operation_id:
    return 0

  deleted = InventoryOperationReceptionProgress.query.filter_by(
    operation_correlative=operation_id,
  ).delete(synchronize_session=False)
  return deleted


def get_failure_info(product_code, store_code):
  return ProductsFailure.query.filter_by(
    product_code=normalize_code(product_code),
    store_code=store_code,
  ).first()


def get_transfer_operation_report_data(order_id):
  order = InventoryOperation.query.options(
    joinedload(InventoryOperation.store1),
    joinedload(InventoryOperation.store2),
    joinedload(InventoryOperation.user),
    joinedload(InventoryOperation.details).options(
      joinedload(InventoryOperationDetail.product),
      joinedload(InventoryOperationDetail.products_unit).joinedload(ProductsUnit.unit1),
      joinedload(InventoryOperationDetail.failure_info),
    ),
  ).get_or_404(order_id)
  return order


def get_transfer_reception_differences_report_data(order_id):
  order = InventoryOperation.query.options(
    joinedload(InventoryOperation.store1),
    joinedload(InventoryOperation.store2),
    joinedload(InventoryOperation.user),
  ).get_or_404(order_id)
  differences = (
    InventoryOperationReceptionDifference.query.filter_by(
      operation_correlative=order_id
    )
    .options(
      joinedload(InventoryOperationReceptionDifference.product),
      joinedload(InventoryOperationReceptionDifference.user),
    )
    .order_by(InventoryOperationReceptionDifference.detail_line.asc())
    .all()
  )
  return order, differences


def get_products_locations_view_data(store_code, location):
  stores = get_all_stores()
  store_obj = get_store_by_code(store_code) if store_code else None
  return {
    "stores": stores,
    "store": store_obj,
    "location": location,
  }


def bulk_update_product_location(store_code, location, products):
  updated = 0
  for code in products:
    pf = ProductsFailure.query.filter_by(
      product_code=code,
      store_code=store_code,
    ).first()
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
    updated += 1

  db.session.commit()
  return updated


def get_search_product_for_location_data(product_code, store_code):
  products_code = ProductsCode.query.filter_by(other_code=product_code).first()
  main_code = products_code.main_code if products_code else product_code
  product = Product.query.filter_by(code=main_code).first()
  pf = None
  if store_code and product:
    pf = ProductsFailure.query.filter_by(
      product_code=main_code,
      store_code=store_code,
    ).first()
  return product, pf


def resolve_main_code_by_other_code(code):
  products_code = ProductsCode.query.filter_by(other_code=code).first()
  return products_code.main_code if products_code else code


def build_product_params_payload(store_code, code_product):
  main_code = resolve_main_code_by_other_code(code_product)
  product = Product.query.filter_by(code=main_code).first()
  if not product:
    return None, main_code

  product_failure = ProductsFailure.query.filter_by(
    product_code=main_code,
    store_code=store_code,
  ).first()
  product_stock = ProductsStock.query.filter_by(
    product_code=main_code,
    store=store_code,
  ).first()

  payload = {
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
      if product_failure and product_failure.location
      else ""
    ),
  }
  return payload, main_code


def upsert_product_params(store_code, code_product, minimal_stock, maximum_stock, location):
  main_code = resolve_main_code_by_other_code(code_product)
  pf = ProductsFailure.query.filter_by(
    product_code=main_code,
    store_code=store_code,
  ).first()

  if pf:
    pf.minimal_stock = minimal_stock
    pf.maximum_stock = maximum_stock
    pf.location = location
  else:
    pf = ProductsFailure(
      product_code=main_code,
      store_code=store_code,
      minimal_stock=minimal_stock,
      maximum_stock=maximum_stock,
      location=location,
    )
    db.session.add(pf)

  db.session.commit()
  return main_code


def apply_transfer_reception_count(
  operation_id,
  product_code,
  destination_store,
  counted_amount,
  minimal_stock,
  maximum_stock,
  user_code,
):
  detail = InventoryOperationDetail.query.filter(
    InventoryOperationDetail.main_correlative == operation_id,
    func.upper(func.trim(InventoryOperationDetail.code_product)) == normalize_code(product_code),
  ).first()

  if not detail:
    return None, "PRODUCT_NOT_FOUND"

  failure_info = ProductsFailure.query.filter(
    func.upper(func.trim(ProductsFailure.product_code)) == normalize_code(product_code),
    func.trim(ProductsFailure.store_code) == destination_store,
  ).first()

  if not failure_info:
    failure_info = ProductsFailure(
      product_code=normalize_code(product_code),
      store_code=destination_store,
      minimal_stock=minimal_stock or 0,
      maximum_stock=maximum_stock or 0,
      location="",
    )
    db.session.add(failure_info)
  else:
    failure_info.minimal_stock = minimal_stock or 0
    failure_info.maximum_stock = maximum_stock or 0

  existing_difference = get_reception_difference(operation_id, detail.line)
  original_amount = (
    float(existing_difference.original_amount)
    if existing_difference
    else float(detail.amount or 0)
  )
  difference_amount = float(counted_amount) - original_amount

  if difference_amount != 0:
    if not existing_difference:
      existing_difference = InventoryOperationReceptionDifference(
        operation_correlative=operation_id,
        detail_line=detail.line,
        product_code=detail.code_product,
        original_amount=original_amount,
        counted_amount=float(counted_amount),
        difference=difference_amount,
        user_code=user_code,
      )
      db.session.add(existing_difference)
    else:
      existing_difference.counted_amount = float(counted_amount)
      existing_difference.difference = difference_amount
      existing_difference.user_code = user_code
      existing_difference.updated_at = datetime.now()

    detail.amount = float(counted_amount)
  else:
    if existing_difference:
      detail.amount = original_amount
      db.session.delete(existing_difference)

  upsert_user_transfer_reception_progress(
    operation_id,
    user_code,
    detail.code_product,
    counted_amount,
  )

  db.session.commit()
  return {
    "detail": detail,
    "counted_amount": counted_amount,
    "expected_amount": original_amount,
    "difference_amount": difference_amount,
  }, None


def get_product_counter_context(user_code, store_code, counters_by_user):
  stores = get_all_stores()
  store = get_store_by_code(store_code) if store_code else None
  store_counters = {}
  if store and counters_by_user:
    store_counters = counters_by_user.get(store.code, {}) or {}

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
      {
        "product": product_row,
        "system_qty": sys_q,
        "unit": unit_rel.unit1 if unit_rel else None,
        "counted_amount": qty,
        "difference": diff,
        "store_code": store.code if store else store_code,
      }
    )

  return {"stores": stores, "store": store, "rows": rows}


def get_search_product_counter_data(store_code, product_code):
  main_code = resolve_main_code_by_other_code((product_code or "").strip())
  product_info = Product.query.filter_by(code=main_code).first()
  store = get_store_by_code(store_code)
  stock = ProductsStock.query.filter_by(product_code=main_code, store=store_code).first()
  unit = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()
  return {
    "product": product_info,
    "store": store,
    "stock": stock,
    "unit": unit.unit1 if unit is not None else None,
  }


def classify_counter_differences(store_counters):
  positive_diffs = {}
  negative_diffs = {}
  zero_diffs = {}

  for code, item in store_counters.items():
    if isinstance(item, dict):
      system_qty = float(item.get("system_qty", 0) or 0)
      counted = float(item.get("counted", 0) or 0)
      difference = float(item.get("difference", counted - system_qty) or 0)
    else:
      counted = float(item or 0)
      system_qty = 0.0
      difference = counted - system_qty

    payload = {
      "system_qty": system_qty,
      "counted": counted,
      "difference": difference,
    }
    if difference > 0:
      positive_diffs[code] = payload
    elif difference < 0:
      negative_diffs[code] = payload
    else:
      zero_diffs[code] = payload

  return positive_diffs, negative_diffs, zero_diffs


def save_counter_adjustments(store_code, user_code, store_counters):
  positive_diffs, negative_diffs, _zero_diffs = classify_counter_differences(store_counters)
  if not positive_diffs and not negative_diffs:
    return None

  store = get_store_by_code(store_code)
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

  if positive_diffs:
    header_params_load = {
      "p_correlative": None,
      "p_operation_type": "LOAD",
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
      data_row = (
        db.session.query(ProductsUnit, Product, Tax)
        .join(Product, ProductsUnit.product_code == Product.code)
        .outerjoin(Tax, Product.buy_tax == Tax.code)
        .filter(ProductsUnit.product_code == code, ProductsUnit.main_unit == True)
        .first()
      )
      if not data_row:
        continue
      pu, prod, tax = data_row
      db.session.execute(
        sql_detail,
        {
          "p_main_correlative": load_correlative,
          "p_line": 0,
          "p_code_product": code,
          "p_description_product": prod.description,
          "p_referenc": prod.referenc,
          "p_mark": prod.mark,
          "p_model": prod.model,
          "p_amount": float(data["difference"]),
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
        },
      )

  if negative_diffs:
    header_params_down = {
      "p_correlative": None,
      "p_operation_type": "DOWNLOAD",
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
        continue
      pu, prod, tax = data_row
      db.session.execute(
        sql_detail,
        {
          "p_main_correlative": download_correlative,
          "p_line": 0,
          "p_code_product": code,
          "p_description_product": prod.description,
          "p_referenc": prod.referenc,
          "p_mark": prod.mark,
          "p_model": prod.model,
          "p_amount": abs(float(data["difference"])),
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
        },
      )

  today = datetime.now().date()
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

    history = ProductsCounterHistory.query.filter_by(product_code=code, store_code=store_code).first()
    if not history:
      history = ProductsCounterHistory(product_code=code, store_code=store_code, user_code=user_code)
      db.session.add(history)

    history.user_code = user_code
    history.count_batch_id = count_batch_id
    history.count_date = today
    history.system_qty = system_qty
    history.counted_qty = counted
    history.difference = difference
    if difference > 0 and load_correlative:
      history.operation_correlative_up = load_correlative
      history.operation_correlative_down = None
    elif difference < 0 and download_correlative:
      history.operation_correlative_down = download_correlative
      history.operation_correlative_up = None
    else:
      history.operation_correlative_up = None
      history.operation_correlative_down = None

  db.session.commit()
  return count_batch_id


def get_counter_history_items(count_batch_id):
  return (
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


def get_counter_history_records(count_batch_id):
  return ProductsCounterHistory.query.filter_by(count_batch_id=count_batch_id).all()


def get_modal_product_params_data(product_code, store_code):
  main_code = resolve_main_code(product_code)
  product_info = Product.query.filter_by(code=main_code).first()
  store_info = get_store_by_code(store_code)
  product_params = ProductsFailure.query.filter_by(product_code=main_code, store_code=store_code).first()
  unit_row = ProductsUnit.query.filter_by(product_code=main_code, main_unit=True).first()
  return {
    "main_code": main_code,
    "product": product_info,
    "store": store_info,
    "product_params": product_params,
    "unit": unit_row.unit1 if unit_row else None,
  }


def get_open_package(operation_correlative):
  return (
    InventoryOperationPackage.query.filter_by(
      operation_correlative=operation_correlative,
      status="OPEN",
    )
    .order_by(InventoryOperationPackage.package_number.desc())
    .first()
  )


def get_package_by_id(package_id):
  return (
    InventoryOperationPackage.query.filter_by(correlative=package_id)
    .options(
      joinedload(InventoryOperationPackage.inventory_operation),
      joinedload(InventoryOperationPackage.package_details).joinedload(
        InventoryOperationPackageDetail.product
      ),
    )
    .first()
  )


def open_package_for_operation(operation_correlative, user_code):
  flow = get_inventory_operation_flow(operation_correlative)
  if not flow:
    raise ValueError("La orden no tiene flujo de traslado registrado.")
  if flow["current_status"] != FLOW_RECOLLECTION_ISSUED:
    raise ValueError("La orden ya no permite abrir bultos para embalaje.")

  open_package = get_open_package(operation_correlative)
  if open_package:
    raise ValueError(
      f"Ya existe un bulto abierto (Bulto {open_package.package_number})."
    )

  max_number = (
    db.session.query(func.max(InventoryOperationPackage.package_number))
    .filter(InventoryOperationPackage.operation_correlative == operation_correlative)
    .scalar()
  )

  package = InventoryOperationPackage(
    operation_correlative=operation_correlative,
    package_number=(max_number or 0) + 1,
    status="OPEN",
    opened_user=user_code,
  )
  db.session.add(package)
  db.session.flush()
  return package


def close_open_package_for_operation(operation_correlative, user_code, allow_empty=False):
  flow = get_inventory_operation_flow(operation_correlative)
  if not flow:
    raise ValueError("La orden no tiene flujo de traslado registrado.")
  if flow["current_status"] != FLOW_RECOLLECTION_ISSUED:
    raise ValueError("La orden ya no permite cerrar bultos para embalaje.")

  package = get_open_package(operation_correlative)
  if not package:
    raise ValueError("No hay un bulto abierto para cerrar.")
  if not package.package_details:
    if allow_empty:
      db.session.delete(package)
      db.session.flush()
      return None
    raise ValueError("No se puede cerrar un bulto vacio.")

  package.status = "CLOSED"
  package.closed_user = user_code
  package.closed_at = datetime.now()
  db.session.flush()
  return package


def close_all_open_packages_for_operation(operation_correlative, user_code):
  closed_packages = []

  while True:
    open_package = get_open_package(operation_correlative)
    if not open_package:
      break

    if not open_package.package_details:
      # Discard empty open packages during final confirmation to avoid blocking report emission.
      db.session.delete(open_package)
      db.session.flush()
      continue

    open_package.status = "CLOSED"
    open_package.closed_user = user_code
    open_package.closed_at = datetime.now()
    closed_packages.append(open_package)

  db.session.flush()
  return closed_packages


def _get_counted_amount_by_product(operation_correlative):
  rows = (
    db.session.query(
      InventoryOperationDetail.code_product,
      func.coalesce(func.sum(InventoryOperationDetail.amount), 0.0),
    )
    .filter(InventoryOperationDetail.main_correlative == operation_correlative)
    .group_by(InventoryOperationDetail.code_product)
    .all()
  )
  return {normalize_code(code): float(total or 0.0) for code, total in rows}


def _get_packed_amount_by_product(operation_correlative):
  rows = (
    db.session.query(
      InventoryOperationPackageDetail.product_code,
      func.coalesce(func.sum(InventoryOperationPackageDetail.packed_amount), 0.0),
    )
    .join(
      InventoryOperationPackage,
      InventoryOperationPackage.correlative
      == InventoryOperationPackageDetail.package_correlative,
    )
    .filter(
      InventoryOperationPackage.operation_correlative == operation_correlative,
      InventoryOperationPackage.status.in_(["OPEN", "CLOSED"]),
    )
    .group_by(InventoryOperationPackageDetail.product_code)
    .all()
  )
  return {normalize_code(code): float(total or 0.0) for code, total in rows}


def upsert_open_package_product(operation_correlative, product_code, packed_amount, user_code):
  normalized_code = normalize_code(product_code)
  if not normalized_code:
    raise ValueError("Debe indicar un codigo de producto valido.")
  if packed_amount is None:
    raise ValueError("La cantidad embalada es obligatoria.")

  package = get_open_package(operation_correlative)
  if not package:
    raise ValueError("Debe abrir un bulto antes de embalar productos.")

  detail = find_detail_by_codes(operation_correlative, [normalized_code])
  if not detail:
    raise ValueError("El producto no pertenece a la orden de recoleccion.")

  counted_map = _get_counted_amount_by_product(operation_correlative)
  counted_amount = float(counted_map.get(normalized_code, 0.0))

  packed_map = _get_packed_amount_by_product(operation_correlative)
  current_total = float(packed_map.get(normalized_code, 0.0))

  existing_line = InventoryOperationPackageDetail.query.filter_by(
    package_correlative=package.correlative,
    product_code=normalized_code,
  ).first()
  previous_amount = float(existing_line.packed_amount) if existing_line else 0.0

  # Si el usuario deja el conteo en 0, removemos el producto del bulto abierto.
  if float(packed_amount) <= 0:
    if existing_line:
      db.session.delete(existing_line)
      db.session.flush()
    return None

  projected_total = current_total - previous_amount + float(packed_amount)
  if projected_total > counted_amount + 1e-9:
    raise ValueError(
      "La cantidad embalada supera el total contado para este producto."
    )

  if not existing_line:
    existing_line = InventoryOperationPackageDetail(
      package_correlative=package.correlative,
      product_code=normalized_code,
      packed_amount=float(packed_amount),
      updated_user=user_code,
    )
    db.session.add(existing_line)
  else:
    existing_line.packed_amount = float(packed_amount)
    existing_line.updated_user = user_code
    existing_line.updated_at = datetime.now()

  db.session.flush()
  return existing_line


def get_open_package_progress(operation_correlative):
  package = get_open_package(operation_correlative)
  if not package:
    return None

  details = package.package_details or []
  product_lines = len(details)
  total_units = sum(float(item.packed_amount or 0.0) for item in details)

  return {
    "package_id": package.correlative,
    "package_number": package.package_number,
    "product_lines": product_lines,
    "total_units": float(total_units),
  }


def get_operation_packages(operation_correlative):
  return (
    InventoryOperationPackage.query.filter_by(
      operation_correlative=operation_correlative,
    )
    .options(
      joinedload(InventoryOperationPackage.package_details).joinedload(
        InventoryOperationPackageDetail.product
      ),
      joinedload(InventoryOperationPackage.opened_by),
      joinedload(InventoryOperationPackage.closed_by),
    )
    .order_by(InventoryOperationPackage.package_number.asc())
    .all()
  )


def validate_packing_matches_counted(operation_correlative):
  open_package = get_open_package(operation_correlative)
  counted_map = _get_counted_amount_by_product(operation_correlative)
  packed_map = _get_packed_amount_by_product(operation_correlative)

  mismatches = []
  all_codes = sorted(set(counted_map.keys()) | set(packed_map.keys()))
  for code in all_codes:
    counted = float(counted_map.get(code, 0.0))
    packed = float(packed_map.get(code, 0.0))
    if abs(counted - packed) > 1e-9:
      mismatches.append(
        {
          "product_code": code,
          "counted_amount": counted,
          "packed_amount": packed,
          "difference": counted - packed,
        }
      )

  return {
    "has_open_package": bool(open_package),
    "open_package_number": open_package.package_number if open_package else None,
    "mismatches": mismatches,
    "is_valid": not open_package and len(mismatches) == 0,
  }


def lock_packages_for_operation(operation_correlative):
  packages = InventoryOperationPackage.query.filter_by(
    operation_correlative=operation_correlative
  ).all()
  now = datetime.now()
  for package in packages:
    if not package.locked_at:
      package.locked_at = now
  db.session.flush()


def rollback_session():
  db.session.rollback()


def commit_session():
  db.session.commit()
