import { useEffect, useState } from "react";
import { api } from "../api";
import type { Bootstrap, ReferenceDetail } from "../types";
import Drawer from "./Drawer";

interface Props {
  boot: Bootstrap;
  onClose: () => void;
  onChanged: (msg: string) => void;
}

export default function ManageLists({ boot, onClose, onChanged }: Props) {
  const [details, setDetails] = useState<Record<string, ReferenceDetail>>({});
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const entries = await Promise.all(
      boot.reference_lists.map((rl) => api.reference(rl.key))
    );
    const map: Record<string, ReferenceDetail> = {};
    entries.forEach((d) => (map[d.key] = d));
    setDetails(map);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleActive = async (key: string, id: number, next: boolean) => {
    setBusy(true);
    await api.updateReference(key, id, { is_active: next });
    await load();
    onChanged(next ? "Option reactivated." : "Option deactivated.");
    setBusy(false);
  };

  return (
    <Drawer
      title="Manage lists"
      subtitle="Add, rename or deactivate the dropdown options the team picks from."
      onClose={onClose}
    >
      {boot.reference_lists.map((rl) => {
        const detail = details[rl.key];
        return (
          <div className="card" key={rl.key}>
            <h4>{rl.label}</h4>
            {rl.note && <p className="note">{rl.note}</p>}
            {!detail ? (
              <div className="mono">Loading…</div>
            ) : (
              <>
                <table className="mini">
                  <thead>
                    <tr>
                      <th>Option</th>
                      {rl.extra_cols.map((c) => <th key={c.name}>{c.label}</th>)}
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.options.map((o) => (
                      <tr key={o.id}>
                        <td>{o.name}</td>
                        {rl.extra_cols.map((c) => <td key={c.name} className="mono">{o[c.name] ?? "—"}</td>)}
                        <td><span className={`tag ${o.is_active ? "on" : "off"}`}>{o.is_active ? "Active" : "Inactive"}</span></td>
                        <td>
                          <button
                            className="linklike"
                            disabled={busy}
                            onClick={() => toggleActive(rl.key, o.id, !o.is_active)}
                          >
                            {o.is_active ? "Deactivate" : "Reactivate"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <AddOption
                  refKey={rl.key}
                  extraCols={rl.extra_cols}
                  onAdded={async () => {
                    await load();
                    onChanged(`Added a new ${rl.label.toLowerCase()} option.`);
                  }}
                />
              </>
            )}
          </div>
        );
      })}
    </Drawer>
  );
}

function AddOption({
  refKey,
  extraCols,
  onAdded,
}: {
  refKey: string;
  extraCols: { name: string; label: string; help: string | null }[];
  onAdded: () => void;
}) {
  const [data, setData] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const add = async () => {
    setBusy(true);
    setErr(null);
    const res = await api.addReference(refKey, data);
    setBusy(false);
    if (res.ok) {
      setData({});
      onAdded();
    } else {
      setErr(res.errors?.[0] ?? "Could not add option.");
    }
  };

  return (
    <div className="inline-form">
      <div className="field">
        <label>New option</label>
        <input
          type="text"
          value={data.name ?? ""}
          placeholder="e.g. Health & Wellness"
          onChange={(e) => setData((d) => ({ ...d, name: e.target.value }))}
        />
      </div>
      {extraCols.map((c) => (
        <div className="field" key={c.name}>
          <label>{c.label}</label>
          <input
            type="text"
            value={data[c.name] ?? ""}
            placeholder={c.help ?? ""}
            onChange={(e) => setData((d) => ({ ...d, [c.name]: e.target.value }))}
          />
        </div>
      ))}
      <button className="btn sm" disabled={busy || !data.name} onClick={add}>Add</button>
      {err && <div className="val-box err" style={{ width: "100%" }}>{err}</div>}
    </div>
  );
}
