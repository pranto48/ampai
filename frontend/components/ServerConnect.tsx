import React, { useEffect, useState } from 'react';
import { isDesktopApp, getServerUrl, setServerUrl } from '../api-client';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  /** Called once the server URL has been saved and the app is ready to proceed. */
  onConnected: () => void;
}

interface TestResult {
  ok: boolean;
  message: string;
}

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
export default function ServerConnect({ onConnected }: Props) {
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
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
      } else {
        setTestResult({
          ok: false,
          message: `Server responded with status ${res.status} — is this the right URL?`,
        });
      }
    } catch (err) {
      setTestResult({
        ok: false,
        message: `Could not connect: ${err instanceof Error ? err.message : 'Network error'}`,
      });
    } finally {
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

  const overlay: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    background: '#1a1a2e',
    fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
  };

  const card: React.CSSProperties = {
    width: '100%',
    maxWidth: 480,
    padding: '48px 40px',
    background: 'rgba(15, 23, 42, 0.95)',
    border: '1px solid rgba(148, 163, 184, 0.15)',
    borderRadius: 16,
    boxShadow: '0 25px 50px rgba(0, 0, 0, 0.5)',
  };

  const logoWrap: React.CSSProperties = {
    textAlign: 'center',
    marginBottom: 36,
  };

  const logoIcon: React.CSSProperties = {
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

  const titleStyle: React.CSSProperties = {
    margin: '0 0 8px',
    fontSize: 24,
    fontWeight: 700,
    color: '#e2e8f0',
  };

  const subtitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: 15,
    color: '#94a3b8',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: 13,
    fontWeight: 600,
    color: '#94a3b8',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  const inputStyle: React.CSSProperties = {
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

  const helpText: React.CSSProperties = {
    margin: '8px 0 24px',
    fontSize: 13,
    color: '#64748b',
    lineHeight: 1.5,
  };

  const statusBox = (ok: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '10px 14px',
    borderRadius: 8,
    marginBottom: 16,
    background: ok ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)',
    border: `1px solid ${ok ? '#059669' : '#dc2626'}`,
  });

  const statusIcon: React.CSSProperties = {
    fontSize: 15,
    lineHeight: 1.6,
    flexShrink: 0,
  };

  const statusText = (ok: boolean): React.CSSProperties => ({
    fontSize: 13,
    color: ok ? '#6ee7b7' : '#fca5a5',
    lineHeight: 1.5,
  });

  const errorBox: React.CSSProperties = {
    padding: '10px 14px',
    borderRadius: 8,
    marginBottom: 16,
    background: 'rgba(220, 38, 38, 0.15)',
    border: '1px solid #dc2626',
    color: '#fca5a5',
    fontSize: 13,
  };

  const btnRow: React.CSSProperties = {
    display: 'flex',
    gap: 10,
    marginTop: 4,
  };

  const btnSecondary = (disabled: boolean): React.CSSProperties => ({
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

  const btnPrimary: React.CSSProperties = {
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

  return (
    <div style={overlay}>
      <div style={card}>

        {/* ── Branding ──────────────────────────────────────────────────── */}
        <div style={logoWrap}>
          <div style={logoIcon} aria-hidden="true">⚡</div>
          <h1 style={titleStyle}>AmpAI Desktop</h1>
          <p style={subtitleStyle}>Connect to your AmpAI Docker Server</p>
        </div>

        {/* ── Server URL input ──────────────────────────────────────────── */}
        <label style={labelStyle} htmlFor="ampai-server-url">
          Server URL
        </label>
        <input
          id="ampai-server-url"
          type="url"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            // Clear stale test results and errors as the user types
            setTestResult(null);
            setError('');
          }}
          onKeyDown={(e) => { if (e.key === 'Enter') handleConnect(); }}
          placeholder="http://192.168.1.100:8001"
          autoFocus
          autoComplete="url"
          spellCheck={false}
          style={inputStyle}
        />

        <p style={helpText}>
          Enter the URL of your AmpAI Docker server. Default port is{' '}
          <strong style={{ color: '#94a3b8' }}>8001</strong>.
        </p>

        {/* ── Test result banner ────────────────────────────────────────── */}
        {testResult && (
          <div style={statusBox(testResult.ok)} role="status">
            <span style={statusIcon}>{testResult.ok ? '✅' : '❌'}</span>
            <span style={statusText(testResult.ok)}>{testResult.message}</span>
          </div>
        )}

        {/* ── Validation error ──────────────────────────────────────────── */}
        {error && (
          <div style={errorBox} role="alert">
            {error}
          </div>
        )}

        {/* ── Action buttons ────────────────────────────────────────────── */}
        <div style={btnRow}>
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testing}
            style={btnSecondary(testing)}
          >
            {testing ? 'Testing…' : 'Test Connection'}
          </button>

          <button
            type="button"
            onClick={handleConnect}
            style={btnPrimary}
          >
            Connect
          </button>
        </div>

      </div>
    </div>
  );
}
