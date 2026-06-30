import React, { useState } from "react";
import { get, post, put, remove } from "../api";
import { Badge, Button, Card, Empty, Field, Modal, PageHeader, Spinner, useAsync } from "../ui";

const empty = { id_tienda: "", correo_destino: "", minutos_tolerancia: 10, nombre_reporte: "Reporte mañana", hora_envio: "08:30", ventana_minutos: 5 };

function ConfigForm({ config, stores, onClose, onSaved, notify }) {
  const [form, setForm] = useState(config ? { ...config, hora_envio: String(config.hora_envio || "").slice(0, 5) } : empty);
  const [saving, setSaving] = useState(false);
  const set = (key, value) => setForm({ ...form, [key]: value });
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      if (config) await put(`/api/email-configs/${config.id_config}`, form);
      else await post("/api/email-configs", form);
      notify(config ? "Configuración actualizada." : "Configuración creada.");
      onSaved();
    } catch (error) { notify(error.message, "error"); setSaving(false); }
  };
  return (
    <Modal title={config ? "Editar alerta" : "Nueva alerta"} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Tienda"><select value={form.id_tienda || ""} onChange={(event) => set("id_tienda", event.target.value)}><option value="">General · Todas</option>{stores.map((store) => <option key={store.id_tienda} value={store.id_tienda}>{store.nombre_tienda}</option>)}</select></Field>
          <Field label="Correo destino *"><input type="email" value={form.correo_destino} onChange={(event) => set("correo_destino", event.target.value)} /></Field>
          <Field label="Nombre del reporte"><select value={form.nombre_reporte} onChange={(event) => set("nombre_reporte", event.target.value)}><option>Reporte mañana</option><option>Reporte tarde</option></select></Field>
          <Field label="Hora de envío *"><input type="time" value={form.hora_envio} onChange={(event) => set("hora_envio", event.target.value)} /></Field>
          <Field label="Tolerancia (min)"><input type="number" min="0" max="120" value={form.minutos_tolerancia} onChange={(event) => set("minutos_tolerancia", event.target.value)} /></Field>
          <Field label="Ventana (min)"><input type="number" min="1" max="60" value={form.ventana_minutos} onChange={(event) => set("ventana_minutos", event.target.value)} /></Field>
        </div>
        <div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button><Button disabled={saving}>{saving ? "Guardando…" : "Guardar alerta"}</Button></div>
      </form>
    </Modal>
  );
}

export default function EmailPage({ notify }) {
  const configs = useAsync(() => get("/api/email-configs"), []);
  const stores = useAsync(() => get("/api/stores"), []);
  const [editing, setEditing] = useState(undefined);
  const erase = async (config) => {
    if (!window.confirm("¿Eliminar esta configuración de correo?")) return;
    try { await remove(`/api/email-configs/${config.id_config}`); notify("Configuración eliminada."); configs.reload(); }
    catch (error) { notify(error.message, "error"); }
  };
  const storeName = (id) => stores.data?.find((store) => String(store.id_tienda) === String(id))?.nombre_tienda || "General";
  return (
    <>
      <PageHeader title="Alertas de puntualidad" subtitle="Gestiona los reportes automáticos enviados por correo." actions={<Button onClick={() => setEditing(null)}>＋ Nueva configuración</Button>} />
      {configs.error && <div className="form-error">{configs.error}</div>}
      {configs.loading || stores.loading ? <Spinner /> : !configs.data?.length ? <Card><Empty title="Sin alertas configuradas" text="Crea la primera regla de envío automático." /></Card> : (
        <div className="config-grid">
          {configs.data.map((config) => <Card className="config-card" key={config.id_config}><div className="config-card__head"><span className="config-icon">✉</span><Badge active={config.activo}>{config.activo ? "Activa" : "Inactiva"}</Badge></div><h2>{config.nombre_reporte}</h2><p>{storeName(config.id_tienda)}</p><dl><div><dt>Destino</dt><dd>{config.correo_destino}</dd></div><div><dt>Hora</dt><dd>{String(config.hora_envio).slice(0, 5)}</dd></div><div><dt>Tolerancia</dt><dd>{config.minutos_tolerancia} min</dd></div><div><dt>Ventana</dt><dd>{config.ventana_minutos} min</dd></div></dl><div className="config-card__actions"><Button variant="ghost" onClick={() => setEditing(config)}>Editar</Button><Button variant="danger" onClick={() => erase(config)}>Eliminar</Button></div></Card>)}
        </div>
      )}
      {editing !== undefined && <ConfigForm config={editing} stores={stores.data || []} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); configs.reload(); }} notify={notify} />}
    </>
  );
}
