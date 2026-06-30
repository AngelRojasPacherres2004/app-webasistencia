import React, { useMemo, useState } from "react";
import { download, get, patch, post, put, query } from "../api";
import { Badge, Button, Card, Empty, Field, Modal, PageHeader, Spinner, Table, useAsync } from "../ui";

const DAYS = [
  ["lunes", "Lunes"], ["martes", "Martes"], ["miercoles", "Miércoles"],
  ["jueves", "Jueves"], ["viernes", "Viernes"], ["sabado", "Sábado"],
];
const baseHours = {
  horario_entrada: "09:00",
  horario_inicio_receso: "13:00",
  horario_fin_receso: "14:00",
  horario_salida: "18:00",
};

function WorkerForm({ worker, stores, onClose, onSaved, notify }) {
  const existingSchedule = worker?.horario || {};
  const [form, setForm] = useState({
    dni: worker?.dni || "",
    nombre: worker?.nombre_trabajador || "",
    correo: worker?.correo || "",
    telefono: worker?.telefono || "",
    cargo: worker?.area || "",
    sueldo: worker?.sueldo || 0,
    csi: worker?.csi || "",
    id_tienda: worker?.id_sede || "",
    password: "",
    foto_dni: worker?.foto_dni || "",
    estado: worker?.estado ?? true,
  });
  const [days, setDays] = useState(worker?.dias_horario?.length ? worker.dias_horario : DAYS.map(([key]) => key));
  const [hours, setHours] = useState(Object.fromEntries(DAYS.map(([key]) => [key, { ...baseHours, ...(existingSchedule[key] || {}) }])));
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (key, value) => setForm({ ...form, [key]: value });
  const toggleDay = (day) => setDays((current) => current.includes(day) ? current.filter((item) => item !== day) : [...current, day]);
  const setHour = (day, key, value) => setHours({ ...hours, [day]: { ...hours[day], [key]: value } });

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      let photoUrl = form.foto_dni;
      if (file) {
        const upload = new FormData();
        upload.append("file", file);
        const result = await post(`/api/uploads/worker-document?dni=${encodeURIComponent(form.dni)}`, upload);
        photoUrl = result.secure_url;
      }
      const payload = {
        ...form,
        foto_dni: photoUrl,
        schedules: days.map((day) => ({ dia_semana: day, ...hours[day] })),
      };
      if (worker) await put(`/api/workers/${worker.dni}`, payload);
      else await post("/api/workers", payload);
      notify(worker ? "Trabajador actualizado." : "Trabajador registrado.");
      onSaved();
    } catch (error) {
      notify(error.message, "error");
      setSaving(false);
    }
  };

  return (
    <Modal title={worker ? "Editar trabajador" : "Nuevo trabajador"} onClose={onClose} wide>
      <form onSubmit={submit}>
        <div className="form-grid form-grid--3">
          <Field label="DNI *"><input value={form.dni} disabled={Boolean(worker)} onChange={(event) => set("dni", event.target.value)} /></Field>
          <Field label="Nombre completo *"><input value={form.nombre} onChange={(event) => set("nombre", event.target.value)} /></Field>
          <Field label="Tienda *"><select value={form.id_tienda} onChange={(event) => set("id_tienda", event.target.value)}><option value="">Selecciona…</option>{stores.map((store) => <option key={store.id_tienda} value={store.id_tienda}>{store.nombre_tienda}</option>)}</select></Field>
          <Field label="Cargo"><input value={form.cargo} onChange={(event) => set("cargo", event.target.value)} /></Field>
          <Field label="Sueldo"><input type="number" min="0" step="50" value={form.sueldo} onChange={(event) => set("sueldo", event.target.value)} /></Field>
          <Field label="CSI / código"><input value={form.csi} onChange={(event) => set("csi", event.target.value)} /></Field>
          <Field label="Correo"><input type="email" value={form.correo} onChange={(event) => set("correo", event.target.value)} /></Field>
          <Field label="Teléfono"><input value={form.telefono} onChange={(event) => set("telefono", event.target.value)} /></Field>
          <Field label={worker ? "Nueva contraseña" : "Contraseña *"}><input type="password" value={form.password} onChange={(event) => set("password", event.target.value)} /></Field>
          <Field label={worker ? "Reemplazar documento DNI" : "Documento DNI *"}><input type="file" accept=".jpg,.jpeg,.png,.pdf" onChange={(event) => setFile(event.target.files[0] || null)} /></Field>
          <Field label="Estado"><select value={String(form.estado)} onChange={(event) => set("estado", event.target.value === "true")}><option value="true">Activo</option><option value="false">Inactivo</option></select></Field>
        </div>
        <div className="schedule">
          <div className="schedule__title"><div><h3>Horario semanal</h3><p>Activa los días laborables y define las cuatro marcas.</p></div><Badge tone="blue">{days.length} días</Badge></div>
          {DAYS.map(([day, label]) => (
            <div className={`schedule-row ${days.includes(day) ? "" : "schedule-row--off"}`} key={day}>
              <label className="day-toggle"><input type="checkbox" checked={days.includes(day)} onChange={() => toggleDay(day)} /><span>{label}</span></label>
              {[
                ["horario_entrada", "Entrada"], ["horario_inicio_receso", "Ini. receso"],
                ["horario_fin_receso", "Fin receso"], ["horario_salida", "Salida"],
              ].map(([key, text]) => <Field label={text} key={key}><input type="time" disabled={!days.includes(day)} value={hours[day][key]} onChange={(event) => setHour(day, key, event.target.value)} /></Field>)}
            </div>
          ))}
        </div>
        <div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button><Button disabled={saving}>{saving ? "Guardando…" : "Guardar trabajador"}</Button></div>
      </form>
    </Modal>
  );
}

