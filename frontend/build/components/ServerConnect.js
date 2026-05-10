import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { isDesktopApp, getServerUrl, setServerUrl } from '../api-client';
// ─── Component ─────────────────────────────────────────────────────────────────
/**
 * First-run connection screen shown when the Tauri desktop app starts and no
 * Docker server URL has been configured yet.
 *
 * Rendering behaviour:
 *  - Returns `null` (and immediately fires `onConnected`) if we are NOT inside
 *    Tauri, or if a server URL is already stored in localStorage.
 *  - Otherwise, renders a full-screen setup wizard that lets the user enter,
 *    test, and save the Docker server URL.
 */
export default function ServerConnect({ onConnected }) {
    const [url, setUrl] = useState('');
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState(null);
    const [error, setError] = useState('');
    /**
     * On mount: if we're not in Tauri OR a URL is already stored, skip this
     * screen and hand control back to the parent immediately.
     */
    useEffect(() => {
        if (!isDesktopApp() || getServerUrl()) {
            onConnected();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    // Synchronous guard — avoids a flash of the UI before the effect fires.
    if (!isDesktopApp() || getServerUrl()) {
        return null;
    }
    // ─── Handlers ───────────────────────────────────────────────────────────────
    /** Probe the /healthz endpoint of the entered URL and show the result. */
    async function handleTestConnection() {
        const trimmed = url.trim();
        if (!trimmed) {
            setError('Please enter a server URL first.');
            return;
        }
        setError('');
        setTestResult(null);
        setTesting(true);
        try {
            const res = await fetch(`${trimmed.replace(/\/+$/, '')}/healthz`);
            if (res.ok) {
                setTestResult({
                    ok: true,
                    message: 'Connection successful! Server is reachable.',
                });
            }
            else {
                setTestResult({
                    ok: false,
                    message: `Server responded with status ${res.status} — is this the right URL?`,
                });
            }
        }
        catch (err) {
            setTestResult({
                ok: false,
                message: `Could not connect: ${err instanceof Error ? err.message : 'Network error'}`,
            });
        }
        finally {
            setTesting(false);
        }
    }
    /** Validate the URL, persist it to localStorage, then call onConnected(). */
    function handleConnect() {
        const trimmed = url.trim();
        if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
            setError('URL must start with http:// or https://');
            return;
        }
        setError('');
        setServerUrl(trimmed);
        onConnected();
    }
    // ─── Inline styles ───────────────────────────────────────────────────────────
    const overlay = {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#1a1a2e',
        fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
    };
    const card = {
        width: '100%',
        maxWidth: 480,
        padding: '48px 40px',
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: 16,
        boxShadow: '0 25px 50px rgba(0, 0, 0, 0.5)',
    };
    const logoWrap = {
        textAlign: 'center',
        marginBottom: 36,
    };
    const logoIcon = {
        width: 64,
        height: 64,
        borderRadius: 16,
        background: 'linear-gradient(135deg, #4a90d9 0%, #7b5ea7 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 28,
        margin: '0 auto 16px',
        userSelect: 'none',
    };
    const titleStyle = {
        margin: '0 0 8px',
        fontSize: 24,
        fontWeight: 700,
        color: '#e2e8f0',
    };
    const subtitleStyle = {
        margin: 0,
        fontSize: 15,
        color: '#94a3b8',
    };
    const labelStyle = {
        display: 'block',
        fontSize: 13,
        fontWeight: 600,
        color: '#94a3b8',
        marginBottom: 8,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
    };
    const inputStyle = {
        width: '100%',
        boxSizing: 'border-box',
        padding: '12px 14px',
        borderRadius: 8,
        border: '1px solid #334155',
        background: '#020617',
        color: '#f8fafc',
        fontSize: 15,
        outline: 'none',
        fontFamily: 'inherit',
    };
    const helpText = {
        margin: '8px 0 24px',
        fontSize: 13,
        color: '#64748b',
        lineHeight: 1.5,
    };
    const statusBox = (ok) => ({
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 8,
        marginBottom: 16,
        background: ok ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)',
        border: `1px solid ${ok ? '#059669' : '#dc2626'}`,
    });
    const statusIcon = {
        fontSize: 15,
        lineHeight: 1.6,
        flexShrink: 0,
    };
    const statusText = (ok) => ({
        fontSize: 13,
        color: ok ? '#6ee7b7' : '#fca5a5',
        lineHeight: 1.5,
    });
    const errorBox = {
        padding: '10px 14px',
        borderRadius: 8,
        marginBottom: 16,
        background: 'rgba(220, 38, 38, 0.15)',
        border: '1px solid #dc2626',
        color: '#fca5a5',
        fontSize: 13,
    };
    const btnRow = {
        display: 'flex',
        gap: 10,
        marginTop: 4,
    };
    const btnSecondary = (disabled) => ({
        flex: 1,
        padding: '11px 16px',
        borderRadius: 8,
        border: '1px solid #334155',
        background: '#1e293b',
        color: '#e2e8f0',
        fontWeight: 600,
        fontSize: 14,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.65 : 1,
        transition: 'background 0.15s, opacity 0.15s',
        fontFamily: 'inherit',
    });
    const btnPrimary = {
        flex: 1,
        padding: '11px 16px',
        borderRadius: 8,
        border: 'none',
        background: '#4a90d9',
        color: '#fff',
        fontWeight: 600,
        fontSize: 14,
        cursor: 'pointer',
        transition: 'background 0.15s',
        fontFamily: 'inherit',
    };
    // ─── Render ──────────────────────────────────────────────────────────────────
    return (_jsx("div", { style: overlay, children: _jsxs("div", { style: card, children: [_jsxs("div", { style: logoWrap, children: [_jsx("div", { style: logoIcon, "aria-hidden": "true", children: "\u26A1" }), _jsx("h1", { style: titleStyle, children: "AmpAI Desktop" }), _jsx("p", { style: subtitleStyle, children: "Connect to your AmpAI Docker Server" })] }), _jsx("label", { style: labelStyle, htmlFor: "ampai-server-url", children: "Server URL" }), _jsx("input", { id: "ampai-server-url", type: "url", value: url, onChange: (e) => {
                        setUrl(e.target.value);
                        // Clear stale test results and errors as the user types
                        setTestResult(null);
                        setError('');
                    }, onKeyDown: (e) => { if (e.key === 'Enter')
                        handleConnect(); }, placeholder: "http://192.168.1.100:8001", autoFocus: true, autoComplete: "url", spellCheck: false, style: inputStyle }), _jsxs("p", { style: helpText, children: ["Enter the URL of your AmpAI Docker server. Default port is", ' ', _jsx("strong", { style: { color: '#94a3b8' }, children: "8001" }), "."] }), testResult && (_jsxs("div", { style: statusBox(testResult.ok), role: "status", children: [_jsx("span", { style: statusIcon, children: testResult.ok ? '✅' : '❌' }), _jsx("span", { style: statusText(testResult.ok), children: testResult.message })] })), error && (_jsx("div", { style: errorBox, role: "alert", children: error })), _jsxs("div", { style: btnRow, children: [_jsx("button", { type: "button", onClick: handleTestConnection, disabled: testing, style: btnSecondary(testing), children: testing ? 'Testing…' : 'Test Connection' }), _jsx("button", { type: "button", onClick: handleConnect, style: btnPrimary, children: "Connect" })] })] }) }));
}
