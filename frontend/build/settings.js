import { jsx as _jsx } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function SettingsPage() {
    return _jsx(PageShell, { title: "AmpAI Settings", description: "Settings page rendered in TSX.", spaRoute: "/#/settings" });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(SettingsPage, {}));
}
