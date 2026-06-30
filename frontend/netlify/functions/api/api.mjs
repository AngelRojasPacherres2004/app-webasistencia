import { createHash, randomBytes, randomUUID } from "node:crypto";
import {
  ApiError, attendancePeriod, checkCredentials, createStoreRecord, createToken,
  deleteEmailConfig, isoDate, justifyAttendance, listEmailConfigs, listMarks,
  loadDashboard, salarySummary, saveEmailConfig, saveWorker, setStatus,
  updateStoreRecord, verifyToken,
} from "./lib.mjs";
import {
  attendanceExcel, attendancePdf, marksExcel, workersPdf,
} from "./reports.mjs";

const json = (value, status = 200) =>
  Response.json(value, { status, headers: { "cache-control": "no-store" } });

const attachment = (data, type, filename) =>
  new Response(data, {
    headers: {
      "content-type": type,
      "content-disposition": `attachment; filename="${filename}"`,
      "cache-control": "no-store",
    },
  });

const body = async (request) => {
  try {
    return await request.json();
  } catch {
    throw new ApiError(422, "El contenido enviado no es válido.");
  }
};

const requiredPassword = (password, required = false) => {
  const value = String(password || "").trim();
  if (!value && !required) return;
  if (value.length < 3) throw new ApiError(422, "La contraseña debe tener al menos 3 caracteres.");
  if (/\s/.test(value)) throw new ApiError(422, "La contraseña no puede contener espacios.");
};

const apiFilters = (url) => ({
  period: url.searchParams.get("period") || "month",
  reference: url.searchParams.get("reference") || "",
  store_id: url.searchParams.get("store_id") || "",
  worker_dni: url.searchParams.get("worker_dni") || "",
  q: url.searchParams.get("q") || "",
});

async function attendanceResult(url) {
  return attendancePeriod(await loadDashboard(true), apiFilters(url));
}

async function uploadDocument(request, url) {
  const dni = url.searchParams.get("dni")?.trim();
  if (!dni) throw new ApiError(422, "Indica el DNI del trabajador.");
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) throw new ApiError(422, "Selecciona un archivo.");
  const extension = file.name.toLowerCase().split(".").pop();
  if (!["jpg", "jpeg", "png", "pdf"].includes(extension)) {
    throw new ApiError(422, "Solo se admite JPG, PNG o PDF.");
  }
  if (file.size > 4 * 1024 * 1024) {
    throw new ApiError(422, "En Netlify el documento no puede superar 4 MB.");
  }
  const cloudName = process.env.CLOUDINARY_CLOUD_NAME?.trim();
  const apiKey = process.env.CLOUDINARY_API_KEY?.trim();
  const apiSecret = process.env.CLOUDINARY_API_SECRET?.trim();
  const folder = process.env.CLOUDINARY_FOLDER?.trim() || "trabajadores_dni";
  if (!cloudName || !apiKey || !apiSecret) throw new Error("Faltan las credenciales de Cloudinary.");
  const publicId = `dni_${dni}_${randomBytes(4).toString("hex")}`;
  const timestamp = String(Math.floor(Date.now() / 1000));
  const signature = createHash("sha1")
    .update(`folder=${folder}&public_id=${publicId}&timestamp=${timestamp}${apiSecret}`)
    .digest("hex");
  const upload = new FormData();
  upload.set("file", file, file.name);
  upload.set("api_key", apiKey);
  upload.set("timestamp", timestamp);
  upload.set("signature", signature);
  upload.set("folder", folder);
  upload.set("public_id", publicId);
  const response = await fetch(`https://api.cloudinary.com/v1_1/${cloudName}/auto/upload`, {
    method: "POST", body: upload,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || "Cloudinary rechazó el archivo.");
  return {
    asset_id: result.asset_id || "", public_id: result.public_id || "",
    secure_url: result.secure_url || "", resource_type: result.resource_type || "",
    name: file.name,
  };
}

