import { useRef, useState } from "react";
import { api } from "../api";
import { parseCsv } from "../csv";
import type { Bootstrap } from "../types";
import Drawer from "./Drawer";

interface Props {
  boot: Bootstrap;
  onClose: () => void;
  onCommitted: (msg: string) => void;
}

type Check = {
  valid: number;
  total: number;
  problems: { row: number; errors: string[] }[];
  expected_columns: string[];
};

export default function BulkLoad({ boot, onClose, onCommitted }: Props) {
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [fileName, setFileName] = useState<string | null>(null);
  const [check, setCheck] = useState<Check | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const expected = boot.domain.fields.map((f) => f.name);

  const onFile = async (file: File) => {
    const text = await file.text();
    const parsed = parseCsv(text);
    setFileName(file.name);
    setRows(parsed);
    setCheck(null);
    if (parsed.length) {
      setBusy(true);
      const res = await api.bulkValidate(parsed);
      setCheck(res);
      setBusy(false);
    }
  };

  const commit = async () => {
    setBusy(true);
    const res = await api.bulkCommit(rows);
    setBusy(false);
    if (res.ok) onCommitted(`Committed ${res.committed} authorisations.`);
    else setCheck((c) => (c ? { ...c, problems: res.problems ?? c.problems } : c));
  };

  const headers = rows.length ? Object.keys(rows[0]) : [];

  return (
    <Drawer
      title="Bulk / seed load"
      subtitle="Upload a CSV to seed or extend the mapping. Every row is validated before anything commits."
      onClose={onClose}
    >
      <div className="card">
        <h4>1 · Choose a CSV</h4>
        <p className="note">
          Expected columns: <b>{expected.join(", ")}</b>. Effective dates are set automatically —
          don't include them.
        </p>
        <input
          ref={fileInput}
          type="file"
          accept=".csv,text/csv"
          style={{ display: "none" }}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <div className="dropzone" onClick={() => fileInput.current?.click()}>
          {fileName ? <b>{fileName}</b> : "Click to choose a CSV file"}
          <div style={{ fontSize: 12, marginTop: 4 }}>{rows.length ? `${rows.length} data rows` : ""}</div>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="card">
          <h4>2 · Preview & validation</h4>
          {busy && <div className="mono">Validating…</div>}
          {check && (
            <>
              {check.problems.length === 0 ? (
                <div className="val-box ok">✓ All {check.valid} rows valid and ready to commit.</div>
              ) : (
                <div className="val-box err">
                  <b>{check.problems.length} row(s) need fixing</b> ({check.valid} of {check.total} valid).
                  <ul>
                    {check.problems.slice(0, 20).map((p) => (
                      <li key={p.row}>Row {p.row}: {p.errors.join("; ")}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          <div style={{ overflowX: "auto", marginTop: 8 }}>
            <table className="mini">
              <thead>
                <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {rows.slice(0, 25).map((r, i) => (
                  <tr key={i}>{headers.map((h) => <td key={h}>{r[h]}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > 25 && <div className="mono" style={{ marginTop: 6 }}>…and {rows.length - 25} more rows</div>}
        </div>
      )}

      {check && check.problems.length === 0 && (
        <button className="btn" disabled={busy} onClick={commit}>
          Commit {check.valid} rows
        </button>
      )}
    </Drawer>
  );
}
