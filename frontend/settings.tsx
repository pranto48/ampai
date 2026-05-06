import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function SettingsPage() {
  const [status, setStatus] = React.useState("");
  const [includeSecrets, setIncludeSecrets] = React.useState(false);
  const [importPreview, setImportPreview] = React.useState<any[]>([]);
  const [dryRun, setDryRun] = React.useState(true);
  const [strategy, setStrategy] = React.useState<"skip" | "overwrite">("skip");
  const [filePayload, setFilePayload] = React.useState<any>(null);

  const token = localStorage.getItem("ampai_token") || "";
  const apiFetch = (path: string, options: RequestInit = {}) => fetch(path, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  const onExport = async () => {
    const confirmFlag = includeSecrets && window.confirm("Include secret values in exported JSON?");
    const url = `/api/admin/settings/export?include_secrets=${includeSecrets ? "true" : "false"}&confirm_include_secrets=${confirmFlag ? "true" : "false"}`;
    const res = await apiFetch(url);
    const data = await res.json();
    if (!res.ok) return setStatus(data.detail || "Export failed");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href; a.download = `ampai-settings-${new Date().toISOString()}.json`; a.click();
    URL.revokeObjectURL(href);
    setStatus(`Exported ${data.meta?.exported_key_count || 0} keys.`);
  };
  const onImportFile = async (evt: React.ChangeEvent<HTMLInputElement>) => {
    const file = evt.target.files?.[0]; if (!file) return;
    const payload = JSON.parse(await file.text());
    setFilePayload(payload);
    const res = await apiFetch("/api/admin/settings/import", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ configs: payload.configs || payload, dry_run: true, conflict_strategy: strategy }) });
    const data = await res.json();
    setImportPreview(data.results || []);
    setStatus(`Preview ready: ${(data.results || []).length} keys.`);
  };
  const runImport = async () => {
    if (!filePayload) return;
    const res = await apiFetch("/api/admin/settings/import", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ configs: filePayload.configs || filePayload, dry_run: dryRun, conflict_strategy: strategy }) });
    const data = await res.json();
    setImportPreview(data.results || []);
    setStatus(`Import complete (${dryRun ? "dry-run" : "applied"}).`);
  };
  return <div><PageShell title="AmpAI Settings" description="Settings page rendered in TSX." spaRoute="/#/settings" />
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h3>Admin Settings Export/Import</h3>
      <label><input type="checkbox" checked={includeSecrets} onChange={(e) => setIncludeSecrets(e.target.checked)} /> Include secrets (requires confirmation)</label>
      <button onClick={onExport}>Download JSON</button>
      <div>
        <input type="file" accept="application/json" onChange={onImportFile} />
        <label><input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} /> Dry-run</label>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value as any)}><option value="skip">Skip conflicts</option><option value="overwrite">Overwrite conflicts</option></select>
        <button onClick={runImport}>Run Import</button>
      </div>
      <p>{status}</p>
      <pre style={{ maxHeight: 220, overflow: "auto", background: "#0f172a", padding: 8 }}>{JSON.stringify(importPreview.slice(0, 50), null, 2)}</pre>
    </div>
  </div>;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<SettingsPage />);
}