async function route(request) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method;

  if (path === "/api/health" && method === "GET") {
    return json({ ok: true, runtime: "netlify-functions" });
  }

  if (path === "/api/auth/login" && method === "POST") {
    const payload = await body(request);
    const username = String(payload.username || "").trim().toLowerCase();
    const password = String(payload.password || "");
    if (!username || !password) throw new ApiError(422, "Completa el usuario y la contraseña.");
    if (!(await checkCredentials(username, password))) throw new ApiError(401, "Usuario o contraseña incorrectos.");
    return json({ token: createToken(username), user: username });
  }

  const admin = verifyToken(request);
  if (!admin) throw new ApiError(401, "La sesión venció. Inicia sesión nuevamente.");
  if (path === "/api/auth/me" && method === "GET") return json({ user: admin });

  if (path === "/api/stores" && method === "GET") {
    return json((await loadDashboard(false)).stores);
  }

  if (path === "/api/stores" && method === "POST") {
    const payload = await body(request);
    if (!String(payload.nombre || "").trim() || !String(payload.correo || "").trim() || !String(payload.password || "").trim()) {
      throw new ApiError(422, "Nombre, correo y contraseña son obligatorios.");
    }
    requiredPassword(payload.password, true);
    const id = randomUUID();
    const token = randomBytes(16).toString("hex");
    await createStoreRecord(id, token, {
      correo: String(payload.correo).trim().toLowerCase(),
      contrasena: String(payload.password),
      nombre: String(payload.nombre).trim(),
      telefono: String(payload.telefono || "").trim(),
      direccion: String(payload.direccion || "").trim(),
      fecha_apertura: payload.fecha_apertura || null,
    });
    return json({ id_tienda: id, qr_token: token });
  }

  const storeMatch = path.match(/^\/api\/stores\/([^/]+)$/);
  const storeStatus = path.match(/^\/api\/stores\/([^/]+)\/status$/);
  if (storeMatch && method === "PUT") {
    const payload = await body(request);
    if (!String(payload.nombre || "").trim() || !String(payload.correo || "").trim()) {
      throw new ApiError(422, "Nombre y correo son obligatorios.");
    }
    requiredPassword(payload.password);
    const data = {
      correo: String(payload.correo).trim().toLowerCase(),
      nombre: String(payload.nombre).trim(),
      telefono: String(payload.telefono || "").trim(),
      direccion: String(payload.direccion || "").trim(),
      fecha_apertura: payload.fecha_apertura || null,
      estado: payload.estado ?? true,
    };
    if (String(payload.password || "").trim()) data.contrasena = String(payload.password).trim();
    await updateStoreRecord(decodeURIComponent(storeMatch[1]), data);
    return json({ ok: true });
  }
  if (storeStatus && method === "PATCH") {
    const payload = await body(request);
    await setStatus("tienda", "id_tienda", decodeURIComponent(storeStatus[1]), Boolean(payload.estado));
    return json({ ok: true });
  }

  if (path === "/api/workers" && method === "GET") {
    const dashboard = await loadDashboard(false);
    return json({ workers: dashboard.workers, stores: dashboard.stores, schedules: dashboard.schedules });
  }
  if (path === "/api/uploads/worker-document" && method === "POST") {
    return json(await uploadDocument(request, url));
  }
  if (path === "/api/workers" && method === "POST") {
    const payload = await body(request);
    const dni = String(payload.dni || "").trim();
    requiredPassword(payload.password, true);
    await saveWorker(dni, payload, true);
    return json({ dni });
  }
  const workerMatch = path.match(/^\/api\/workers\/([^/.]+)$/);
  const workerStatus = path.match(/^\/api\/workers\/([^/]+)\/status$/);
  if (workerMatch && method === "PUT") {
    const payload = await body(request);
    requiredPassword(payload.password);
    await saveWorker(decodeURIComponent(workerMatch[1]), payload, false);
    return json({ ok: true });
  }
  if (workerStatus && method === "PATCH") {
    const payload = await body(request);
    await setStatus("trabajador", "dni", decodeURIComponent(workerStatus[1]), Boolean(payload.estado));
    return json({ ok: true });
  }
  if (path === "/api/workers/export.pdf" && method === "GET") {
    const dashboard = await loadDashboard(false);
    const storeId = url.searchParams.get("store_id") || "";
    const query = (url.searchParams.get("q") || "").toLowerCase();
    const rows = dashboard.workers.filter((worker) =>
      (!storeId || worker.id_sede === storeId) &&
      (!query || `${worker.nombre_trabajador} ${worker.dni} ${worker.area}`.toLowerCase().includes(query)),
    );
    const store = dashboard.stores.find((item) => item.id_tienda === storeId)?.nombre_tienda || "Todas";
    return attachment(await workersPdf(rows, store, query), "application/pdf", "trabajadores.pdf");
  }

  if (path === "/api/attendance" && method === "GET") return json(await attendanceResult(url));
  const justify = path.match(/^\/api\/attendance\/([^/]+)\/justify$/);
  if (justify && method === "PATCH") {
    await justifyAttendance(decodeURIComponent(justify[1]));
    return json({ ok: true });
  }
  const exportAttendance = path.match(/^\/api\/attendance\/export\.(xlsx|pdf)$/);
  if (exportAttendance && method === "GET") {
    const result = await attendanceResult(url);
    const slug = result.label.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    const scope = !url.searchParams.get("store_id") && !url.searchParams.get("worker_dni") ? "todas" : "filtradas";
    const filename = `asistencias_${slug}_${scope}`;
    if (exportAttendance[1] === "xlsx") {
      return attachment(await attendanceExcel(result.rows, result), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", `${filename}.xlsx`);
    }
    return attachment(await attendancePdf(result.rows, result.workers, result), "application/pdf", `${filename}.pdf`);
  }

  const salary = path.match(/^\/api\/salaries\/([^/]+)$/);
  if (salary && method === "GET") {
    return json(salarySummary(await loadDashboard(true), decodeURIComponent(salary[1]), Object.fromEntries(url.searchParams)));
  }

  if (path === "/api/email-configs" && method === "GET") {
    return json(await listEmailConfigs());
  }
  if (path === "/api/email-configs" && method === "POST") {
    const payload = await body(request);
    if (!String(payload.correo_destino || "").trim() || !String(payload.hora_envio || "").trim()) throw new ApiError(422, "Correo y hora de envío son obligatorios.");
    const id = randomUUID();
    await saveEmailConfig(payload, id);
    return json({ id_config: id });
  }
  const emailMatch = path.match(/^\/api\/email-configs\/([^/]+)$/);
  if (emailMatch && method === "PUT") {
    await saveEmailConfig(await body(request), decodeURIComponent(emailMatch[1]));
    return json({ ok: true });
  }
  if (emailMatch && method === "DELETE") {
    await deleteEmailConfig(decodeURIComponent(emailMatch[1]));
    return json({ ok: true });
  }

  if ((path === "/api/marks" || path === "/api/marks/export.xlsx") && method === "GET") {
    const start = url.searchParams.get("start") || "";
    const end = url.searchParams.get("end") || "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || start > end) throw new ApiError(422, "Rango de fechas no válido.");
    const rows = await listMarks(start, end, url.searchParams.get("store_id") || "", url.searchParams.get("worker_dni") || "");
    if (path.endsWith(".xlsx")) {
      return attachment(await marksExcel(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "marcas_asistencia.xlsx");
    }
    return json(rows);
  }

  throw new ApiError(404, "Ruta no encontrada.");
}

export default async (request) => {
  try {
    return await route(request);
  } catch (error) {
    console.error(error);
    return json({ detail: error.message || "Error interno." }, error.status || 500);
  }
};

export const config = {
  path: "/api/*",
};
