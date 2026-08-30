# AGENTS.md

Guía de arquitectura y convenciones para trabajar en **Toolbox Chrystal**. Léela completa antes de generar, modificar o crear código.

## Visión general

Aplicación web **Flask** que complementa al ERP **Chrystal**. Su objetivo principal es reponer inventarios de forma automática y generar pedidos de compras automáticos. Expone paneles para administradores, usuarios internos y **proveedores** que gestionan ofertas/catálogos.

- **Backend:** Python 3 / Flask 3 (patrón de Blueprints)
- **ORM:** Flask-SQLAlchemy 2.0 sobre **PostgreSQL**
- **Auth:** Flask-Login (usuarios internos) + sesión propia para proveedores
- **Frontend:** Bootstrap 5 (vía CDN), HTMX (`htmx.org@1.9.10`), modo claro/oscuro con `data-bs-theme`
- **Reportes:** `pdfkit`/`wkhtmltopdf` y `XlsxWriter`/`xlwt`/`pandas` para PDF y Excel, códigos de barras con `python-barcode`
- **Servidor prod:** Waitress (`wsgi:app`)
- **Frontend (migración):** antes se usaba Tailwind v4 + Flowbite; ahora **se migra todo a Bootstrap 5** por su simplicidad. Las nuevas vistas deben usar Bootstrap 5 a través de `base.html`.

## Comandos

| Acción | Comando |
|--------|---------|
| Ejecutar en desarrollo | `run-dev.bat` (o `.\\.venv\\Scripts\\python.exe app.py`) |
| Ejecutar en producción | `run-prod.bat` (Waitress, escribe en `log/waitress.log`) |
| Compilar CSS de Tailwind | `npm run build:css` (solo si trabajas sobre Tailwind) |

- La app se crea con el factory `create_app()` (en `app/__init__.py`).
- No hay suite de tests configurada (`package.json` y `requirements.txt` no definen pruebas). No inventes un runner.

## Arquitectura de código (obligatorio)

### Modelos de base de datos — TODO en `app/models.py` (raíz)

- **TODOS los modelos viven en un único archivo:** `app/models.py` (~9900 líneas). **NO** crees carpetas `models/` dentro de los módulos.
- Se distinguen dos esquemas:
  - **Esquema `public`** → tablas del ERP externo (mapeo inicial de producción). **SOLO LECTURA.** Prohibido modificar/eliminar estas clases.
  - **Esquema `toolbox`** → tablas propias de la app. Todo modelo **nuevo** debe agregarse **al final** de `app/models.py` con:
    ```python
    __table_args__ = {"schema": "toolbox", "extend_existing": True}
    ```
- Las tablas propias se crean/actualizan automáticamente al arrancar (`create_toolbox_schema_tables()` en `app/__init__.py`), incluyendo columnas nuevas vía `ensure_toolbox_schema_columns()`.

### Blueprints (módulos)

Cada módulo vive en `app/<modulo>/` con:

```
app/<modulo>/
├── __init__.py            # instancia el Blueprint (template_folder='templates')
├── routes.py              # defines endpoints con @<modulo>_bp.route(...)
├── services/              # lógica de negocio / consultas SQLAlchemy
│   └── <modulo>_service.py
└── templates/<modulo>/    # vistas HTML en subcarpeta del módulo
```

Los Blueprints se registran en `app/__init__.py` con `app.register_blueprint(...)`.

Módulos actuales:

| Módulo | Rutas | Propósito |
|--------|-------|-----------|
| `main` | `/` | Home / dashboard público principal |
| `auth` | `/auth` | Login/logout de usuarios internos; login de modo proveedor/admin |
| `dashboard` | `/dashboard` | Panel principal autenticado (`service.py` alimenta los datos) |
| `common` | `/common` | Utilidades compartidas (ej. modal de búsqueda de usuarios) |
| `admin` | `/admin` | Gestión de menús, perfiles y usuarios |
| `inventory` | `/inventory` | Guías de transferencia, recolección, operaciones de inventario (`services/inventory_service.py`) |
| `shopping` | `/shopping` | Compras, catálogo de proveedores, listas de ofertas, panel de proveedor (`services/shopping_service.py`) |
| `reports` | `/reports` | Reportes (PDF/Excel), códigos de barras, ubicación de productos (`utils.py`, `services/reports_service.py`) |
| `document_manager` | `/documents` | Gestión de documentos/operaciones de inventario (recepción, transferencias) |
| `products_label` | `/etiquetas` | Generación de etiquetas de productos (PDF) |

`notifications/` no contiene código activo (solo restos de rutas).

## Convenciones de código

1. **Idioma del código:** código, nombres, clases, métodos y modelos en **inglés**. Los textos visibles de la UI y comentarios de negocio van en **español** (idioma del producto).
2. **Colecciones/queries:** usa la API de SQLAlchemy 2.0 (`db.session.execute(select(...))`) además del estilo clásico (`Model.query`). Ambos conviven; sigue el estilo del archivo que editas.
3. **Seguridad:** toda ruta de módulos autenticados DEBE llevar `@login_required`. La autenticación global se refuerza en `app/__init__.py` (`before_request`), que además usa sesión propia (`provider_logged_in`) para las rutas de proveedores y una lista `public_endpoints`.
4. **Plantillas:** cada HTML principal hereda de `base.html` (`{% extends "base.html" %}`) y encapsula en `{% block content %}`. La UI usa **Bootstrap 5** y componentes HTMX para actualizaciones parciales / modales.
5. **Reportes:** centraliza la generación en `app/reports/utils.py` (`render_pdf`, `render_pdf_from_html_file`, `generate_barcode`). Usa `render_template` para PDF; reutiliza helpers como `_normalize_code` / `_resolve_main_code` (normalizan códigos a MAYÚSCULAS, resuelven códigos alternos vía `ProductsCode`).
6. **No añadas comentarios innecesarios** a menos que aporten contexto de negocio.

## Estructura de datos transversal

- Los códigos de producto se normalizan con `.strip().upper()`.
- `ProductsCode` mapea códigos alternos (`other_code`) al código principal (`main_code`).
- `create_toolbox_schema_tables()` / `ensure_toolbox_schema_columns()` aplican migraciones idempotentes al arranque; si agregas columnas a tablas `toolbox`, regístralas ahí.

## Seguridad / entorno

- Variables sensibles vienen de `.env` (ignorado en git). **Nunca** comitees `.env` ni credenciales.
- `DATABASE_URL` es obligatorio (la app lanza `RuntimeError` si falta).
- `SECRET_KEY` tiene valor por defecto solo para desarrollo.
