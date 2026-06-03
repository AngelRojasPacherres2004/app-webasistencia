from io import BytesIO
from pathlib import Path
from uuid import uuid4
import hashlib
import time as time_module

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


def get_cloudinary_config():
    try:
        if "cloudinary" in st.secrets:
            return normalize_cloudinary_config(st.secrets["cloudinary"])
    except Exception:
        pass

    for secret_path in CLOUDINARY_SECRET_PATHS:
        config = load_cloudinary_config_file(secret_path)
        if config:
            return normalize_cloudinary_config(config)

    raise RuntimeError(
        "Faltan credenciales de Cloudinary. Coloca `[cloudinary]` en "
        "`.streamlit/secrets.toml` con `cloud_name`, `api_key` y `api_secret`."
    )


def normalize_cloudinary_config(cloudinary_config):
    import re

    def _clean(val, strip_whitespace=False):
        if not val:
            return ""
        s = str(val).strip().strip('"').strip("'").strip()
        if strip_whitespace:
            s = re.sub(r'\s+', '', s)
        return s

    return {
        "cloud_name": _clean(cloudinary_config.get("cloud_name"), True),
        "api_key":    _clean(cloudinary_config.get("api_key"),    True),
        "api_secret": _clean(cloudinary_config.get("api_secret"), True),
        "folder":     _clean(cloudinary_config.get("folder", "trabajadores_dni"), False),
    }


def load_cloudinary_config_file(path):
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8-sig").strip()
    try:
        parsed = tomllib.loads(raw)
        if "cloudinary" in parsed:
            return parsed["cloudinary"]
    except Exception:
        pass
    section = _extract_toml_section(raw, "cloudinary")
    if not section:
        return None
    try:
        return tomllib.loads(section).get("cloudinary")
    except Exception:
        return None


def _extract_toml_section(raw, section_name):
    lines = raw.splitlines()
    result, collecting = [], False
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
    Genera la firma SHA-1 de Cloudinary.
    Regla oficial: ordenar los parámetros alfabéticamente (excepto 'file',
    'api_key', 'resource_type' y 'cloud_name'), concatenar como
    key=value&key=value y añadir api_secret al final sin separador.
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

    for field in ("cloud_name", "api_key", "api_secret"):
        if not config[field]:
            raise RuntimeError(f"Credencial Cloudinary faltante: {field}")

    cloud_name = config["cloud_name"]
    api_key    = config["api_key"]
    api_secret = config["api_secret"]
    folder     = config["folder"].strip("/")

    public_id = f"dni_{worker_id}_{uuid4().hex[:8]}"
    timestamp = str(int(time_module.time()))

    # Parámetros que van en la firma (exactamente los que se envían al API,
    # sin 'file', 'api_key', 'resource_type', 'cloud_name')
    sign_params = {
        "folder":    folder,
        "public_id": public_id,
        "timestamp": timestamp,
    }

    signature = _build_signature(sign_params, api_secret)

    file_bytes = uploaded_file.getvalue()
    file_name  = uploaded_file.name

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload"

    response = requests.post(
        upload_url,
        data={
            "api_key":    api_key,
            "timestamp":  timestamp,
            "signature":  signature,
            "folder":     folder,
            "public_id":  public_id,
        },
        files={"file": (file_name, BytesIO(file_bytes))},
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Cloudinary error {response.status_code}: {response.text[:400]}"
        )

    result = response.json()
    return {
        "asset_id":      result.get("asset_id", ""),
        "public_id":     result.get("public_id", ""),
        "secure_url":    result.get("secure_url", ""),
        "resource_type": result.get("resource_type", ""),
        "name":          file_name,
    }