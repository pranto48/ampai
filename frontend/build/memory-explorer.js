import { jsx as _jsx } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function MemoryExplorerPage() {
    return _jsx(PageShell, { title: "AmpAI Memory Explorer", description: "Memory explorer page rendered in TSX.", spaRoute: "/#/memory" });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(MemoryExplorerPage, {}));
}
