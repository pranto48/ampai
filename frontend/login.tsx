import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function LoginPage() {
  return <PageShell title="AmpAI Login" description="Login entry page rendered in TSX." spaRoute="/index.html#/login" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<LoginPage />);
}