export default function WorkersPage({ notify }) {
  const { data, loading, error, reload } = useAsync(() => get("/api/workers"), []);
  const [search, setSearch] = useState("");
  const [store, setStore] = useState("");
  const [editing, setEditing] = useState(undefined);
  const workers = data?.workers || [];
  const filtered = useMemo(() => workers.filter((worker) =>
    (!store || worker.id_sede === store) &&
    `${worker.nombre_trabajador} ${worker.dni} ${worker.area} ${worker.nombre_sede}`.toLowerCase().includes(search.toLowerCase()),
  ), [workers, store, search]);

  const toggle = async (worker) => {
    try {
      await patch(`/api/workers/${worker.dni}/status`, { estado: !worker.estado });
      notify("Estado del trabajador actualizado.");
      reload();
    } catch (requestError) { notify(requestError.message, "error"); }
  };
  const exportPdf = async () => {
    try {
      await download(`/api/workers/export.pdf?${query({ store_id: store, q: search })}`, "trabajadores.pdf");
    } catch (requestError) { notify(requestError.message, "error"); }
  };

  return (
    <>
      <PageHeader title="Trabajadores" subtitle="Gestiona personal, documentos, horarios y accesos." actions={<><Button variant="secondary" onClick={exportPdf}>↓ PDF</Button><Button onClick={() => setEditing(null)}>＋ Nuevo trabajador</Button></>} />
      <Card>
        <div className="toolbar toolbar--filters">
          <input className="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar nombre, DNI o cargo…" />
          <select value={store} onChange={(event) => setStore(event.target.value)}><option value="">Todas las tiendas</option>{(data?.stores || []).map((item) => <option key={item.id_tienda} value={item.id_tienda}>{item.nombre_tienda}</option>)}</select>
          <Badge tone="blue">{filtered.length} personas</Badge>
        </div>
        {error && <div className="form-error">{error}</div>}
        {loading ? <Spinner /> : !filtered.length ? <Empty text="No hay trabajadores que coincidan con los filtros." /> : (
          <Table headers={["Trabajador", "DNI", "Tienda", "Cargo", "Sueldo", "Horario", "Estado", "Acciones"]} minWidth={1050}>
            {filtered.map((worker) => (
              <tr key={worker.dni}>
                <td><div className="person"><span>{worker.nombre_trabajador.slice(0, 1)}</span><div><strong>{worker.nombre_trabajador}</strong><small>{worker.correo || "Sin correo"}</small></div></div></td>
                <td>{worker.dni}</td><td>{worker.nombre_sede || "—"}</td><td>{worker.area || "—"}</td><td>S/ {Number(worker.sueldo || 0).toFixed(2)}</td><td>{worker.dias_horario.length} días</td>
                <td><Badge active={worker.estado}>{worker.estado ? "Activo" : "Inactivo"}</Badge></td>
                <td className="row-actions"><button onClick={() => toggle(worker)}>{worker.estado ? "●" : "○"}</button><button onClick={() => setEditing(worker)}>✎</button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing !== undefined && <WorkerForm worker={editing} stores={data?.stores || []} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); reload(); }} notify={notify} />}
    </>
  );
}
