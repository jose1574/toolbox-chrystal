from sqlalchemy import text
from app import db


STATUS_LABELS = {
    "RECOLLECTION_ISSUED": "Orden emitida",
    "RECOLLECTION_CHECKED": "Chequeada",
    "IN_TRANSIT": "En traslado",
    "RECEIVED": "Recepcionada",
}


def get_dashboard_data():
    metrics_sql = text(
        """
        SELECT COUNT(io.correlative) AS total_transfers,
               COUNT(f.operation_correlative) AS app_transfers,
               SUM(CASE WHEN f.current_status = 'RECOLLECTION_ISSUED' THEN 1 ELSE 0 END) AS issued_count,
               SUM(CASE WHEN f.current_status = 'RECOLLECTION_CHECKED' THEN 1 ELSE 0 END) AS checked_count,
               SUM(CASE WHEN f.current_status = 'IN_TRANSIT' THEN 1 ELSE 0 END) AS transit_count,
               SUM(CASE WHEN f.current_status = 'RECEIVED' THEN 1 ELSE 0 END) AS received_count,
               SUM(CASE WHEN io.wait IS TRUE THEN 1 ELSE 0 END) AS open_transfers,
               SUM(CASE WHEN io.emission_date >= (CURRENT_DATE - INTERVAL '30 days') THEN 1 ELSE 0 END) AS last_30_days
          FROM public.inventory_operation io
          LEFT JOIN toolbox.inventory_operation_flow f
            ON f.operation_correlative = io.correlative
         WHERE io.operation_type = 'TRANSFER'
        """
    )

    recent_sql = text(
        """
        SELECT io.correlative,
               io.document_no,
               io.emission_date,
               io.store,
               origin_store.description AS store_description,
               io.destination_store,
               destination_store.description AS destination_store_description,
               COALESCE(f.current_status, 'SIN_FLUJO') AS current_status,
               io.description
          FROM public.inventory_operation io
          LEFT JOIN toolbox.inventory_operation_flow f
            ON f.operation_correlative = io.correlative
          LEFT JOIN public.store origin_store
            ON origin_store.code = io.store
          LEFT JOIN public.store destination_store
            ON destination_store.code = io.destination_store
         WHERE io.operation_type = 'TRANSFER'
         ORDER BY io.correlative DESC
         LIMIT 6
        """
    )

    metrics_row = db.session.execute(metrics_sql).first()
    recent_rows = db.session.execute(recent_sql).all()

    metrics = {
        "total_transfers": int(metrics_row.total_transfers or 0),
        "app_transfers": int(metrics_row.app_transfers or 0),
        "issued_count": int(metrics_row.issued_count or 0),
        "checked_count": int(metrics_row.checked_count or 0),
        "transit_count": int(metrics_row.transit_count or 0),
        "received_count": int(metrics_row.received_count or 0),
        "open_transfers": int(metrics_row.open_transfers or 0),
        "last_30_days": int(metrics_row.last_30_days or 0),
    }

    status_cards = [
        {
            "code": "RECOLLECTION_ISSUED",
            "label": STATUS_LABELS["RECOLLECTION_ISSUED"],
            "count": metrics["issued_count"],
            "class": "bg-amber-50 text-amber-800 border-amber-200",
        },
        {
            "code": "RECOLLECTION_CHECKED",
            "label": STATUS_LABELS["RECOLLECTION_CHECKED"],
            "count": metrics["checked_count"],
            "class": "bg-teal-50 text-teal-800 border-teal-200",
        },
        {
            "code": "IN_TRANSIT",
            "label": STATUS_LABELS["IN_TRANSIT"],
            "count": metrics["transit_count"],
            "class": "bg-blue-50 text-blue-800 border-blue-200",
        },
        {
            "code": "RECEIVED",
            "label": STATUS_LABELS["RECEIVED"],
            "count": metrics["received_count"],
            "class": "bg-green-50 text-green-800 border-green-200",
        },
    ]

    recent_transfers = [
        {
            "correlative": row.correlative,
            "document_no": row.document_no,
            "emission_date": row.emission_date,
            "store": row.store,
            "store_description": row.store_description,
            "destination_store": row.destination_store,
            "destination_store_description": row.destination_store_description,
            "current_status": row.current_status,
            "status_label": STATUS_LABELS.get(row.current_status, "Sin flujo"),
            "description": row.description,
        }
        for row in recent_rows
    ]

    return {
        "metrics": metrics,
        "status_cards": status_cards,
        "recent_transfers": recent_transfers,
    }
