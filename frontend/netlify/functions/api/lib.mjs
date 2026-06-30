import { createClient } from "@supabase/supabase-js";
import bcrypt from "bcryptjs";
import { createHmac, timingSafeEqual } from "node:crypto";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];
export const WEEKDAYS = [
  "domingo", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
];

let client;
export function db() {
  const url = process.env.SUPABASE_URL?.trim();
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim();
  if (!url || !key) {
    throw new Error("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en Netlify.");
  }
  if (key.startsWith("sb_publishable_")) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY contiene una clave pública. Usa la clave secreta sb_secret_... de Supabase.",
    );
  }
  client ||= createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}

export function check(result, fallback = "Error de base de datos") {
  if (result.error) throw new Error(`${fallback}: ${result.error.message}`);
  return result.data ?? [];
}

const bool = (value) =>
  value === true || ["1", "true", "t", "yes", "y", "si", "sí"].includes(
    String(value ?? "").trim().toLowerCase(),
  );

export function formatTime(value) {
  if (!value) return "";
  const text = String(value).trim();
  if (text.includes("T")) {
    const parsed = new Date(text);
    if (!Number.isNaN(parsed.valueOf())) {
      return new Intl.DateTimeFormat("en-GB", {
        timeZone: "America/Lima", hour: "2-digit", minute: "2-digit",
        hour12: false,
      }).format(parsed);
    }
  }
  return text.includes(" ") ? text.split(" ").at(-1).slice(0, 5) : text.slice(0, 5);
}

export function timeMinutes(value) {
  const [hour, minute] = formatTime(value).split(":").map(Number);
  return Number.isFinite(hour) && Number.isFinite(minute) ? hour * 60 + minute : null;
}

const localDate = (value) => {
  const text = String(value ?? "").slice(0, 10);
  const [year, month, day] = text.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day, 12) : null;
};

export const isoDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export function periodBounds(reference, period) {
  const selected = localDate(reference) || new Date();
  const year = selected.getFullYear();
  const month = selected.getMonth();
  if (period === "fortnight") {
    const first = selected.getDate() <= 15;
    const start = new Date(year, month, first ? 1 : 16, 12);
    const end = new Date(year, month + (first ? 0 : 1), first ? 15 : 0, 12);
    return {
      start, end,
      label: `${MONTHS[month]} ${year} · Quincena ${first ? 1 : 2}`,
    };
  }
  return {
    start: new Date(year, month, 1, 12),
    end: new Date(year, month + 1, 0, 12),
    label: `${MONTHS[month]} ${year}`,
  };
}

function serializeStore(row) {
  return {
    id_tienda: String(row.id_tienda ?? ""),
    correo: row.correo || "",
    tiene_contrasena: Boolean(row.contrasena),
    nombre_tienda: row.nombre || "",
    direccion: row.direccion || "",
    telefono: row.telefono || "",
    fecha_apertura: String(row.fecha_apertura || "").slice(0, 10),
    estado: bool(row.estado ?? true),
  };
}

function serializeWorker(row, stores, scheduleMap) {
  const dni = String(row.dni ?? "");
  const store = stores.get(String(row.id_tienda ?? "")) || {};
  const schedule = scheduleMap[dni] || {};
  return {
    dni,
    id_trabajador: dni,
    id_sede: String(row.id_tienda ?? ""),
    nombre_sede: store.nombre_tienda || "",
    nombre_trabajador: row.nombre || "",
    correo: row.correo || "",
    tiene_contrasena: Boolean(row.contrasena),
    area: row.cargo || "",
    sueldo: Number(row.sueldo || 0),
    csi: row.csi || "",
    telefono: row.telefono || "",
    foto_dni: row.foto_dni || "",
    dias_horario: Object.keys(schedule),
    horario: schedule,
    estado: bool(row.estado ?? true),
  };
}

function serializeAttendance(row) {
  return {
    id_asistencia: String(row.id_asistencia ?? row.doc_id ?? ""),
    fecha: String(row.fecha || "").slice(0, 10),
    id_tienda: String(row.id_tienda ?? ""),
    nombre_tienda: row.nombre_tienda || "",
    dni: String(row.dni_trabajador ?? row.dni ?? ""),
    nombre_trabajador: row.nombre_trabajador || "",
    cargo: row.cargo || "",
    hora_inicio: formatTime(row.horario_entrada),
    inicio_receso: formatTime(row.horario_inicio_receso),
    final_receso: formatTime(row.horario_fin_receso),
    hora_final: formatTime(row.horario_salida),
    justificado: bool(row.justificado),
  };
}

