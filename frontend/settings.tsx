import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function SettingsPage() {
  return <PageShell title="AmpAI Settings" description="Settings page rendered in TSX." spaRoute="/index.html#/settings" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<SettingsPage />);
}
