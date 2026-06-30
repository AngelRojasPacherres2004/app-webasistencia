# Panel Admin · Asistencia

Aplicación web migrada a React + FastAPI. React mantiene la navegación y los
formularios en el navegador, por lo que una interacción ya no vuelve a ejecutar
toda la interfaz como ocurría con Streamlit. FastAPI conserva las credenciales,
consultas PostgreSQL, archivos y reportes en el servidor.

## Funcionalidades

- Inicio de sesión administrativo con sesión firmada.
- Resumen de asistencias, tardanzas y justificaciones.
- Exportación de asistencias a Excel y PDF.
- Cálculo de salarios por faltas, tardanzas y días extra.
- Gestión de tiendas y generación de QR al registrarlas.
- Gestión de trabajadores, horarios y documentos en Cloudinary.
- Configuración de alertas automáticas por correo.
- Consulta y exportación del historial de marcas.

## Configuración

1. Copia `.env.example` como `.env`.
2. Define `DATABASE_URL` y `AUTH_SECRET`.
3. Opcionalmente configura el usuario de emergencia con `ADMIN_USERNAME` y
   `ADMIN_PASSWORD`.
4. Para cargar documentos, define las variables `CLOUDINARY_*`. También se
   admite el archivo local `.secrets.toml` migrado desde la versión anterior.

## Desarrollo

En una terminal, inicia la API:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

En otra terminal, inicia React:

```powershell
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173`.

## Producción

Compila React y sirve todo desde FastAPI:

```powershell
cd frontend
npm install
npm run build
cd ..
uvicorn app:app --host 0.0.0.0 --port 8000
```

La aplicación completa queda disponible en `http://localhost:8000`.