export async function loadDashboard(includeAttendances = true) {
  const requests = [
    db().from("tienda").select("*").order("nombre"),
    db().from("trabajador").select("*").order("nombre"),
    db().from("horario_trabajador").select("*").order("dni_trabajador").order("dia_semana"),
  ];
  if (includeAttendances) {
    requests.push(
      db().from("v_asistencia_resumen").select("*").order("fecha", { ascending: false }).order("id_asistencia", { ascending: false }),
    );
  }
  const results = await Promise.all(requests);
  const stores = check(results[0], "No se pudieron consultar las tiendas").map(serializeStore);
  const storesById = new Map(stores.map((item) => [item.id_tienda, item]));
  const rawSchedules = check(results[2], "No se pudieron consultar los horarios");
  const scheduleMap = {};
  for (const row of rawSchedules) {
    const dni = String(row.dni_trabajador ?? "");
    scheduleMap[dni] ||= {};
    scheduleMap[dni][String(row.dia_semana || "")] = {
      horario_entrada: formatTime(row.horario_entrada),
      horario_inicio_receso: formatTime(row.horario_inicio_receso),
      horario_fin_receso: formatTime(row.horario_fin_receso),
      horario_salida: formatTime(row.horario_salida),
    };
  }
  const workers = check(results[1], "No se pudieron consultar los trabajadores")
    .map((row) => serializeWorker(row, storesById, scheduleMap));
  const workersByDni = new Map(workers.map((item) => [item.dni, item]));
  const schedules = rawSchedules.map((row) => {
    const worker = workersByDni.get(String(row.dni_trabajador ?? "")) || {};
    return {
      dni_trabajador: String(row.dni_trabajador ?? ""),
      nombre_trabajador: worker.nombre_trabajador || "",
      id_tienda: worker.id_sede || "",
      nombre_tienda: worker.nombre_sede || "",
      dia_semana: row.dia_semana || "",
      horario_entrada: formatTime(row.horario_entrada),
      horario_inicio_receso: formatTime(row.horario_inicio_receso),
      horario_fin_receso: formatTime(row.horario_fin_receso),
      horario_salida: formatTime(row.horario_salida),
    };
  });
  const attendances = includeAttendances
    ? check(results[3], "No se pudieron consultar las asistencias").map(serializeAttendance)
    : [];
  for (const attendance of attendances) {
    const worker = workersByDni.get(attendance.dni);
    if (worker) {
      attendance.nombre_trabajador = worker.nombre_trabajador;
      attendance.id_tienda = worker.id_sede;
      attendance.nombre_tienda = worker.nombre_sede;
    }
  }
  return { stores, workers, schedules, attendances };
}

