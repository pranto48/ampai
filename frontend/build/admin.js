import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function AdminPage() {
    return _jsxs("div", { children: [_jsx(PageShell, { title: "AmpAI Admin", description: "Admin area rendered in TSX.", spaRoute: "/#/admin" }), _jsxs("div", { style: { maxWidth: 900, margin: "0 auto", padding: 16 }, children: [_jsx("p", { children: "Use the Settings page export/import controls to download and upload admin config JSON with changed-key preview." }), _jsx("a", { href: "/settings", children: "Open Settings page" })] })] });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(AdminPage, {}));
}
