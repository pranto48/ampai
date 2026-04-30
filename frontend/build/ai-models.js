import { jsx as _jsx } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function AIModelsPage() {
    return _jsx(PageShell, { title: "AmpAI AI Models", description: "AI models page rendered in TSX.", spaRoute: "/#/models" });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(AIModelsPage, {}));
}
