from flask import Response, render_template, request
from flask_login import login_required
from app.reports import reports_bp
from app.reports.utils import render_pdf
from app.models import User
from datetime import datetime


@reports_bp.route('/users')
@login_required
def users_report():
    users = User.query.all()
    return render_template('reports/users.html', users=users)


@reports_bp.route('/users/pdf')
@login_required
def users_report_pdf():
    users = User.query.all()
    download = request.args.get('download', '0') == '1'
    filename = 'reporte_usuarios.pdf'
    try:
        pdf = render_pdf(
            'reports/users_pdf.html',
            {
                'users': users,
                'title': 'Reporte de Usuarios',
                'now': datetime.now,
            },
        )
    except Exception as exc:
        return (
            f"Error generando PDF: {exc}",
            500,
        )

    disposition = 'attachment' if download else 'inline'
    headers = {
        'Content-Disposition': f"{disposition}; filename={filename}"
    }
    return Response(pdf, mimetype='application/pdf', headers=headers)
