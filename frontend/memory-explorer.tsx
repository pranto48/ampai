import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function MemoryExplorerPage() {
  return <PageShell title="AmpAI Memory Explorer" description="Memory explorer page rendered in TSX." spaRoute="/index.html#/memory" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<MemoryExplorerPage />);
}
