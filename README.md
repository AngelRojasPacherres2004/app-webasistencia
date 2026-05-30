# Panel Admin - Asistencia

Aplicacion Streamlit conectada directo a PostgreSQL de Supabase usando `DATABASE_URL` para crear y consultar datos en tus tablas reales: `tienda`, `qr`, `trabajador`, `horario_trabajador`, `asistencia` y `administrador`.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Credenciales

La app solo necesita que pegues tu `DATABASE_URL` en `.env`:

```env
DATABASE_URL=postgresql://postgres:TU_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres
```

Opcionalmente puedes guardar un usuario de emergencia para el login en la misma ruta:

```toml
[admin_auth]
username = "admin"
password = "admin123"
```

Para subir archivos de trabajadores a Cloudinary, crea una cuenta en Cloudinary y copia tus credenciales desde el dashboard.

Coloca estas credenciales en `.streamlit/secrets.toml`:

```toml
[cloudinary]
cloud_name = "TU_CLOUD_NAME"
api_key = "TU_API_KEY"
api_secret = "TU_API_SECRET"
folder = "trabajadores_dni"
```

## Coleccion tienda
Cada tienda se guarda en `tienda` y el QR activo se crea en `qr` con el `token` unico. La app usa `id_tienda` como UUID y guarda la contrasena como hash bcrypt en `contrasena`.

## Coleccion trabajador

Cada trabajador se guarda en `trabajador` y su horario por dia se guarda en `horario_trabajador`. La app usa `dni` como clave del trabajador y `id_tienda` para enlazarlo con su tienda.

En el resumen se muestran los registros leidos desde PostgreSQL para `tienda`, `trabajador` y `asistencia`.

## Coleccion asistencia

Cada asistencia se guarda en `asistencia` con `dni_trabajador`, `fecha` y las marcas `timestamptz` reales (`horario_entrada`, `horario_inicio_receso`, `horario_fin_receso`, `horario_salida`).
# asistencia-web
# app-webasistencia
