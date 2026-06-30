import React, { useMemo, useState } from "react";
import { get, patch, post, put } from "../api";
import { Badge, Button, Card, Empty, Field, Modal, PageHeader, Spinner, Table, today, useAsync } from "../ui";

const emptyStore = () => ({
  nombre: "", correo: "", telefono: "", direccion: "", fecha_apertura: today(), password: "", estado: true,
});

function StoreForm({ initial, onClose, onSaved, notify }) {
  const [form, setForm] = useState(initial ? {
    nombre: initial.nombre_tienda,
    correo: initial.correo,
    telefono: initial.telefono,
    direccion: initial.direccion,
    fecha_apertura: initial.fecha_apertura || today(),
    password: "",
    estado: initial.estado,
  } : emptyStore());
  const [saving, setSaving] = useState(false);
  const set = (key, value) => setForm({ ...form, [key]: value });
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      if (initial) await put(`/api/stores/${initial.id_tienda}`, form);
      else await post("/api/stores", form);
      notify(initial ? "Tienda actualizada." : "Tienda registrada.");
      onSaved();
    } catch (error) {
      notify(error.message, "error");
      setSaving(false);
    }
  };
  return (
    <Modal title={initial ? "Editar tienda" : "Nueva tienda"} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Nombre *"><input value={form.nombre} onChange={(event) => set("nombre", event.target.value)} /></Field>
          <Field label="Correo *"><input type="email" value={form.correo} onChange={(event) => set("correo", event.target.value)} /></Field>
          <Field label="Teléfono"><input value={form.telefono} onChange={(event) => set("telefono", event.target.value)} /></Field>
          <Field label="Dirección"><input value={form.direccion} onChange={(event) => set("direccion", event.target.value)} /></Field>
          <Field label="Fecha de apertura"><input type="date" value={form.fecha_apertura} onChange={(event) => set("fecha_apertura", event.target.value)} /></Field>
          <Field label={initial ? "Nueva contraseña" : "Contraseña *"} hint={initial ? "Déjala vacía para conservar la actual." : ""}>
            <input type="password" value={form.password} onChange={(event) => set("password", event.target.value)} />
          </Field>
        </div>
        <div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button><Button disabled={saving}>{saving ? "Guardando…" : "Guardar tienda"}</Button></div>
      </form>
    </Modal>
  );
}

export default function StoresPage({ notify }) {
  const { data: stores, loading, error, reload } = useAsync(() => get("/api/stores"), []);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(undefined);
  const filtered = useMemo(() => (stores || []).filter((store) =>
    `${store.nombre_tienda} ${store.correo} ${store.direccion}`.toLowerCase().includes(search.toLowerCase()),
  ), [stores, search]);

  const toggle = async (store) => {
    try {
      await patch(`/api/stores/${store.id_tienda}/status`, { estado: !store.estado });
      notify("Estado de la tienda actualizado.");
      reload();
    } catch (requestError) { notify(requestError.message, "error"); }
  };

  return (
    <>
      <PageHeader title="Tiendas" subtitle="Administra sedes, accesos y estado operativo." actions={<Button onClick={() => setEditing(null)}>＋ Nueva tienda</Button>} />
      <Card>
        <div className="toolbar"><input className="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre, correo o dirección…" /><Badge tone="blue">{filtered.length} tiendas</Badge></div>
        {error && <div className="form-error">{error}</div>}
        {loading ? <Spinner /> : !filtered.length ? <Empty text="No hay tiendas que coincidan con la búsqueda." /> : (
          <Table headers={["Tienda", "Correo", "Dirección", "Apertura", "Estado", "Acciones"]}>
            {filtered.map((store) => (
              <tr key={store.id_tienda}>
                <td><strong>{store.nombre_tienda}</strong><small className="cell-sub">{store.telefono || "Sin teléfono"}</small></td>
                <td>{store.correo}</td><td>{store.direccion || "—"}</td><td>{store.fecha_apertura || "—"}</td>
                <td><Badge active={store.estado}>{store.estado ? "Activa" : "Inactiva"}</Badge></td>
                <td className="row-actions"><button onClick={() => toggle(store)} title="Cambiar estado">{store.estado ? "●" : "○"}</button><button onClick={() => setEditing(store)} title="Editar">✎</button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing !== undefined && <StoreForm initial={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); reload(); }} notify={notify} />}
    </>
  );
}
