import pdfkit
import os
import platform
from flask import render_template, current_app

def render_pdf(template_src, context_dict={}):
    """
    Renderiza un template de HTML a PDF usando pdfkit.
    """
    html = render_template(template_src, **context_dict)
    
    # Opciones de configuración para pdfkit
    options = {
        'page-size': 'Letter',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None  # Importante para cargar CSS/imágenes locales
    }
    
    config = None
    
    # Configuración específica para Windows si no está en el PATH
    if platform.system() == 'Windows':
        wkhtmltopdf_paths = [
            r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
            r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
        ]
        
        for path in wkhtmltopdf_paths:
            if os.path.exists(path):
                config = pdfkit.configuration(wkhtmltopdf=path)
                break
    
    try:
        if config:
            pdf = pdfkit.from_string(html, False, configuration=config, options=options)
        else:
            # Si no se encontró en rutas estándar, intentar desde el PATH
            pdf = pdfkit.from_string(html, False, options=options)
        return pdf
    except OSError as e:
        error_msg = f"Error generando PDF. Asegúrate de tener wkhtmltopdf instalado y en el PATH.\nDetalles: {e}"
        print(error_msg) # Loggear el error
        raise RuntimeError(error_msg)