export function attendancePeriod(dashboard, filters) {
  const { start, end, label } = periodBounds(filters.reference, filters.period);
  const query = String(filters.q || "").trim().toLowerCase();
  let workers = dashboard.workers.filter((worker) =>
    (!filters.store_id || worker.id_sede === filters.store_id) &&
    (!filters.worker_dni || worker.dni === filters.worker_dni) &&
    (!query || `${worker.nombre_trabajador} ${worker.dni} ${worker.nombre_sede}`.toLowerCase().includes(query)),
  );
  const workersByDni = new Map(workers.map((item) => [item.dni, item]));
  const schedules = {};
  for (const row of dashboard.schedules) {
    schedules[row.dni_trabajador] ||= {};
    schedules[row.dni_trabajador][row.dia_semana] = row;
  }
  const rows = [];
  for (const raw of dashboard.attendances) {
    const date = localDate(raw.fecha);
    const worker = workersByDni.get(raw.dni);
    if (!date || date < start || date > end || !worker) continue;
    const schedule = schedules[raw.dni]?.[WEEKDAYS[date.getDay()]];
    if (!schedule && !raw.justificado) continue;
    const expected = schedule ? timeMinutes(schedule.horario_entrada) : null;
    const actual = timeMinutes(raw.hora_inicio);
    rows.push({
      ...raw,
      nombre_trabajador: worker.nombre_trabajador,
      nombre_tienda: worker.nombre_sede,
      cargo: worker.area,
      late: expected !== null && actual !== null && actual > expected,
      fuera_horario: !schedule,
      justificable: !schedule && !raw.justificado && Boolean(raw.hora_inicio || raw.hora_final),
    });
  }
  rows.sort((a, b) => `${a.fecha}${a.nombre_trabajador}`.localeCompare(`${b.fecha}${b.nombre_trabajador}`));
  const storeLabel = dashboard.stores.find((item) => item.id_tienda === filters.store_id)?.nombre_tienda || "Todas las tiendas";
  const workerLabel = dashboard.workers.find((item) => item.dni === filters.worker_dni)?.nombre_trabajador || "Todas";
  return {
    start: isoDate(start), end: isoDate(end), label, store_label: storeLabel,
    worker_label: workerLabel, search: filters.q || "", workers, rows,
    metrics: {
      workers: workers.length,
      records: rows.length,
      on_time: rows.filter((row) => !row.late).length,
      late: rows.filter((row) => row.late).length,
      pending_justifications: rows.filter((row) => row.justificable).length,
    },
  };
}

function tokenSecret() {
  return process.env.AUTH_SECRET?.trim() || process.env.SUPABASE_SERVICE_ROLE_KEY || "cambia-esta-clave";
}

const b64url = (input) => Buffer.from(input).toString("base64url");

export function createToken(username) {
  const payload = b64url(JSON.stringify({
    u: String(username).trim().toLowerCase(),
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 12,
  }));
  const signature = createHmac("sha256", tokenSecret()).update(payload).digest("base64url");
  return `${payload}.${signature}`;
}

export function verifyToken(request) {
  const authorization = request.headers.get("authorization") || "";
  if (!authorization.toLowerCase().startsWith("bearer ")) return null;
  try {
    const [payload, supplied] = authorization.slice(7).split(".");
    const expected = createHmac("sha256", tokenSecret()).update(payload).digest();
    const actual = Buffer.from(supplied, "base64url");
    if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    return parsed.exp >= Math.floor(Date.now() / 1000) ? parsed.u : null;
  } catch {
    return null;
  }
}

export async function checkCredentials(username, password) {
  const result = await db().from("administrador").select("*").eq("correo", username).limit(1);
  const admin = check(result, "No se pudo validar el administrador")[0];
  if (admin) {
    const stored = admin.contrasena || admin.password || admin["contraseña"] || admin.clave || "";
    if (String(stored).startsWith("$2")) {
      if (await bcrypt.compare(password, stored)) return true;
    } else if (String(stored) === password) return true;
  }
  return Boolean(
    process.env.ADMIN_USERNAME && process.env.ADMIN_PASSWORD &&
    username === process.env.ADMIN_USERNAME.trim().toLowerCase() &&
    password === process.env.ADMIN_PASSWORD,
  );
}

export async function saveWorker(dni, payload, creating) {
  if (!dni || !String(payload.nombre || "").trim()) throw new ApiError(422, "DNI y nombre son obligatorios.");
  if (!String(payload.id_tienda || "").trim()) throw new ApiError(422, "Selecciona una tienda.");
  if (!(payload.schedules || []).length) throw new ApiError(422, "Selecciona al menos un día laborable.");
  if (creating && !String(payload.foto_dni || "").trim()) throw new ApiError(422, "El documento de DNI es obligatorio.");
  const data = {
    dni, id_tienda: payload.id_tienda,
    correo: String(payload.correo || "").trim().toLowerCase(),
    nombre: String(payload.nombre || "").trim(),
    cargo: String(payload.cargo || "").trim(),
    sueldo: Number(payload.sueldo || 0),
    telefono: String(payload.telefono || "").trim(),
    csi: String(payload.csi || "").trim(),
    foto_dni: String(payload.foto_dni || "").trim(),
    estado: payload.estado ?? true,
  };
  if (String(payload.password || "").trim()) data.contrasena = String(payload.password).trim();
  check(await db().from("trabajador").upsert(data, { onConflict: "dni" }), "No se pudo guardar el trabajador");
  check(await db().from("horario_trabajador").delete().eq("dni_trabajador", dni), "No se pudo actualizar el horario");
  const schedules = payload.schedules.map((item) => ({
    dni_trabajador: dni,
    dia_semana: item.dia_semana,
    horario_entrada: item.horario_entrada || "00:00",
    horario_inicio_receso: item.horario_inicio_receso || "00:00",
    horario_fin_receso: item.horario_fin_receso || "00:00",
    horario_salida: item.horario_salida || "00:00",
  }));
  check(await db().from("horario_trabajador").insert(schedules), "No se pudo guardar el horario");
}

