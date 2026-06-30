from __future__ import annotations

import os
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.auth import AdminUser, check_credentials, create_token
from backend.data import (
    attendance_period,
    fortnight_bounds,
    load_dashboard,
    month_bounds,
    parse_date,
    salary_summary,
)
from backend.database import (
    delete_email_config,
    list_email_configs,
    list_marks,
    replace_worker_schedule,
    save_email_config,
)
from backend.exports import (
    attendance_excel,
    attendance_pdf,
    marks_excel,
    workers_pdf,
)
from cloudinary_uploader import upload_worker_file
from supabase_backend import (
    create_store_with_qr,
    hash_password,
    update_document,
    upsert_document,
)


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "frontend" / "dist"
PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|`~]+$")

app = FastAPI(title="Panel de Asistencia API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def api_error(exc: Exception, fallback: str) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=400, detail=f"{fallback}: {exc}")


def valid_password(password: str, required: bool = False) -> None:
    password = str(password or "").strip()
    if not password and not required:
        return
    if len(password) < 3:
        raise HTTPException(
            status_code=422,
            detail="La contraseña debe tener al menos 3 caracteres.",
        )
    if not PASSWORD_PATTERN.fullmatch(password):
        raise HTTPException(
            status_code=422,
            detail="La contraseña no puede contener espacios.",
        )


def attachment(data: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno: {exc}"},
    )


@app.get("/api/health")
def health():
    return {"ok": True, "frontend_built": DIST.exists()}


@app.post("/api/auth/login")
def login(payload: dict = Body(...)):
    username = str(payload.get("username") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise HTTPException(
            status_code=422, detail="Completa el usuario y la contraseña."
        )
    if not check_credentials(username, password):
        raise HTTPException(
            status_code=401, detail="Usuario o contraseña incorrectos."
        )
    return {"token": create_token(username), "user": username}


@app.get("/api/auth/me")
def current_user(admin: AdminUser):
    return {"user": admin}


@app.get("/api/stores")
def stores(_admin: AdminUser):
    return load_dashboard(include_attendances=False)["stores"]


@app.post("/api/stores")
def create_store(_admin: AdminUser, payload: dict = Body(...)):
    required = {
        "nombre": payload.get("nombre"),
        "correo": payload.get("correo"),
        "contraseña": payload.get("password"),
    }
    missing = [label for label, value in required.items() if not str(value or "").strip()]
    if missing:
        raise HTTPException(
            status_code=422, detail="Campos requeridos: " + ", ".join(missing)
        )
    valid_password(payload.get("password"), required=True)
    store_id = str(uuid4())
    try:
        qr_token = create_store_with_qr(
            "tienda",
            "qr",
            store_id,
            {
                "correo": str(payload.get("correo") or "").strip().lower(),
                "contrasena": hash_password(payload.get("password")),
                "nombre": str(payload.get("nombre") or "").strip(),
                "telefono": str(payload.get("telefono") or "").strip(),
                "direccion": str(payload.get("direccion") or "").strip(),
                "fecha_apertura": payload.get("fecha_apertura") or None,
                "estado": True,
            },
        )
        return {"id_tienda": store_id, "qr_token": qr_token}
    except Exception as exc:
        raise api_error(exc, "No se pudo registrar la tienda")


@app.put("/api/stores/{store_id}")
def edit_store(store_id: str, _admin: AdminUser, payload: dict = Body(...)):
    if not str(payload.get("nombre") or "").strip() or not str(
        payload.get("correo") or ""
    ).strip():
        raise HTTPException(
            status_code=422, detail="Nombre y correo son obligatorios."
        )
    valid_password(payload.get("password"))
    data = {
        "correo": str(payload.get("correo") or "").strip().lower(),
        "nombre": str(payload.get("nombre") or "").strip(),
        "telefono": str(payload.get("telefono") or "").strip(),
        "direccion": str(payload.get("direccion") or "").strip(),
        "fecha_apertura": payload.get("fecha_apertura") or None,
        "estado": bool(payload.get("estado", True)),
    }
    if str(payload.get("password") or "").strip():
        data["contrasena"] = hash_password(payload["password"])
    try:
        update_document("tienda", store_id, data, key_field="id_tienda")
        return {"ok": True}
    except Exception as exc:
        raise api_error(exc, "No se pudo guardar la tienda")


@app.patch("/api/stores/{store_id}/status")
def change_store_status(
    store_id: str, _admin: AdminUser, payload: dict = Body(...)
):
    update_document(
        "tienda",
        store_id,
        {"estado": bool(payload.get("estado"))},
        key_field="id_tienda",
    )
    return {"ok": True}


@app.get("/api/workers")
def workers(_admin: AdminUser):
    dashboard = load_dashboard(include_attendances=False)
    return {
        "workers": dashboard["workers"],
        "stores": dashboard["stores"],
        "schedules": dashboard["schedules"],
    }


@app.post("/api/uploads/worker-document")
async def upload_worker_document(
    _admin: AdminUser,
    file: UploadFile,
    dni: str = Query(..., min_length=1),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".pdf"}:
        raise HTTPException(
            status_code=422, detail="Solo se admite JPG, PNG o PDF."
        )
    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(
            status_code=422, detail="El archivo supera el máximo de 12 MB."
        )
    try:
        return upload_worker_file(content, file.filename or f"dni{suffix}", dni)
    except Exception as exc:
        raise api_error(exc, "No se pudo subir el documento")


def save_worker_payload(dni: str, payload: dict, creating: bool) -> None:
    if not dni.strip() or not str(payload.get("nombre") or "").strip():
        raise HTTPException(
            status_code=422, detail="DNI y nombre son obligatorios."
        )
    if not str(payload.get("id_tienda") or "").strip():
        raise HTTPException(status_code=422, detail="Selecciona una tienda.")
    schedules = payload.get("schedules") or []
    if not schedules:
        raise HTTPException(
            status_code=422, detail="Selecciona al menos un día laborable."
        )
    valid_password(payload.get("password"), required=creating)
    if creating and not str(payload.get("foto_dni") or "").strip():
        raise HTTPException(
            status_code=422, detail="La foto o documento de DNI es obligatorio."
        )
    data = {
        "dni": dni.strip(),
        "id_tienda": payload.get("id_tienda"),
        "correo": str(payload.get("correo") or "").strip().lower(),
        "nombre": str(payload.get("nombre") or "").strip(),
        "cargo": str(payload.get("cargo") or "").strip(),
        "sueldo": float(payload.get("sueldo") or 0),
        "telefono": str(payload.get("telefono") or "").strip(),
        "csi": str(payload.get("csi") or "").strip(),
        "foto_dni": str(payload.get("foto_dni") or "").strip(),
        "estado": bool(payload.get("estado", True)),
    }
    if str(payload.get("password") or "").strip():
        data["contrasena"] = str(payload["password"]).strip()
    upsert_document("trabajador", dni, data, key_field="dni")
    replace_worker_schedule(dni, schedules)


@app.post("/api/workers")
def create_worker(_admin: AdminUser, payload: dict = Body(...)):
    dni = str(payload.get("dni") or "").strip()
    try:
        save_worker_payload(dni, payload, creating=True)
        return {"dni": dni}
    except Exception as exc:
        raise api_error(exc, "No se pudo registrar el trabajador")


@app.put("/api/workers/{dni}")
def edit_worker(dni: str, _admin: AdminUser, payload: dict = Body(...)):
    try:
        save_worker_payload(dni, payload, creating=False)
        return {"ok": True}
    except Exception as exc:
        raise api_error(exc, "No se pudo guardar el trabajador")


@app.patch("/api/workers/{dni}/status")
def change_worker_status(
    dni: str, _admin: AdminUser, payload: dict = Body(...)
):
    update_document(
        "trabajador",
        dni,
        {"estado": bool(payload.get("estado"))},
        key_field="dni",
    )
    return {"ok": True}


@app.get("/api/workers/export.pdf")
def export_workers(
    _admin: AdminUser,
    store_id: str = "",
    q: str = "",
):
    dashboard = load_dashboard(include_attendances=False)
    rows = dashboard["workers"]
    if store_id:
        rows = [row for row in rows if row["id_sede"] == store_id]
    if q:
        lowered = q.lower()
        rows = [
            row
            for row in rows
            if lowered
            in f"{row['nombre_trabajador']} {row['dni']} {row['area']}".lower()
        ]
    store = next(
        (
            row["nombre_tienda"]
            for row in dashboard["stores"]
            if row["id_tienda"] == store_id
        ),
        "Todas",
    )
    return attachment(
        workers_pdf(rows, store, q),
        "application/pdf",
        "trabajadores.pdf",
    )


def attendance_result(
    period: str,
    reference: str,
    store_id: str,
    worker_dni: str,
    q: str,
) -> tuple[dict, str]:
    selected = parse_date(reference) or date.today()
    start, end, label = (
        fortnight_bounds(selected)
        if period == "fortnight"
        else month_bounds(selected)
    )
    result = attendance_period(
        load_dashboard(),
        start,
        end,
        store_id=store_id,
        worker_dni=worker_dni,
        query=q,
    )
    result["label"] = label
    return result, label


@app.get("/api/attendance")
def attendance(
    _admin: AdminUser,
    period: str = "month",
    reference: str = "",
    store_id: str = "",
    worker_dni: str = "",
    q: str = "",
):
    result, _label = attendance_result(
        period, reference, store_id, worker_dni, q
    )
    return result


@app.patch("/api/attendance/{attendance_id}/justify")
def justify_attendance(attendance_id: str, _admin: AdminUser):
    update_document(
        "asistencia",
        attendance_id,
        {"justificado": True},
        key_field="id_asistencia",
    )
    return {"ok": True}


@app.get("/api/attendance/export.{kind}")
def export_attendance(
    kind: str,
    _admin: AdminUser,
    period: str = "month",
    reference: str = "",
    store_id: str = "",
    worker_dni: str = "",
    q: str = "",
):
    result, label = attendance_result(
        period, reference, store_id, worker_dni, q
    )
    metadata = {**result, "label": label}
    if kind == "xlsx":
        return attachment(
            attendance_excel(result["rows"], metadata),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "reporte_asistencias.xlsx",
        )
    if kind == "pdf":
        return attachment(
            attendance_pdf(result["rows"], result["workers"], metadata),
            "application/pdf",
            "reporte_asistencias.pdf",
        )
    raise HTTPException(status_code=404, detail="Formato no disponible.")


@app.get("/api/salaries/{dni}")
def salary(
    dni: str,
    _admin: AdminUser,
    month: str = "",
    reference_days: int = 26,
    hours_per_day: float = 8,
    tolerance_minutes: int = 0,
    penalty_mode: str = "hour",
    fixed_penalty: float = 0,
):
    selected = parse_date(month) or date.today().replace(day=1)
    try:
        return salary_summary(
            load_dashboard(),
            dni,
            selected.replace(day=1),
            reference_days,
            hours_per_day,
            tolerance_minutes,
            penalty_mode,
            fixed_penalty,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/email-configs")
def email_configs(_admin: AdminUser):
    return jsonable_encoder(list_email_configs())


@app.post("/api/email-configs")
def create_email_config(_admin: AdminUser, payload: dict = Body(...)):
    if not str(payload.get("correo_destino") or "").strip() or not str(
        payload.get("hora_envio") or ""
    ).strip():
        raise HTTPException(
            status_code=422, detail="Correo y hora de envío son obligatorios."
        )
    return {"id_config": save_email_config(payload)}


@app.put("/api/email-configs/{config_id}")
def edit_email_config(
    config_id: str, _admin: AdminUser, payload: dict = Body(...)
):
    save_email_config(payload, config_id)
    return {"ok": True}


@app.delete("/api/email-configs/{config_id}")
def remove_email_config(config_id: str, _admin: AdminUser):
    delete_email_config(config_id)
    return {"ok": True}


@app.get("/api/marks")
def marks(
    _admin: AdminUser,
    start: str,
    end: str,
    store_id: str = "",
    worker_dni: str = "",
):
    start_date = parse_date(start)
    end_date = parse_date(end)
    if not start_date or not end_date or start_date > end_date:
        raise HTTPException(status_code=422, detail="Rango de fechas no válido.")
    return jsonable_encoder(
        list_marks(start_date, end_date, store_id, worker_dni)
    )


@app.get("/api/marks/export.xlsx")
def export_marks(
    _admin: AdminUser,
    start: str,
    end: str,
    store_id: str = "",
    worker_dni: str = "",
):
    start_date = parse_date(start)
    end_date = parse_date(end)
    if not start_date or not end_date:
        raise HTTPException(status_code=422, detail="Fechas no válidas.")
    rows = list_marks(start_date, end_date, store_id, worker_dni)
    return attachment(
        marks_excel(rows),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "marcas_asistencia.xlsx",
    )


@app.get("/media/{filename}")
def media(filename: str):
    allowed = {
        "fondo.png",
        "fondoo.png",
        "fondologin.mp4",
        "fondologiin.mp4",
        "Sidebarfondo.mp4",
    }
    if filename not in allowed:
        raise HTTPException(status_code=404)
    path = ROOT / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def frontend(full_path: str):
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Frontend no compilado. Ejecuta `npm run build` en `frontend`."
        },
    )
