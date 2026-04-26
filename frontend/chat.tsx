import React from "react";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";

export default function ChatPage() {
  return <PageShell title="AmpAI Chat" description="Chat entry page rendered in TSX." spaRoute="/#/chat" />;
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<ChatPage />);
}
