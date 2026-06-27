# Reglas del Proyecto e Instrucciones de Arquitectura (Modelos Centralizados)

Debes seguir estrictamente estas reglas de arquitectura y nomenclatura para cada respuesta, generación de código o creación de archivos en este espacio de trabajo.

## 1. Estándar de Idioma y Nomenclatura
* **TODO el código, nombres de variables, clases, métodos, comentarios y nuevos modelos DEBEN estar en inglés.**
* Si el usuario te pide una funcionalidad en español, traduce los conceptos internamente antes de generar el código.

## 2. Regla de Oro para Modelos de Base de Datos (Centralizados)
* **TODOS los modelos de la base de datos deben vivir exclusivamente dentro del archivo `models.py` en la raíz del proyecto.** No crees carpetas `models/` dentro de los módulos.
* El archivo `models.py` contiene dos tipos de tablas bien diferenciadas por su esquema:

### A. Tablas del Sistema Externo (Esquema `public`)
* Corresponden al mapeo inicial de la aplicación en producción.
* **SON DE SOLO LECTURA.** Queda estrictamente prohibido modificar, alterar o eliminar las clases existentes que pertenecen al esquema `public`.

### B. Tablas Propias de Nuestra Aplicación (Esquema `toolbox`)
* Cada vez que el usuario te pida crear una nueva entidad, tabla o modelo (ej. Tickets, Repuestos, Inventario), debes **añadirla al final del archivo `models.py` raíz**.
* **OBLIGATORIO:** Cada nuevo modelo que agregues debe especificar explícitamente que pertenece al esquema `toolbox` usando:
  ```python
  __table_args__ = {'schema': 'toolbox'}


## 3. SKILL: Creación de Nuevos Módulos (Workflow Step-by-Step)
Cuando el usuario te pida crear un nuevo módulo (ej. "Crea el módulo de inventario" o "Crea el módulo de users"), debes ejecutar estrictamente este flujo de trabajo en orden:


### Paso 3.1: Estructurar las Carpetas del Módulo (Flask Blueprints)
Crea la siguiente estructura exacta de archivos y carpetas dentro del directorio `app/[nombre_en_ingles]/`:

```text
app/[nombre_en_ingles]/
├── __init__.py                # Inicializa el Blueprint de Flask para el módulo
├── routes.py                  # Define las rutas (@nombre_bp.route) del módulo
├── services/                  # Lógica de negocio y consultas SQLAlchemy
│   └── [nombre]_service.py    # Servicio principal del módulo
└── templates/
    └── [nombre_en_ingles]/    # Subcarpeta obligatoria para evitar colisiones en Flask
        └── [archivo].html     # Vistas HTML basadas en Bootstrap 5 e hilos de Jinja
```
* Registro del Blueprint: En el app/[nombre_en_ingles]/__init__.py debes instanciar el Blueprint configurando explícitamente el template_folder='templates' y el url_prefix. Luego, asegúrate de registrar este Blueprint en el archivo central de la aplicación (ej. app/main.py o app/__init__.py de la raíz) usando app.register_blueprint().

### Paso 3.2: Extender el Archivo de Modelos Central (`models.py`)
* Analiza qué tablas nuevas requiere el módulo.
* Genera las clases de SQLAlchemy en inglés.
* OBLIGATORIO: Añádelas al final del models.py de la raíz del proyecto.
* Asegúrate de incluir __table_args__ = {'schema': 'toolbox'} en cada una.
* Si requieren relacionarse con tablas existentes del esquema public, define los ForeignKey y relationship() directamente apuntando a esas clases en el mismo archivo.



### Paso 3.3: Generar la Lógica Base (Servicios y Rutas)
1. **Servicios (`services/`):** Diseña las funciones CRUD y de consultas (en inglés). Si el módulo requiere reportes complejos con `JOIN`s que involucren otros módulos, agrégalos en un archivo específico aquí (ej. `services/reports.py`).
2. **Rutas e Interfaz (`routes.py`):** * Define los endpoints utilizando los decoradores del Blueprint (ej. `@inventory_bp.route('/list')`).
   * **SEGURIDAD OBLIGATORIA:** Todas las rutas del módulo destinadas a usuarios autenticados deben estar protegidas con el decorador `@login_required` de Flask-Login. Asegúrate de importarlo correctamente al inicio del archivo (`from flask_login import login_required`).
   * Para mostrar la interfaz, utiliza el `render_template` nativo de Flask apuntando a la subcarpeta del módulo (ej. `render_template('nombre_en_ingles/index.html')`).
3. **Diseño de Plantillas (Bootstrap 5 & Herencia Jinja):** * **OBLIGATORIO:** Cada archivo HTML principal de un módulo DEBE heredar de la plantilla base global utilizando la sintaxis de Jinja: `{% extends "base.html" %}` al inicio del archivo.
   * El contenido específico de la vista debe ir encapsulado dentro del bloque principal: `{% block content %} ... {% endblock %}`.
   * Toda la interfaz dentro del bloque debe maquetarse utilizando exclusivamente componentes nativos de **Bootstrap 5**, asumiendo que `base.html` ya incluye los estilos y scripts globales.


