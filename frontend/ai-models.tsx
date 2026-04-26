import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function AIModelsPage() {
  return <PageShell title="AmpAI AI Models" description="AI models page rendered in TSX." spaRoute="/#/models" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<AIModelsPage />);
}
