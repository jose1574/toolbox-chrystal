from flask import jsonify, render_template, request
from flask_login import login_required, current_user
from app.document_manager import document_manager_bp 
from sqlalchemy.orm import joinedload
from app.models import InventoryOperation, InventoryOperationPackage
from app import db

@document_manager_bp.route("/")
@login_required
def index():
    document_type = (request.args.get("document_type") or "order_report").strip()
    if document_type not in {"order_report", "package_label"}:
        document_type = "order_report"
    package_order_id = request.args.get("package_order_id", type=int)

    transfer_operations = []
    packages = []

    if document_type == "order_report":
        transfer_operations = (
            InventoryOperation.query.filter_by(operation_type="TRANSFER", wait=True)
            .options(joinedload(InventoryOperation.operation_flow))
            .order_by(InventoryOperation.correlative.desc())
            .all()
        )
    else:
        packages_query = (
            InventoryOperationPackage.query.options(
                joinedload(InventoryOperationPackage.inventory_operation).joinedload(
                    InventoryOperation.store2
                ),
                joinedload(InventoryOperationPackage.inventory_operation).joinedload(
                    InventoryOperation.store1
                ),
            )
            .join(InventoryOperation)
            .filter(InventoryOperation.operation_type == "TRANSFER")
        )

        if package_order_id:
            packages_query = packages_query.filter(
                InventoryOperationPackage.operation_correlative == package_order_id
            )

        packages = packages_query.order_by(
            InventoryOperationPackage.operation_correlative.desc(),
            InventoryOperationPackage.package_number.asc(),
        ).all()

    return render_template(
        "document_manager/index.html",
        user=current_user,
        document_type=document_type,
        package_order_id=package_order_id,
        transfer_operations=transfer_operations,
        packages=packages,
    )



# @document_manager_bp.route("/transfer/delete/", methods=["POST"])
# @login_required 
# def delete_transfers():
#     # Obtener correlativos del JSON
#     data = request.get_json()
#     correlatives = data.get('correlatives', [])
    
#     # Validar que sea una lista de strings/números
#     if isinstance(correlatives, (str, int)):
#         correlatives = [correlatives]
#     if not isinstance(correlatives, list) or not correlatives:
#         return jsonify({"status": "error", "message": "Debe proporcionar una lista de correlativos."}), 400
    
#     deleted_count = 0
#     try:
#         for item in correlatives:
#             correlative = int(item)
            
#             # Verificar existencia y eliminar (los detalles se eliminan en cascada por la DB)
#             if InventoryOperation.query.filter_by(correlative=correlative, operation_type="TRANSFER", wait=True).first():
#                 InventoryOperation.query.filter_by(correlative=correlative, operation_type="TRANSFER", wait=True).delete(synchronize_session=False)
#                 deleted_count += 1
        
#         db.session.commit()
#         return jsonify({"status": "success", "message": f"Eliminadas {deleted_count} operaciones."}), 200
    
#     except ValueError:
#         return jsonify({"status": "error", "message": "Correlativos inválidos."}), 400
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({"status": "error", "message": "Error interno.", "detail": str(e)}), 500


@document_manager_bp.route("/transfer/delete/", methods=["POST"])
@login_required
def delete_transfers():
    data = request.get_json(silent=True) or {}
    correlatives = data.get("correlatives", [])

    if isinstance(correlatives, (str, int)):
        correlatives = [correlatives]
    if not isinstance(correlatives, list) or not correlatives:
        return jsonify({"status": "error", "message": "Debe proporcionar una lista de correlativos."}), 400

    deleted_count = 0
    try:
        for item in correlatives:
            correlative = int(item)

            deleted_count += InventoryOperation.query.filter_by(
                correlative=correlative,
                operation_type="TRANSFER",
                wait=True,
            ).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({"status": "success", "message": f"Eliminadas {deleted_count} operaciones."}), 200

    except ValueError:
        return jsonify({"status": "error", "message": "Correlativos inválidos."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Error interno.", "detail": str(e)}), 500