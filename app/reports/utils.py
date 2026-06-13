import pdfkit
import os
import platform
import base64
from io import BytesIO
from pathlib import Path
import barcode
from barcode.writer import ImageWriter
from flask import render_template
from jinja2 import Template

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
            'write_text': False,
        }
        
        # Buffer para guardar la imagen
        buffer = BytesIO()
        BARCODE(str(data), writer=ImageWriter()).write(buffer, options=writer_options)
        
        # Convertir a base64
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error generando código de barras: {e}")
        return None

def render_pdf(
    template_src,
    context_dict=None,
    paper_format='Letter',
    orientation='Portrait',
    extra_options=None,
):
    """
    Renderiza un template de HTML a PDF usando pdfkit.
    Permite especificar el formato de papel (Letter, A4, HalfLetter, etc.)
    y la orientación (Portrait, Landscape).
    """
    if context_dict is None:
        context_dict = {}

    html = render_template(template_src, **context_dict)
    
    # Mapeo de formatos personalizados o específicos
    paper_configs = {
        'Letter': {'page-size': 'Letter'},
        'A4': {'page-size': 'A4'},
        'HalfLetter': {
            'page-width': '5.5in',
            'page-height': '8.5in'
        },
        'Label56x44': {
            'page-width': '56mm',
            'page-height': '44mm',
        },
        'Label57x44': {
            'page-width': '57mm',
            'page-height': '44mm',
        },
        'Label57x40': {
            'page-width': '57mm',
            'page-height': '40mm',
        },
        'Label57x32': {
            'page-width': '57mm',
            'page-height': '32mm',
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

    if extra_options:
        options.update(extra_options)
    
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
            return pdfkit.from_string(
                html,
                False,
                configuration=config,
                options=options,
            )
        # Si no se encontró en rutas estándar, intentar desde el PATH
        return pdfkit.from_string(html, False, options=options)
    except OSError as e:
        error_msg = f"Error generando PDF. Asegúrate de tener wkhtmltopdf instalado y en el PATH.\nDetalles: {e}"
        print(error_msg) # Loggear el error
        raise RuntimeError(error_msg)


def render_pdf_from_html_file(
    html_file_path,
    context_dict=None,
    paper_format='Letter',
    orientation='Portrait',
    extra_options=None,
):
    """
    Renderiza un archivo HTML (fuera de templates) como Jinja y lo convierte a PDF.
    """
    if context_dict is None:
        context_dict = {}

    template_source = Path(html_file_path).read_text(encoding='utf-8')
    html = Template(template_source).render(**context_dict)

    paper_configs = {
        'Letter': {'page-size': 'Letter'},
        'A4': {'page-size': 'A4'},
        'HalfLetter': {
            'page-width': '5.5in',
            'page-height': '8.5in'
        },
        'Label56x44': {
            'page-width': '56mm',
            'page-height': '44mm',
        },
        'Label57x44': {
            'page-width': '57mm',
            'page-height': '44mm',
        },
        'Label57x40': {
            'page-width': '57mm',
            'page-height': '40mm',
        },
        'Label57x32': {
            'page-width': '57mm',
            'page-height': '32mm',
        }
    }

    size_options = paper_configs.get(paper_format, paper_configs['Letter']).copy()

    options = {
        'orientation': orientation,
        'margin-top': '0.2in',
        'margin-right': '0.2in',
        'margin-bottom': '0.2in',
        'margin-left': '0.2in',
        'encoding': 'UTF-8',
        'no-outline': None,
        'enable-local-file-access': None,
    }
    options.update(size_options)
    if extra_options:
        options.update(extra_options)

    config = None
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
            return pdfkit.from_string(
                html,
                False,
                configuration=config,
                options=options,
            )
        return pdfkit.from_string(html, False, options=options)
    except OSError as e:
        error_msg = f"Error generando PDF. Asegúrate de tener wkhtmltopdf instalado y en el PATH.\nDetalles: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)
