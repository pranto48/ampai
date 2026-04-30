import { jsx as _jsx } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function AdminPage() {
    return _jsx(PageShell, { title: "AmpAI Admin", description: "Admin area rendered in TSX.", spaRoute: "/#/admin" });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(AdminPage, {}));
}
