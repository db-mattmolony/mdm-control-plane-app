import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditRow } from "../types";
import Drawer from "./Drawer";

interface Props {
  onClose: () => void;
}

const ACTIONS = ["(all)", "INSERT", "UPDATE", "RETIRE", "BULK_INSERT", "REF_INSERT", "REF_UPDATE"];

export default function ActivityLog({ onClose }: Props) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [action, setAction] = useState("(all)");

  useEffect(() => {
    api.audit().then((r) => setRows(r.rows));
  }, []);

  const filtered = (rows ?? []).filter((r) => action === "(all)" || r.action === action);

  const summarise = (r: AuditRow): string => {
    const after = r.after_json ?? {};
    const bits: string[] = [];
    for (const k of ["vendor_name", "vendor_id", "country_key", "supply_region", "name"]) {
      if (after[k]) bits.push(String(after[k]));
    }
    return bits.join(" · ");
  };

  return (
    <Drawer
      title="Activity log"
      subtitle="Every change — who, what and when. The belt-and-braces record behind the SCD2 history."
      onClose={onClose}
    >
      <div className="inline-form" style={{ marginBottom: 12 }}>
        <div className="field">
          <label>Filter by action</label>
          <select className="filter" value={action} onChange={(e) => setAction(e.target.value)}>
            {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
      </div>

      {rows === null ? (
        <div className="mono">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="empty">No activity recorded yet.</div>
      ) : (
        filtered.map((r) => (
          <div className="audit-item" key={r.audit_id}>
            <div className="top">
              <span className={`action-tag action-${r.action}`}>{r.action}</span>
              <span>{summarise(r) || `${r.domain_key} #${r.record_pk}`}</span>
              <span className="when">{new Date(r.changed_at).toLocaleString()} · {r.changed_by}</span>
            </div>
          </div>
        ))
      )}
    </Drawer>
  );
}