export async function listMarks(start, end, storeId, workerDni) {
  const endExclusive = localDate(end);
  endExclusive.setDate(endExclusive.getDate() + 1);
  let request = db().from("asistencia_multiple").select(
    "id,id_tienda,id_trabajador,hora_marca,ubicacion,tipo",
  ).gte("hora_marca", `${start}T05:00:00.000Z`)
    .lt("hora_marca", `${isoDate(endExclusive)}T05:00:00.000Z`)
    .order("hora_marca", { ascending: false });
  if (storeId) request = request.eq("id_tienda", storeId);
  if (workerDni) request = request.eq("id_trabajador", workerDni);
  const marks = check(await request, "No se pudieron consultar las marcas");
  const [storesResult, workersResult] = await Promise.all([
    db().from("tienda").select("id_tienda,nombre,direccion"),
    db().from("trabajador").select("dni,nombre"),
  ]);
  const stores = new Map(check(storesResult).map((row) => [String(row.id_tienda), row]));
  const workers = new Map(check(workersResult).map((row) => [String(row.dni), row]));
  return marks.map((row) => {
    const date = new Date(row.hora_marca);
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    }).formatToParts(date).reduce((acc, item) => ({ ...acc, [item.type]: item.value }), {});
    return {
      id: row.id, id_tienda: row.id_tienda,
      nombre_tienda: stores.get(String(row.id_tienda))?.nombre || "",
      direccion_tienda: stores.get(String(row.id_tienda))?.direccion || "",
      id_trabajador: row.id_trabajador,
      nombre_trabajador: workers.get(String(row.id_trabajador))?.nombre || "",
      hora_marca: row.hora_marca,
      fecha_local: `${parts.year}-${parts.month}-${parts.day}`,
      hora_local: `${parts.hour}:${parts.minute}:${parts.second}`,
      ubicacion: row.ubicacion, tipo: row.tipo,
    };
  });
}

const hoursInSchedule = (schedule) => {
  const start = timeMinutes(schedule.horario_entrada);
  const end = timeMinutes(schedule.horario_salida);
  if (start === null || end === null || end <= start) return 8;
  let total = end - start;
  const breakStart = timeMinutes(schedule.horario_inicio_receso);
  const breakEnd = timeMinutes(schedule.horario_fin_receso);
  if (breakStart !== null && breakEnd !== null && breakEnd > breakStart) total -= breakEnd - breakStart;
  return Math.max(total / 60, 1);
};

const actualHours = (attendance) => {
  const start = timeMinutes(attendance.hora_inicio);
  const end = timeMinutes(attendance.hora_final);
  if (start === null || end === null || end <= start) return 0;
  let total = end - start;
  const breakStart = timeMinutes(attendance.inicio_receso);
  const breakEnd = timeMinutes(attendance.final_receso);
  if (breakStart !== null && breakEnd !== null && breakEnd > breakStart) total -= breakEnd - breakStart;
  return Math.max(total / 60, 0);
};

