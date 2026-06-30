const TOKEN_KEY = "attendance_admin_token";

export const session = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    if (response.status === 401) {
      session.clear();
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(payload?.detail || payload || "No se pudo completar la operación.");
  }
  return payload;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = session.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers });
  return parseResponse(response);
}

export const get = (path) => api(path);
export const post = (path, body) =>
  api(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) });
export const put = (path, body) =>
  api(path, { method: "PUT", body: JSON.stringify(body) });
export const patch = (path, body = {}) =>
  api(path, { method: "PATCH", body: JSON.stringify(body) });
export const remove = (path) => api(path, { method: "DELETE" });

export async function download(path, filename) {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${session.get()}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "No se pudo generar el archivo.");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const serverFilename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename || serverFilename || "descarga";
  anchor.click();
  URL.revokeObjectURL(url);
}

export const query = (values) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== "" && value !== undefined && value !== null) params.set(key, value);
  });
  return params.toString();
};
