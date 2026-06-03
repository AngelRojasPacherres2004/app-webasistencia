from io import BytesIO
from pathlib import Path
from uuid import uuid4
import hashlib
import time as time_module
import re

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        import toml as _toml
        class _TomlFallback:
            @staticmethod
            def loads(content):
                return _toml.loads(content)
        tomllib = _TomlFallback()

import requests
import streamlit as st


CLOUDINARY_SECRET_PATHS = (
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/secret.toml"),
)


def _hard_clean(val):
    """Elimina absolutamente todo carácter que no sea ASCII imprimible."""
    if not val:
        return ""
    s = str(val)
    # Quitar BOM, comillas, espacios, saltos de línea, tabs, caracteres de control
    s = s.strip()
    s = s.strip('"').strip("'").strip()
    s = re.sub(r'[\x00-\x1f\x7f-\xff\s]', '', s)
    return s


def get_cloudinary_config():
    try:
        if "cloudinary" in st.secrets:
            return _build_config(st.secrets["cloudinary"])
    except Exception:
        pass

    for secret_path in CLOUDINARY_SECRET_PATHS:
        config = _load_file(secret_path)
        if config:
            return _build_config(config)

    raise RuntimeError(
        "Faltan credenciales de Cloudinary. Coloca `[cloudinary]` en "
        "`.streamlit/secrets.toml` con `cloud_name`, `api_key` y `api_secret`."
    )


def _build_config(raw):
    cloud_name = _hard_clean(raw.get("cloud_name", ""))
    api_key    = _hard_clean(raw.get("api_key",    ""))
    api_secret = _hard_clean(raw.get("api_secret", ""))
    folder     = str(raw.get("folder", "trabajadores_dni")).strip().strip("/")

    for field, val in [("cloud_name", cloud_name), ("api_key", api_key), ("api_secret", api_secret)]:
        if not val:
            raise RuntimeError(f"Credencial Cloudinary faltante o vacía: {field}")

    return {
        "cloud_name": cloud_name,
        "api_key":    api_key,
        "api_secret": api_secret,
        "folder":     folder,
    }


def _load_file(path):
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8-sig").strip()
    try:
        parsed = tomllib.loads(raw)
        if "cloudinary" in parsed:
            return parsed["cloudinary"]
    except Exception:
        pass
    section = _extract_section(raw, "cloudinary")
    if not section:
        return None
    try:
        return tomllib.loads(section).get("cloudinary")
    except Exception:
        return None


def _extract_section(raw, section_name):
    lines, result, collecting = raw.splitlines(), [], False
    header = f"[{section_name}]"
    for line in lines:
        stripped = line.strip()
        if stripped == header:
            collecting = True
        elif collecting and stripped.startswith("[") and stripped.endswith("]"):
            break
        if collecting:
            result.append(line)
    return "\n".join(result).strip()


def _build_signature(params: dict, api_secret: str) -> str:
    """
    Firma oficial Cloudinary:
    Ordenar alfabéticamente los parámetros (excluir file, api_key,
    resource_type, cloud_name), concatenar como k=v&k=v, añadir api_secret
    sin separador, SHA-1.
    """
    excluded = {"file", "api_key", "resource_type", "cloud_name"}
    pairs = sorted(
        f"{k}={v}"
        for k, v in params.items()
        if k not in excluded and v not in (None, "")
    )
    to_sign = "&".join(pairs) + api_secret
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()


def upload_worker_file(uploaded_file, worker_id):
    config = get_cloudinary_config()

    cloud_name = config["cloud_name"]
    api_key    = config["api_key"]
    api_secret = config["api_secret"]
    folder     = config["folder"]

    public_id = f"dni_{worker_id}_{uuid4().hex[:8]}"
    timestamp  = str(int(time_module.time()))

    sign_params = {
        "folder":    folder,
        "public_id": public_id,
        "timestamp": timestamp,
    }

    signature = _build_signature(sign_params, api_secret)

    # --- DEBUG: muestra en pantalla el string firmado y la firma ---
    # Descomenta estas líneas si vuelve a fallar para ver qué está pasando:
    # st.info(f"String to sign: folder={folder}&public_id={public_id}&timestamp={timestamp}{api_secret[:4]}***")
    # st.info(f"Signature: {signature}")
    # st.info(f"api_key len={len(api_key)}, api_secret len={len(api_secret)}")

    file_bytes = uploaded_file.getvalue()
    file_name  = uploaded_file.name

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload"

    response = requests.post(
        upload_url,
        data={
            "api_key":   api_key,
            "timestamp": timestamp,
            "signature": signature,
            "folder":    folder,
            "public_id": public_id,
        },
        files={"file": (file_name, BytesIO(file_bytes))},
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Cloudinary error {response.status_code}: {response.text[:600]}"
        )

    result = response.json()
    return {
        "asset_id":      result.get("asset_id", ""),
        "public_id":     result.get("public_id", ""),
        "secure_url":    result.get("secure_url", ""),
        "resource_type": result.get("resource_type", ""),
        "name":          file_name,
    }