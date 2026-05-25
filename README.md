# Panel Admin - Asistencia

Aplicacion Streamlit conectada a Firebase para crear documentos en las colecciones `tienda`, `qr_activos`, `trabajador` y `asistencia`.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Credenciales

La app lee el service account desde cualquiera de estos archivos:

```text
.streamlit/secrets.toml
.streamlit/secret.toml
.streamlit/secrets,toml
.streamlit/firebase-service-account.json
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

Cada documento se guarda en:

```text
tienda/{id_tienda}
```

Campos:

```text
id_tienda
correo
password
contrasena
nombre_tienda
id_sede
nombre_sede
direccion
```

Al crear una tienda tambien se genera automaticamente su QR activo en:

```text
qr_activos/{id_tienda}
```

Campos:

```text
id_tienda
nombre_tienda
id_sede
nombre_sede
direccion
token
activo
fecha_creada
```

El QR dinamico debe usar el campo `token`; cada tienda nueva recibe un token unico.

## Coleccion trabajador

Cada documento se guarda en:

```text
trabajador/{id_trabajador}
```

Campos:

```text
id_trabajador
correo
password
contrasena
area
dni
foto_dni
foto_dni_public_id
foto_dni_asset_id
foto_dni_resource_type
foto_dni_nombre_archivo
id_sede
nombre_sede
nombre_trabajador
cuenta_bancaria
fecha_creada
horario
```

Al crear el trabajador se eligen los dias que tendran horario. El campo `horario` guarda solo los dias seleccionados:

```text
horario.lunes.hora_inicio
horario.lunes.inicio_receso
horario.lunes.final_receso
horario.lunes.hora_final
```

La misma estructura se repite para:

```text
martes
miercoles
jueves
viernes
sabado
```

En el resumen se muestran los documentos leidos desde Firebase para `tienda`, `trabajador` y `asistencia`. Las contraseñas no se muestran en la tabla; solo aparece si el registro tiene contraseña.

## Coleccion asistencia

Cada documento se guarda en:

```text
asistencia/{id_trabajador}_{fecha}_{id_tienda}
```

Campos:

```text
nombre_tienda
id_tienda
id_trabajador
fecha
hora_inicio
inicio_receso
final_receso
hora_finalhas
ultima_marca
id_sede
nombre_sede
dni
```
# asistencia-web
# app-webasistencia
