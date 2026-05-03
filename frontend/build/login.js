import { jsx as _jsx } from "react/jsx-runtime";
import { createRoot } from "react-dom/client";
import { PageShell } from "./PageShell";
export default function LoginPage() {
    return _jsx(PageShell, { title: "AmpAI Login", description: "Login entry page rendered in TSX.", spaRoute: "/#/login" });
}
const rootEl = document.getElementById("root");
if (rootEl) {
    createRoot(rootEl).render(_jsx(LoginPage, {}));
}
