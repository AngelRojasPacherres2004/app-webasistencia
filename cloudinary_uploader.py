from io import BytesIO
from pathlib import Path
from uuid import uuid4
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

import cloudinary
import cloudinary.uploader
import streamlit as st


CLOUDINARY_SECRET_PATHS = (
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/secret.toml"),
)


def get_cloudinary_config():
    try:
        if "cloudinary" in st.secrets:
            cloudinary_config = st.secrets["cloudinary"]
            return normalize_cloudinary_config(cloudinary_config)
    except Exception:
        pass

    for secret_path in CLOUDINARY_SECRET_PATHS:
        cloudinary_config = load_cloudinary_config_file(secret_path)
        if cloudinary_config:
            return normalize_cloudinary_config(cloudinary_config)

    raise RuntimeError(
        "Faltan credenciales de Cloudinary. Coloca `[cloudinary]` en "
        "`.streamlit/secrets.toml` con `cloud_name`, `api_key` y `api_secret`."
    )


def normalize_cloudinary_config(cloudinary_config):
    def _clean(val):
        # Elimina espacios y comillas accidentales (común al copiar/pegar)
        if not val:
            return ""
        return str(val).strip().strip('"').strip("'").strip()

    return {
        "cloud_name": _clean(cloudinary_config.get("cloud_name")),
        "api_key": _clean(cloudinary_config.get("api_key")),
        "api_secret": _clean(cloudinary_config.get("api_secret")),
        "folder": _clean(cloudinary_config.get("folder", "trabajadores_dni")),
    }


def load_cloudinary_config_file(path):
    if not path.exists():
        return None

    raw_content = path.read_text(encoding="utf-8-sig").strip()
    try:
        parsed = tomllib.loads(raw_content)
        if "cloudinary" in parsed:
            return parsed["cloudinary"]
    except tomllib.TOMLDecodeError:
        pass

    section = extract_toml_section(raw_content, "cloudinary")
    if not section:
        return None
    try:
        parsed = tomllib.loads(section)
    except tomllib.TOMLDecodeError:
        return None
    return parsed.get("cloudinary")


def extract_toml_section(raw_content, section_name):
    lines = raw_content.splitlines()
    section_lines = []
    collecting = False
    header = f"[{section_name}]"

    for line in lines:
        stripped = line.strip()
        if stripped == header:
            collecting = True
        elif collecting and stripped.startswith("[") and stripped.endswith("]"):
            break

        if collecting:
            section_lines.append(line)

    return "\n".join(section_lines).strip()


@st.cache_resource(show_spinner=False, ttl=3600)
def configure_cloudinary():
    config = get_cloudinary_config()
    required_fields = ("cloud_name", "api_key", "api_secret")
    missing = [field for field in required_fields if not config[field]]
    if missing:
        raise RuntimeError("Credenciales Cloudinary incompletas: " + ", ".join(missing))

    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        secure=True,
    )
    return config


def upload_worker_file(uploaded_file, worker_id):
    config = configure_cloudinary()
    # Normalizamos el nombre del archivo eliminando espacios y caracteres raros
    original_name = "".join(c for c in Path(uploaded_file.name).stem if c.isalnum() or c in ("_", "-"))
    public_id = f"{worker_id}_{uuid4().hex}_{original_name}"
    file_buffer = BytesIO(uploaded_file.getvalue())
    file_buffer.name = uploaded_file.name

    result = cloudinary.uploader.upload(
        file_buffer,
        folder=config.get("folder") or "trabajadores_dni",
        public_id=public_id,
        resource_type="auto",
        # Quitamos overwrite=False para simplificar la firma (por defecto es False para archivos nuevos)
    )

    return {
        "asset_id": result.get("asset_id", ""),
        "public_id": result.get("public_id", ""),
        "secure_url": result.get("secure_url", ""),
        "resource_type": result.get("resource_type", ""),
        "name": uploaded_file.name,
    }