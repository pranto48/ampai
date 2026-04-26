import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function AdminPage() {
  return <PageShell title="AmpAI Admin" description="Admin area rendered in TSX." spaRoute="/#/admin" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<AdminPage />);
}
