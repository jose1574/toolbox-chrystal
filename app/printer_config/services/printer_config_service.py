from datetime import datetime

from app import db
from app.models import PrinterSetting

# Reportes que admiten impresora configurable por dispositivo.
CONFIGURABLE_REPORTS = {
    "sales_dispatch": "Despacho de facturas de venta",
}


def list_installed_printers():
    """Lista las impresoras instaladas en el servidor (Windows).

    Devuelve una lista de dicts {name, is_default} ordenada por nombre.
    """
    import win32print

    try:
        default_name = win32print.GetDefaultPrinter()
    except Exception:
        default_name = None

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = []
    for _flags, _description, name, _comment in win32print.EnumPrinters(flags):
        printers.append({"name": name, "is_default": name == default_name})

    printers.sort(key=lambda item: item["name"].lower())
    return printers


def get_default_printer_name():
    import win32print

    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def get_device_settings(device_id):
    """Devuelve {report_key: printer_name} para el dispositivo indicado."""
    if not device_id:
        return {}
    rows = PrinterSetting.query.filter_by(device_id=device_id).all()
    return {row.report_key: row.printer_name for row in rows}


def save_device_printer(device_id, report_key, printer_name, user_code):
    """Guarda (upsert) la impresora elegida por el dispositivo para un reporte."""
    if report_key not in CONFIGURABLE_REPORTS:
        raise ValueError("Reporte no configurable.")
    if not device_id:
        raise ValueError("No se pudo identificar el dispositivo.")
    if not printer_name:
        raise ValueError("Debe seleccionar una impresora.")

    setting = PrinterSetting.query.filter_by(
        device_id=device_id, report_key=report_key
    ).first()
    if setting is None:
        setting = PrinterSetting(
            device_id=device_id,
            report_key=report_key,
            printer_name=printer_name,
            updated_by=user_code,
        )
        db.session.add(setting)
    else:
        setting.printer_name = printer_name
        setting.updated_by = user_code
        setting.updated_at = datetime.now()

    db.session.commit()
    return setting


def resolve_printer_name(device_id, report_key):
    """Impresora a usar para un reporte: la del dispositivo o la predeterminada."""
    printer_name = get_device_settings(device_id).get(report_key)
    if printer_name:
        return printer_name
    return get_default_printer_name()
