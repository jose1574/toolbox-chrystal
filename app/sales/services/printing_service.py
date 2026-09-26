import pymupdf
from escpos.printer import Network
from PIL import Image


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