export function salarySummary(dashboard, dni, options) {
  const worker = dashboard.workers.find((item) => item.dni === dni);
  if (!worker) throw new ApiError(404, "Trabajador no encontrado.");
  const month = localDate(options.month) || new Date(new Date().getFullYear(), new Date().getMonth(), 1, 12);
  const schedules = Object.fromEntries(
    dashboard.schedules.filter((item) => item.dni_trabajador === dni).map((item) => [item.dia_semana, item]),
  );
  const attendance = new Map(
    dashboard.attendances
      .filter((item) => item.dni === dni && localDate(item.fecha)?.getMonth() === month.getMonth() && localDate(item.fecha)?.getFullYear() === month.getFullYear())
      .map((item) => [item.fecha, item]),
  );
  const referenceDays = Math.max(Number(options.reference_days || 26), 1);
  const hoursPerDay = Math.max(Number(options.hours_per_day || 8), 1);
  const baseSalary = Number(worker.sueldo || 0);
  const dailyRate = baseSalary / referenceDays;
  const hourRate = dailyRate / hoursPerDay;
  const penalty = options.penalty_mode === "fixed" ? Number(options.fixed_penalty || 0) : hourRate;
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const breakdown = [];
  let absences = 0, tardies = 0, extraDays = 0, scheduledDays = 0;
  let absenceDeduction = 0, tardyDeduction = 0, extraEarnings = 0, scheduledEarnings = 0;
  for (let day = 1; day <= days; day += 1) {
    const current = new Date(month.getFullYear(), month.getMonth(), day, 12);
    const key = isoDate(current);
    const schedule = schedules[WEEKDAYS[current.getDay()]];
    const mark = attendance.get(key);
    if (schedule) scheduledDays += 1;
    if (!mark && schedule) {
      absences += 1;
      absenceDeduction += dailyRate;
      breakdown.push({
        fecha: key, tipo: "Falta",
        entrada_programada: schedule.horario_entrada || "-",
        salida_programada: schedule.horario_salida || "-",
        entrada_real: "-", salida_real: "-", horas_reales: 0, pago: 0,
        descuento: Number(dailyRate.toFixed(2)), bonificacion: 0,
      });
      continue;
    }
    if (mark && schedule) {
      const pay = hoursInSchedule(schedule) * hourRate;
      scheduledEarnings += pay;
      const expected = timeMinutes(schedule.horario_entrada);
      const actual = timeMinutes(mark.hora_inicio);
      const late = expected !== null && actual !== null && actual > expected + Number(options.tolerance_minutes || 0);
      const discount = late ? penalty : 0;
      if (late) { tardies += 1; tardyDeduction += discount; }
      breakdown.push({
        fecha: key, tipo: late ? "Tardanza" : "Asistencia",
        entrada_programada: schedule.horario_entrada || "-",
        salida_programada: schedule.horario_salida || "-",
        entrada_real: mark.hora_inicio || "-", salida_real: mark.hora_final || "-",
        horas_reales: Number(actualHours(mark).toFixed(2)),
        pago: Number(pay.toFixed(2)), descuento: Number(discount.toFixed(2)), bonificacion: 0,
      });
    } else if (mark?.justificado) {
      let extraHours = Math.max(Math.floor((timeMinutes(mark.hora_final) || 0) / 60) - Math.ceil((timeMinutes(mark.hora_inicio) || 0) / 60), 0);
      if (mark.inicio_receso && mark.final_receso) extraHours = Math.max(extraHours - 1, 0);
      const bonus = extraHours * hourRate;
      if (extraHours) { extraDays += 1; extraEarnings += bonus; }
      breakdown.push({
        fecha: key, tipo: extraHours ? "Extra" : "Asistencia",
        entrada_programada: "-", salida_programada: "-",
        entrada_real: mark.hora_inicio || "-", salida_real: mark.hora_final || "-",
        horas_reales: Number(actualHours(mark).toFixed(2)),
        pago: Number(bonus.toFixed(2)), descuento: 0, bonificacion: Number(bonus.toFixed(2)),
      });
    }
  }
  const round = (value) => Number(value.toFixed(2));
  return {
    worker, month: isoDate(new Date(month.getFullYear(), month.getMonth(), 1, 12)),
    base_salary: baseSalary, reference_days: referenceDays, hours_per_day: hoursPerDay,
    scheduled_month_days: scheduledDays, present_days: scheduledDays - absences + extraDays,
    absences, tardies, scheduled_earnings: round(scheduledEarnings),
    daily_rate: round(dailyRate), hour_rate: round(hourRate),
    absence_deduction: round(absenceDeduction), tardy_deduction: round(tardyDeduction),
    extra_days: extraDays, extra_earnings: round(extraEarnings),
    net_salary: round(Math.max(scheduledEarnings - tardyDeduction + extraEarnings, 0)),
    penalty_amount: round(penalty), breakdown,
  };
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
