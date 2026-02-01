import pdfkit
import os
import platform
import base64
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
from flask import render_template, current_app

def generate_barcode(data, barcode_type='code128'):
    """
    Genera un código de barras en formato base64.
    """
    try:
        BARCODE = barcode.get_barcode_class(barcode_type)
        writer_options = {
            'module_width': 0.2,
            'module_height': 7.0,
            'font_size': 8,
            'text_distance': 3.0,
            'quiet_zone': 1.0,
        }
        
        # Buffer para guardar la imagen
        buffer = BytesIO()
        BARCODE(str(data), writer=ImageWriter()).write(buffer, options=writer_options)
        
        # Convertir a base64
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error generando código de barras: {e}")
        return None

def render_pdf(template_src, context_dict={}, paper_format='Letter', orientation='Portrait'):
    """
    Renderiza un template de HTML a PDF usando pdfkit.
    Permite especificar el formato de papel (Letter, A4, HalfLetter, etc.)
    y la orientación (Portrait, Landscape).
    """
    html = render_template(template_src, **context_dict)
    
    # Mapeo de formatos personalizados o específicos
    paper_configs = {
        'Letter': {'page-size': 'Letter'},
        'A4': {'page-size': 'A4'},
        'HalfLetter': {
            'page-width': '5.5in',
            'page-height': '8.5in'
        }
    }

    # Obtener la configuración de tamaño, por defecto Letter
    size_options = paper_configs.get(paper_format, paper_configs['Letter']).copy()

    # Opciones base de configuración para pdfkit
    options = {
        'orientation': orientation,
        'margin-top': '0.2in',
        'margin-right': '0.2in',
        'margin-bottom': '0.2in',
        'margin-left': '0.2in',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None
    }
    
    # Mezclar opciones de tamaño con opciones generales
    options.update(size_options)
    
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
