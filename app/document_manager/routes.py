from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.document_manager import document_manager_bp 
from app.models import InventoryOperation
from app import db

@document_manager_bp.route("/")
@login_required
def index():
    transfer_operations = InventoryOperation.query.filter_by(operation_type="TRANSFER", wait=True).all()

    return render_template("document_manager/index.html", user=current_user, transfer_operations=transfer_operations)


@document_manager_bp.route("/transfer/delete/", methods=["POST"])
@login_required 
def delete_transfers():
    # Obtener correlativos del JSON
    data = request.get_json()
    correlatives = data.get('correlatives', [])
    
    # Validar que sea una lista de strings/números
    if isinstance(correlatives, (str, int)):
        correlatives = [correlatives]
    if not isinstance(correlatives, list) or not correlatives:
        return jsonify({"status": "error", "message": "Debe proporcionar una lista de correlativos."}), 400
    
    deleted_count = 0
    try:
        for item in correlatives:
            correlative = int(item)
            
            # Verificar existencia y eliminar (los detalles se eliminan en cascada por la DB)
            if InventoryOperation.query.filter_by(correlative=correlative, operation_type="TRANSFER", wait=True).first():
                InventoryOperation.query.filter_by(correlative=correlative, operation_type="TRANSFER", wait=True).delete(synchronize_session=False)
                deleted_count += 1
        
        db.session.commit()
        return jsonify({"status": "success", "message": f"Eliminadas {deleted_count} operaciones."}), 200
    
    except ValueError:
        return jsonify({"status": "error", "message": "Correlativos inválidos."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Error interno.", "detail": str(e)}), 500