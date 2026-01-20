# run.py
from app import create_app
import os
from dotenv import load_dotenv

# Cargamos las variables de entorno desde el archivo .env
load_dotenv()

# Creamos la instancia de la aplicación
app = create_app()

if __name__ == '__main__':
    # Obtenemos el puerto de las variables de entorno o usamos el 5000 por defecto
    port = int(os.getenv('PORT', 5000))
    
    # Arrancamos la aplicación
    # En desarrollo usamos debug=True para ver cambios en tiempo real
    app.run(host='0.0.0.0', port=port, debug=True)
