const { useState, useEffect, useCallback } = React;

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

function useConfig() {
  const [cfg, setCfg] = useState(() => ({
    baseUrl: localStorage.getItem("kavach.baseUrl") || "http://localhost:8000",
    token: localStorage.getItem("kavach.token") || "operator-dev-token",
    tenant: localStorage.getItem("kavach.tenant") || "bank-1",
  }));
  const update = (patch) => {
    const next = { ...cfg, ...patch };
    setCfg(next);
    localStorage.setItem("kavach.baseUrl", next.baseUrl);
    localStorage.setItem("kavach.token", next.token);
    localStorage.setItem("kavach.tenant", next.tenant);
  };
  return [cfg, update];
}

async function api(cfg, method, path, body) {
  const headers = {
    Authorization: `Bearer ${cfg.token}`,
    "X-Kavach-Tenant": cfg.tenant,
    "X-Kavach-Operator": "console",
  };
  if (body) headers["Content-Type"] = "application/json";
  const resp = await fetch(`${cfg.baseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data && (data.detail || data.title) ? `: ${data.detail || data.title}` : "";
    throw new Error(`${resp.status}${detail}`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function Badge({ kind, children }) {
  return <span className={`badge ${kind}`}>{children || kind}</span>;
}

function ErrorLine({ error }) {
  return error ? <div className="error">⚠ {error}</div> : null;
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

function Timeline({ cfg }) {
  const [agent, setAgent] = useState("agent-cs-01");
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api(cfg, "GET", `/v1/agents/${encodeURIComponent(agent)}/timeline`);
      setItems(data.items);
    } catch (e) {
      setError(e.message);
      setItems([]);
    }
  }, [cfg, agent]);

  return (
    <div className="card">
      <h2>Agent timeline</h2>
      <p className="sub">Every recorded action, decision, and step-up for an agent.</p>
      <div className="row">
        <input value={agent} onChange={(e) => setAgent(e.target.value)} placeholder="agent id" />
        <button className="primary" onClick={load}>Load</button>
      </div>
      <ErrorLine error={error} />
      {items.length === 0 && !error ? <div className="empty">No activity loaded.</div> : null}
      {items.map((it) => (
        <div className="item" key={it.event_id}>
          <div className="meta">
            <span className="title">{it.summary}</span>
            <span className="when">{it.event_type} · {new Date(it.occurred_at).toLocaleString()}</span>
          </div>
          {it.outcome ? <Badge kind={it.outcome}>{it.outcome}</Badge> : null}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trust
// ---------------------------------------------------------------------------

function Trust({ cfg }) {
  const [agent, setAgent] = useState("agent-cs-01");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await api(cfg, "GET", `/v1/agents/${encodeURIComponent(agent)}/trust`);
      setData(d);
    } catch (e) {
      setError(e.message);
      setData(null);
    }
  }, [cfg, agent]);

  return (
    <div className="card">
      <h2>Trust assessment</h2>
      <p className="sub">Multidimensional trust tensor with per-dimension data sufficiency.</p>
      <div className="row">
        <input value={agent} onChange={(e) => setAgent(e.target.value)} placeholder="agent id" />
        <button className="primary" onClick={load}>Load</button>
      </div>
      <ErrorLine error={error} />
      {data ? (
        <div>
          {data.composed_scalar != null ? (
            <div style={{ marginBottom: 18 }}>
              <span className="scalar">{(data.composed_scalar * 100).toFixed(0)}<small> / 100 composed</small></span>
            </div>
          ) : null}
          {Object.entries(data.dimensions).map(([name, dim]) => (
            <div className="dim" key={name}>
              <div className="dim-head">
                <span>{name} <Badge kind={dim.sufficiency.band}>{dim.sufficiency.band}</Badge></span>
                <span>{(dim.value * 100).toFixed(0)}</span>
              </div>
              <div className="bar"><span style={{ width: `${dim.value * 100}%` }} /></div>
              <div className="reason">{dim.reason}</div>
            </div>
          ))}
        </div>
      ) : (!error ? <div className="empty">No assessment loaded.</div> : null)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step-up queue
// ---------------------------------------------------------------------------

function StepUps({ cfg }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await api(cfg, "GET", "/v1/step-ups");
      setItems(d.items);
    } catch (e) {
      setError(e.message);
      setItems([]);
    }
  }, [cfg]);

  useEffect(() => { load(); }, [load]);

  const resolve = async (decisionId, resolution) => {
    setError(null);
    try {
      await api(cfg, "POST", `/v1/decisions/${decisionId}/step-up/resolve`, {
        resolution,
        operator_id: "console",
        rationale: `${resolution} via console`,
      });
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="card">
      <h2>Step-up queue <Badge kind="step_up">{items.length} pending</Badge></h2>
      <p className="sub">Human-in-the-loop approvals (EU AI Act Article 14).</p>
      <div className="row"><button className="ghost" onClick={load}>Refresh</button></div>
      <ErrorLine error={error} />
      {items.length === 0 && !error ? <div className="empty">Queue is clear.</div> : null}
      {items.map((it) => (
        <div className="item" key={it.decision_id}>
          <div className="meta">
            <span className="title">{it.action_type} — {it.reason}</span>
            <span className="when">{it.agent_id} · role {it.required_role} · {new Date(it.requested_at).toLocaleString()}</span>
          </div>
          <div>
            <button className="approve" onClick={() => resolve(it.decision_id, "approve")}>Approve</button>
            <button className="reject" onClick={() => resolve(it.decision_id, "reject")}>Reject</button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence export
// ---------------------------------------------------------------------------

function Evidence({ cfg }) {
  const [agent, setAgent] = useState("agent-cs-01");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setError(null);
    try {
      const now = new Date();
      const past = new Date(now.getTime() - 24 * 3600 * 1000);
      const future = new Date(now.getTime() + 3600 * 1000);
      const d = await api(cfg, "POST", "/v1/audit/exports", {
        agent_id: agent,
        from: past.toISOString(),
        to: future.toISOString(),
      });
      setData(d);
    } catch (e) {
      setError(e.message);
      setData(null);
    }
  }, [cfg, agent]);

  return (
    <div className="card">
      <h2>Evidence export</h2>
      <p className="sub">HMAC-SHA256 chained, signed audit pack (EU AI Act Articles 12 & 13).</p>
      <div className="row">
        <input value={agent} onChange={(e) => setAgent(e.target.value)} placeholder="agent id" />
        <button className="primary" onClick={run}>Export &amp; sign</button>
      </div>
      <ErrorLine error={error} />
      {data ? (
        <div>
          <div className="row">
            <Badge kind="warm">{data.record_count} records</Badge>
            {data.signature_manifest ? <span className="verify-ok">✓ signed ({data.signature_manifest.algorithm})</span> : <span className="empty">no records</span>}
          </div>
          {data.signature_manifest ? (
            <p className="sub">key id <code className="hash">{data.signature_manifest.key_id}</code><br/>chain head <code className="hash">{data.signature_manifest.chain_head}</code></p>
          ) : null}
          <table>
            <thead><tr><th>#</th><th>event</th><th>this_hash</th></tr></thead>
            <tbody>
              {data.records.map((r) => (
                <tr key={r.event_id}>
                  <td>{r.position}</td>
                  <td>{r.event_type}</td>
                  <td><code className="hash">{r.this_hash.slice(0, 24)}…</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

const TABS = [
  { id: "timeline", label: "Timeline", render: (cfg) => <Timeline cfg={cfg} /> },
  { id: "trust", label: "Trust", render: (cfg) => <Trust cfg={cfg} /> },
  { id: "stepups", label: "Step-up queue", render: (cfg) => <StepUps cfg={cfg} /> },
  { id: "evidence", label: "Evidence export", render: (cfg) => <Evidence cfg={cfg} /> },
];

function App() {
  const [cfg, update] = useConfig();
  const [tab, setTab] = useState("timeline");
  const active = TABS.find((t) => t.id === tab);
  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          Kavach <small>Operator Console</small>
        </div>
        <input value={cfg.baseUrl} onChange={(e) => update({ baseUrl: e.target.value })} placeholder="API base URL" style={{ minWidth: 220 }} />
        <input value={cfg.tenant} onChange={(e) => update({ tenant: e.target.value })} placeholder="tenant" style={{ width: 110 }} />
        <input value={cfg.token} onChange={(e) => update({ token: e.target.value })} placeholder="operator token" type="password" style={{ minWidth: 180 }} />
      </header>
      <div className="layout">
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={t.id === tab ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <main>{active.render(cfg)}</main>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
