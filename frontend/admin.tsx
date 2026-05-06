import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function AdminPage() {
  return <div>
    <PageShell title="AmpAI Admin" description="Admin area rendered in TSX." spaRoute="/#/admin" />
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <p>Use the Settings page export/import controls to download and upload admin config JSON with changed-key preview.</p>
      <a href="/settings">Open Settings page</a>
    </div>
  </div>;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<AdminPage />);
}
