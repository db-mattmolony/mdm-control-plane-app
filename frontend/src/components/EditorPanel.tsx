import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Bootstrap, Row, ValidateResult } from "../types";

interface Props {
  boot: Bootstrap;
  row: Row | null; // null = create
  onClose: () => void;
  onSaved: (msg: string) => void;
}

export default function EditorPanel({ boot, row, onClose, onSaved }: Props) {
  const { domain, lookups } = boot;
  const isEdit = row != null;
  const pk = row ? (row[domain.pk] as number) : null;

  const initial = useMemo(() => {
    const v: Record<string, string> = {};
    for (const f of domain.fields) v[f.name] = (row?.[f.name] ?? "") as string;
    return v;
  }, [row, domain]);

  const [values, setValues] = useState<Record<string, string>>(initial);
  const [validation, setValidation] = useState<ValidateResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmRetire, setConfirmRetire] = useState(false);
  const debounce = useRef<number | undefined>(undefined);

  useEffect(() => {
    setValues(initial);
    setValidation(null);
    setConfirmRetire(false);
  }, [initial]);

  // Live validation against the high-level variables, debounced.
  useEffect(() => {
    const complete = domain.fields.every((f) => !f.required || values[f.name]);
    if (!complete) {
      setValidation(null);
      return;
    }
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => {
      api.validate(values, pk).then(setValidation).catch(() => setValidation(null));
    }, 350);
    return () => window.clearTimeout(debounce.current);
  }, [values, domain, pk]);

  const set = (name: string, v: string) => setValues((s) => ({ ...s, [name]: v }));

  const requiredFilled = domain.fields.every((f) => !f.required || values[f.name]);
  const hasErrors = (validation?.errors?.length ?? 0) > 0;
  const canSave = requiredFilled && !hasErrors && !saving;

  const save = async () => {
    setSaving(true);
    try {
      const res = isEdit ? await api.update(pk!, values) : await api.create(values);
      if (res.ok) {
        onSaved(isEdit ? "Changes saved." : "Authorisation added.");
      } else {
        setValidation({ errors: res.errors ?? ["Save failed."], coverage: { fills_gap: false, dimension: null, value: null } });
      }
    } catch (e: any) {
      setValidation({ errors: [e.message ?? "Save failed."], coverage: { fills_gap: false, dimension: null, value: null } });
    } finally {
      setSaving(false);
    }
  };

  const retire = async () => {
    setSaving(true);
    try {
      const res = await api.retire(pk!);
      if (res.ok) onSaved(`Retired #${pk} (expired today).`);
      else setValidation({ errors: res.errors ?? ["Retire failed."], coverage: { fills_gap: false, dimension: null, value: null } });
    } finally {
      setSaving(false);
    }
  };

  const fmtTs = (ts?: string) => (ts ? new Date(ts).toLocaleString() : "—");

  return (
    <div className="panel-inner" role="dialog" aria-label="Authorisation editor">
      <div className="panel-hdr">
        <div>
          <div className="ptitle">
            {isEdit ? `#${pk} · ${row?.vendor_name ?? ""}` : "New authorisation"}
          </div>
          <div className="psub">
            {isEdit ? (
              <>
                <span className={`pill ${row?.status}`}>{row?.status}</span>{" "}
                <span className="changed-note">
                  Last changed by {row?.updated_by ?? "—"} · {fmtTs(row?.updated_at)}
                </span>
              </>
            ) : (
              "Create a vendor supply authorisation"
            )}
          </div>
        </div>
        <button className="panel-x" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="panel-body">
        {domain.fields.map((f) => (
          <div className="field" key={f.name}>
            <label>
              {f.label} {f.required && <span className="req">*</span>}
            </label>
            {f.kind === "lookup" ? (
              <select value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)}>
                <option value="">Select {f.label.toLowerCase()}…</option>
                {(lookups[f.lookup ?? ""] ?? []).map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
                {/* keep a deactivated / legacy value visible on edit */}
                {values[f.name] && !(lookups[f.lookup ?? ""] ?? []).includes(values[f.name]) && (
                  <option value={values[f.name]}>{values[f.name]} (inactive)</option>
                )}
              </select>
            ) : (
              <input
                type="text"
                value={values[f.name] ?? ""}
                placeholder={f.help ?? ""}
                onChange={(e) => set(f.name, e.target.value)}
              />
            )}
            {f.help && <div className="help">{f.help}</div>}
          </div>
        ))}

        {hasErrors && (
          <div className="val-box err">
            <b>Can't save yet</b>
            <ul>
              {validation!.errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          </div>
        )}
        {!hasErrors && validation?.coverage?.fills_gap && (
          <div className="val-box gap">
            ✓ This fills a coverage gap — <b>{validation.coverage.value}</b> currently has no
            active authorisation. Saving this closes the gap.
          </div>
        )}
        {!hasErrors && validation && !validation.coverage?.fills_gap && requiredFilled && (
          <div className="val-box ok">✓ Looks good — no conflicts with existing authorisations.</div>
        )}

        {isEdit && (
          <div className="retire-zone">
            <div className="lbl">Retire this authorisation</div>
            <p>
              Soft-delete: the row is expired as of today and drops out of active views, but is
              never destroyed — history and lineage are preserved.
            </p>
            <label className="checkrow">
              <input
                type="checkbox"
                checked={confirmRetire}
                onChange={(e) => setConfirmRetire(e.target.checked)}
              />
              I want to retire this authorisation
            </label>
            <button className="btn danger sm" disabled={!confirmRetire || saving} onClick={retire}>
              Retire authorisation
            </button>
          </div>
        )}
      </div>

      <div className="panel-foot">
        <button className="btn" disabled={!canSave} onClick={save}>
          {saving ? "Saving…" : isEdit ? "Save changes" : "Save authorisation"}
        </button>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
