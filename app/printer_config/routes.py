from flask import render_template, request
from flask_login import current_user, login_required

from app import get_device_id
from app.printer_config import printer_config_bp
from app.printer_config.services import printer_config_service


def _cards_context():
    device_id = get_device_id()
    settings = printer_config_service.get_device_settings(device_id)
    printers = printer_config_service.list_installed_printers()
    cards = []
    for report_key, report_label in printer_config_service.CONFIGURABLE_REPORTS.items():
        cards.append(
            {
                "report_key": report_key,
                "report_label": report_label,
                "selected_printer": settings.get(report_key),
            }
        )
    return {
        "device_id": device_id,
        "cards": cards,
        "printers": printers,
    }


@printer_config_bp.route("/")
@login_required
def index():
    return render_template("printer_config/index.html", **_cards_context())


@printer_config_bp.route("/save", methods=["POST"])
@login_required
def save():
    report_key = (request.form.get("report_key") or "").strip()
    printer_name = (request.form.get("printer_name") or "").strip()
    report_label = printer_config_service.CONFIGURABLE_REPORTS.get(
        report_key, report_key
    )

    error = None
    try:
        printer_config_service.save_device_printer(
            get_device_id(), report_key, printer_name, current_user.code
        )
    except ValueError as exc:
        error = str(exc)

    current = printer_config_service.get_device_settings(get_device_id()).get(
        report_key
    )
    return render_template(
        "printer_config/partials/printer_card.html",
        card={
            "report_key": report_key,
            "report_label": report_label,
            "selected_printer": current,
        },
        printers=printer_config_service.list_installed_printers(),
        saved=error is None,
        error=error,
    )
