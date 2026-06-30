import React, { useMemo, useState } from "react";
import { get, query } from "../api";
import { Badge, Button, Card, Empty, Field, Metric, PageHeader, Spinner, Table, money, useAsync } from "../ui";

const currentMonth = () => new Date().toISOString().slice(0, 7);

export default function SalariesPage({ notify }) {
  const catalog = useAsync(() => get("/api/workers"), []);
  const [store, setStore] = useState("");
  const [dni, setDni] = useState("");
  const [settings, setSettings] = useState({
    month: currentMonth(),
    reference_days: 26,
    hours_per_day: 8,
    tolerance_minutes: 0,
    penalty_mode: "hour",
    fixed_penalty: 0,
  });
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const workers = useMemo(() => (catalog.data?.workers || []).filter((worker) => worker.estado && (!store || worker.id_sede === store)), [catalog.data, store]);
  const set = (key, value) => setSettings({ ...settings, [key]: value });

  const calculate = async () => {
    if (!dni) return notify("Selecciona un trabajador.", "error");
    setLoading(true);
    try {
      const result = await get(`/api/salaries/${dni}?${query({ ...settings, month: `${settings.month}-01` })}`);
      setSummary(result);
    } catch (error) {
      notify(error.message, "error");
    } finally { setLoading(false); }
  };

  return (
    <>
      <PageHeader title="Salarios" subtitle="Calcula el pago mensual según horarios, faltas, tardanzas y días extra." />
      <Card className="filters salary-filters">
        <Field label="Tienda"><select value={store} onChange={(event) => { setStore(event.target.value); setDni(""); setSummary(null); }}><option value="">Todas</option>{(catalog.data?.stores || []).map((item) => <option key={item.id_tienda} value={item.id_tienda}>{item.nombre_tienda}</option>)}</select></Field>
        <Field label="Trabajador"><select value={dni} onChange={(event) => { setDni(event.target.value); setSummary(null); }}><option value="">Selecciona…</option>{workers.map((worker) => <option key={worker.dni} value={worker.dni}>{worker.nombre_trabajador}</option>)}</select></Field>
        <Field label="Mes"><input type="month" value={settings.month} onChange={(event) => set("month", event.target.value)} /></Field>
        <Field label="Días de referencia"><input type="number" min="1" value={settings.reference_days} onChange={(event) => set("reference_days", event.target.value)} /></Field>
        <Field label="Horas por día"><input type="number" min="1" step="0.5" value={settings.hours_per_day} onChange={(event) => set("hours_per_day", event.target.value)} /></Field>
        <Field label="Tolerancia (min)"><input type="number" min="0" value={settings.tolerance_minutes} onChange={(event) => set("tolerance_minutes", event.target.value)} /></Field>
        <Field label="Descuento por tardanza"><select value={settings.penalty_mode} onChange={(event) => set("penalty_mode", event.target.value)}><option value="hour">1 hora de trabajo</option><option value="fixed">Monto fijo</option></select></Field>
        {settings.penalty_mode === "fixed" && <Field label="Monto fijo"><input type="number" min="0" step="1" value={settings.fixed_penalty} onChange={(event) => set("fixed_penalty", event.target.value)} /></Field>}
        <Button onClick={calculate} disabled={loading}>{loading ? "Calculando…" : "Calcular salario"}</Button>
      </Card>
      {catalog.loading ? <Spinner /> : catalog.error ? <div className="form-error">{catalog.error}</div> : loading ? <Spinner label="Procesando mes…" /> : !summary ? (
        <Card><Empty title="Selecciona una persona" text="Configura el periodo y presiona “Calcular salario” para ver el detalle." /></Card>
      ) : (
        <>
          <Card className="worker-summary">
            <div className="person person--large"><span>{summary.worker.nombre_trabajador.slice(0, 1)}</span><div><strong>{summary.worker.nombre_trabajador}</strong><small>DNI {summary.worker.dni} · {summary.worker.nombre_sede}</small></div></div>
            <Badge tone="blue">{settings.month}</Badge>
          </Card>
          <div className="metrics-grid metrics-grid--salary">
            <Metric label="Sueldo base" value={money(summary.base_salary)} />
            <Metric label="Pago calculado" value={money(summary.scheduled_earnings)} tone="slate" />
            <Metric label="Faltas" value={summary.absences} detail={`Referencia: ${money(summary.absence_deduction)}`} tone="amber" />
            <Metric label="Tardanzas" value={summary.tardies} detail={`Descuento: ${money(summary.tardy_deduction)}`} tone="violet" />
            <Metric label="Días extra" value={summary.extra_days} detail={`Bono: ${money(summary.extra_earnings)}`} tone="green" />
            <Metric label="Pago neto" value={money(summary.net_salary)} tone="green" />
          </div>
          <Card>
            <div className="card-title"><div><h2>Detalle del cálculo</h2><p>{summary.present_days} días presentes · Tarifa diaria {money(summary.daily_rate)}</p></div></div>
            <Table headers={["Fecha", "Tipo", "Programado", "Marcas reales", "Horas", "Pago", "Descuento", "Bonificación"]} minWidth={1000}>
              {summary.breakdown.map((row) => <tr key={`${row.fecha}-${row.tipo}`}><td><strong>{row.fecha}</strong></td><td><Badge tone={row.tipo === "Falta" ? "danger" : row.tipo === "Tardanza" ? "warning" : row.tipo === "Extra" ? "blue" : "success"}>{row.tipo}</Badge></td><td>{row.entrada_programada} — {row.salida_programada}</td><td>{row.entrada_real} — {row.salida_real}</td><td>{row.horas_reales}</td><td>{money(row.pago)}</td><td>{money(row.descuento)}</td><td>{money(row.bonificacion)}</td></tr>)}
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
