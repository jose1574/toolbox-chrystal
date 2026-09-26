import pymupdf
from escpos.printer import Network
from PIL import Image, ImageWin


def _rasterize_pdf(pdf_content, width_dots):
    if width_dots <= 0:
        raise ValueError("El ancho de impresion debe ser mayor que cero.")

    document = pymupdf.open(stream=pdf_content, filetype="pdf")
    try:
        if document.page_count != 1:
            raise ValueError("El reporte de despacho debe tener una sola pagina.")

        page = document[0]
        scale = width_dots / page.rect.width
        raster = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
        image = Image.frombytes(
            "RGB", (raster.width, raster.height), raster.samples
        )
        return image.convert("L").convert("1")
    finally:
        document.close()


def _print_image_via_windows_driver(image, printer_name, job_name):
    """Imprime una imagen PIL a traves del driver de Windows (GDI).

    Escala la imagen al ancho imprimible y pagina en vertical si el recibo es
    mas alto que una pagina del driver.
    """
    import win32con
    import win32ui

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    try:
        page_width = hdc.GetDeviceCaps(win32con.HORZRES)
        page_height = hdc.GetDeviceCaps(win32con.VERTRES)
        if page_width <= 0 or page_height <= 0:
            raise ValueError("La impresora no reporto un area imprimible valida.")

        scale = page_width / image.width
        scaled_height = image.height * scale
        dib = ImageWin.Dib(image)

        hdc.StartDoc(job_name)
        try:
            offset = 0
            while offset < scaled_height:
                src_top = int(offset / scale)
                src_bottom = min(image.height, int((offset + page_height) / scale))
                hdc.StartPage()
                dib.draw(
                    hdc.GetHandleOutput(),
                    (0, 0, page_width, int((src_bottom - src_top) * scale)),
                    (0, src_top, image.width, src_bottom),
                )
                hdc.EndPage()
                offset += page_height
        finally:
            hdc.EndDoc()
    finally:
        hdc.DeleteDC()


def print_pdf_to_windows_printer(
    pdf_content, printer_name, width_dots=576, job_name="Recibo de despacho"
):
    if not printer_name:
        raise ValueError(
            "No hay una impresora configurada para este dispositivo ni una "
            "predeterminada en el servidor."
        )
    image = _rasterize_pdf(pdf_content, width_dots)
    _print_image_via_windows_driver(image, printer_name, job_name)


def print_dispatched_products(
    pdf_content, host, port, width_dots=576, timeout=5
):
    image = _rasterize_pdf(pdf_content, width_dots)
    printer = Network(
        host=host,
        port=port,
        timeout=timeout,
        profile="TM-T20II",
    )
    try:
        printer.image(image, impl="bitImageRaster", center=False)
        printer.textln("")
        printer.textln("")
    finally:
        printer.close()
