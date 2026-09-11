import { useEffect, useMemo, useState } from "react";
import { api, setViewAsRole } from "./api";
import type { Bootstrap, Coverage, Row } from "./types";
import EditorPanel from "./components/EditorPanel";
import ManageLists from "./components/ManageLists";
import BulkLoad from "./components/BulkLoad";
import ActivityLog from "./components/ActivityLog";

const COLUMN_LABELS: Record<string, string> = {
  mapping_id: "ID",
  vendor_id: "Vendor ID",
  vendor_name: "Vendor",
  supply_region: "Supply Region",
  supply_method: "Supply Method",
  merchandise_category: "Merchandise Category",
  status: "Status",
  updated_by: "Last changed by",
  updated_at: "Last changed at",
};

type Drawer = null | "lists" | "bulk" | "activity";

export default function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [statusFilter, setStatusFilter] = useState("(all)");

  const [selected, setSelected] = useState<Row | null>(null);
  const [creating, setCreating] = useState(false);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null);

  const panelOpen = creating || selected != null;

  const showToast = (msg: string, err = false) => {
    setToast({ msg, err });
    window.setTimeout(() => setToast(null), 3200);
  };

  const loadData = async () => {
    const res = await api.list();
    setRows(res.rows);
    setCoverage(res.coverage);
  };

  useEffect(() => {
    api
      .bootstrap()
      .then(async (b) => {
        setBoot(b);
        await loadData();
      })
      .catch((e) => setLoadError(e.message ?? "Failed to load."));
  }, []);

  const domain = boot?.domain;

  const filtered = useMemo(() => {
    if (!domain) return [];
    let view = rows;
    for (const [f, val] of Object.entries(filters)) {
      if (val && val !== "(all)") view = view.filter((r) => String(r[f]) === val);
    }
    if (statusFilter !== "(all)") view = view.filter((r) => r.status === statusFilter);
    const q = search.trim().toLowerCase();
    if (q) {
      view = view.filter((r) =>
        domain.search_fields.some((s) => String(r[s] ?? "").toLowerCase().includes(q))
      );
    }
    return view;
  }, [rows, filters, statusFilter, search, domain]);

  const kpis = useMemo(() => {
    const total = rows.length;
    const active = rows.filter((r) => r.status === "Active").length;
    const future = rows.filter((r) => r.status === "Future").length;
    const expired = rows.filter((r) => r.status === "Expired").length;
    return { total, active, future, expired, gaps: coverage?.gaps.length ?? 0 };
  }, [rows, coverage]);

  const afterWrite = async (msg: string) => {
    await loadData();
    setSelected(null);
    setCreating(false);
    showToast(msg);
  };

  const fmt = (col: string, v: any) => {
    if (v == null || v === "") return "—";
    if (col === "updated_at" || col === "created_at") return new Date(v).toLocaleString();
    if (col === "status") return <span className={`pill ${v}`}>{v}</span>;
    return String(v);
  };

  const exportCsv = () => {
    if (!domain) return;
    const cols = domain.list_columns;
    const head = cols.map((c) => COLUMN_LABELS[c] ?? c).join(",");
    const esc = (s: any) => {
      const str = s == null ? "" : String(s);
      return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
    const body = filtered.map((r) => cols.map((c) => esc(r[c])).join(",")).join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vendor_supply_authorisation_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const changeRole = (role: string) => {
    if (!boot) return;
    setViewAsRole(role);
    setBoot({ ...boot, me: { ...boot.me, role, is_admin: role === "Administrator" } });
    setDrawer(null);
  };

  if (loadError) {
    return (
      <div className="app">
        <Header boot={null} onRole={() => {}} onDrawer={() => {}} />
        <div className="center-fill" style={{ flexDirection: "column", gap: 12, padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--tertiary)" }}>Can't reach the data</div>
          <div style={{ maxWidth: 460 }}>{loadError}</div>
        </div>
      </div>
    );
  }

  if (!boot || !domain) {
    return (
      <div className="app">
        <Header boot={null} onRole={() => {}} onDrawer={() => {}} />
        <div className="center-fill"><div className="spinner" /></div>
      </div>
    );
  }

  const isAdmin = boot.me.is_admin;

  return (
    <div className="app">
      <Header boot={boot} onRole={changeRole} onDrawer={setDrawer} />

      {coverage && coverage.gaps.length > 0 && (
        <div className="banner">
          <span>⚠</span>
          <b>{coverage.gaps.length} region{coverage.gaps.length > 1 ? "s" : ""}</b>
          <span>with no active authorisation — stores here can hit silent ordering failures:</span>
          {coverage.gaps.map((g) => (
            <button
              key={g}
              className="chip"
              onClick={() => {
                setFilters((f) => ({ ...f, [coverage.dimension!]: g }));
                setStatusFilter("(all)");
              }}
            >
              {g}
            </button>
          ))}
        </div>
      )}

      <div className="kpis">
        <div className="kpi"><div className="v">{kpis.total}</div><div className="l">Authorisations</div></div>
        <div className="kpi"><div className="v">{kpis.active}</div><div className="l">Active</div></div>
        <div className="kpi warn"><div className="v">{kpis.future}</div><div className="l">Future-dated</div></div>
        <div className="kpi bad"><div className="v">{kpis.expired}</div><div className="l">Expired</div></div>
        <div className={`kpi ${kpis.gaps ? "bad" : ""}`}><div className="v">{kpis.gaps}</div><div className="l">Coverage gaps</div></div>
      </div>

      <div className="work">
        <div className="grid-wrap">
          <div className="toolbar">
            <input
              className="search"
              placeholder={`Search ${domain.search_fields.map((s) => COLUMN_LABELS[s] ?? s).join(" / ")}…`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {domain.filter_fields.map((f) => (
              <select
                key={f}
                className="filter"
                value={filters[f] ?? "(all)"}
                onChange={(e) => setFilters((s) => ({ ...s, [f]: e.target.value }))}
              >
                <option value="(all)">{COLUMN_LABELS[f] ?? f}: all</option>
                {(boot.lookups[f] ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ))}
            <select className="filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              {["(all)", "Active", "Future", "Expired"].map((s) => (
                <option key={s} value={s}>{s === "(all)" ? "Status: all" : s}</option>
              ))}
            </select>
            <button className="btn" onClick={() => { setSelected(null); setCreating(true); }}>+ New</button>
            <button className="btn ghost sm" onClick={exportCsv}>Export CSV</button>
          </div>

          <div className="grid-scroll">
            {filtered.length === 0 ? (
              <div className="empty">No authorisations match your filters.</div>
            ) : (
              <table className="grid">
                <thead>
                  <tr>{domain.list_columns.map((c) => <th key={c}>{COLUMN_LABELS[c] ?? c}</th>)}</tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr
                      key={r.mapping_id}
                      className={selected?.mapping_id === r.mapping_id ? "sel" : ""}
                      onClick={() => { setCreating(false); setSelected(r); }}
                    >
                      {domain.list_columns.map((c) => (
                        <td key={c} className={c === "mapping_id" ? "mono" : ""}>{fmt(c, r[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="tbl-meta">
            <span>Showing {filtered.length} of {rows.length}</span>
            {domain.uc_target && <span className="mono">Governed target: {domain.uc_target}</span>}
          </div>
        </div>

        <div className={`panel ${panelOpen ? "open" : ""}`}>
          {panelOpen && (
            <EditorPanel
              boot={boot}
              row={creating ? null : selected}
              onClose={() => { setSelected(null); setCreating(false); }}
              onSaved={afterWrite}
            />
          )}
        </div>
      </div>

      {drawer === "lists" && isAdmin && (
        <ManageLists
          boot={boot}
          onClose={() => setDrawer(null)}
          onChanged={async (m) => { await refreshLookups(boot, setBoot); await loadData(); showToast(m); }}
        />
      )}
      {drawer === "bulk" && isAdmin && (
        <BulkLoad boot={boot} onClose={() => setDrawer(null)} onCommitted={afterWrite} />
      )}
      {drawer === "activity" && <ActivityLog onClose={() => setDrawer(null)} />}

      {toast && <div className={`toast ${toast.err ? "err" : ""}`}>{toast.msg}</div>}
    </div>
  );
}

async function refreshLookups(boot: Bootstrap, setBoot: (b: Bootstrap) => void) {
  const fresh = await api.bootstrap();
  setBoot({ ...fresh, me: boot.me });
}

function Header({
  boot,
  onRole,
  onDrawer,
}: {
  boot: Bootstrap | null;
  onRole: (r: string) => void;
  onDrawer: (d: Drawer) => void;
}) {
  const isAdmin = boot?.me.is_admin ?? false;
  return (
    <div className="hdr">
      <img className="mark-img" src={`${import.meta.env.BASE_URL}logo.webp`} alt="7-Eleven" />
      <div className="hdr-title">
        <div className="t1">Article Master</div>
        <div className="t2">Vendor Supply Authorisation · Control Plane</div>
      </div>
      <div className="hdr-spacer" />
      {boot && (
        <div className="hdr-actions">
          <button className="hdr-btn" onClick={() => onDrawer("activity")}>Activity log</button>
          {isAdmin && <button className="hdr-btn" onClick={() => onDrawer("lists")}>Manage lists</button>}
          {isAdmin && <button className="hdr-btn" onClick={() => onDrawer("bulk")}>Bulk load</button>}
          <div className="hdr-user">
            <span className="who">{boot.me.user}</span>
            <select
              className="role-select"
              value={boot.me.role}
              onChange={(e) => onRole(e.target.value)}
              title="Demo: view the app as either role"
            >
              {boot.me.roles.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
