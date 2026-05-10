#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_store::StoreExt;

// ─── Constants ────────────────────────────────────────────────────────────────

const STORE_FILE: &str = "ampai_config.json";
const KEY_SERVER_URL: &str = "server_url";
const KEY_AUTH_TOKEN: &str = "auth_token";

// ─── Shared types ─────────────────────────────────────────────────────────────

/// Returned by `test_server_connection` to the frontend.
#[derive(Debug, Serialize, Deserialize)]
pub struct ServerStatus {
    pub ok: bool,
    pub latency_ms: u64,
    pub server_url: String,
    pub message: String,
}

// ─── Helper ───────────────────────────────────────────────────────────────────

/// Open (or create) the persistent store, returning a human-readable error on
/// failure so every Tauri command can simply call `get_store(&app)?`.
fn get_store(
    app: &tauri::AppHandle,
) -> Result<std::sync::Arc<tauri_plugin_store::Store<tauri::Wry>>, String> {
    app.store(STORE_FILE)
        .map_err(|e| format!("Failed to open store '{STORE_FILE}': {e}"))
}

// ─── Server URL commands ──────────────────────────────────────────────────────

/// Read the saved AmpAI server URL. Returns an empty string when unset.
#[tauri::command]
fn get_server_url(app: tauri::AppHandle) -> String {
    app.store(STORE_FILE)
        .ok()
        .and_then(|store| store.get(KEY_SERVER_URL))
        .and_then(|val| val.as_str().map(String::from))
        .unwrap_or_default()
}

/// Persist the AmpAI server URL.
#[tauri::command]
fn set_server_url(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let store = get_store(&app)?;
    store.set(KEY_SERVER_URL, url);
    store
        .save()
        .map_err(|e| format!("Failed to save store: {e}"))?;
    Ok(())
}

/// Remove the saved AmpAI server URL.
#[tauri::command]
fn clear_server_url(app: tauri::AppHandle) -> Result<(), String> {
    let store = get_store(&app)?;
    store.delete(KEY_SERVER_URL);
    store
        .save()
        .map_err(|e| format!("Failed to save store: {e}"))?;
    Ok(())
}

// ─── Auth token commands ──────────────────────────────────────────────────────

/// Read the saved auth token, or `null` / `None` when not logged in.
#[tauri::command]
fn get_auth_token(app: tauri::AppHandle) -> Option<String> {
    app.store(STORE_FILE)
        .ok()
        .and_then(|store| store.get(KEY_AUTH_TOKEN))
        .and_then(|val| val.as_str().map(String::from))
}

/// Persist the auth token received after login.
#[tauri::command]
fn set_auth_token(app: tauri::AppHandle, token: String) -> Result<(), String> {
    let store = get_store(&app)?;
    store.set(KEY_AUTH_TOKEN, token);
    store
        .save()
        .map_err(|e| format!("Failed to save store: {e}"))?;
    Ok(())
}

/// Remove the saved auth token (logout).
#[tauri::command]
fn clear_auth_token(app: tauri::AppHandle) -> Result<(), String> {
    let store = get_store(&app)?;
    store.delete(KEY_AUTH_TOKEN);
    store
        .save()
        .map_err(|e| format!("Failed to save store: {e}"))?;
    Ok(())
}

// ─── Health-check command ─────────────────────────────────────────────────────

/// Ping `{url}/healthz` with a 5-second timeout and report back.
///
/// The command never returns an `Err` variant to the frontend; all failure
/// scenarios are represented as `ServerStatus { ok: false, … }` so the UI
/// can display a friendly message without special error handling.
#[tauri::command]
async fn test_server_connection(url: String) -> Result<ServerStatus, String> {
    // Normalise the base URL and append the health endpoint.
    let health_url = format!("{}/healthz", url.trim_end_matches('/'));

    // Build a plain reqwest client (no per-client timeout — we control it below).
    let client = reqwest::Client::builder()
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

    let start = std::time::Instant::now();

    // Wrap the request in a 5-second tokio timeout.
    let result = tokio::time::timeout(
        std::time::Duration::from_secs(5),
        client.get(&health_url).send(),
    )
    .await;

    match result {
        // Outer Err => the 5-second deadline expired.
        Err(_elapsed) => Ok(ServerStatus {
            ok: false,
            latency_ms: 5_000,
            server_url: url,
            message: "Connection timed out after 5 seconds".to_string(),
        }),

        // Inner Err => the request itself failed (DNS, TCP refused, TLS, …).
        Ok(Err(req_err)) => Ok(ServerStatus {
            ok: false,
            latency_ms: start.elapsed().as_millis() as u64,
            server_url: url,
            message: format!("Connection failed: {req_err}"),
        }),

        // Got an HTTP response — inspect the status code.
        Ok(Ok(response)) => {
            let latency_ms = start.elapsed().as_millis() as u64;
            let http_status = response.status();

            if http_status.is_success() {
                Ok(ServerStatus {
                    ok: true,
                    latency_ms,
                    server_url: url,
                    message: format!("Server is healthy (HTTP {})", http_status.as_u16()),
                })
            } else {
                Ok(ServerStatus {
                    ok: false,
                    latency_ms,
                    server_url: url,
                    message: format!(
                        "Server returned unexpected status HTTP {}",
                        http_status.as_u16()
                    ),
                })
            }
        }
    }
}

// ─── Utility commands ─────────────────────────────────────────────────────────

/// Return the application version from Cargo metadata.
#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Open a URL in the system's default browser via the shell plugin.
#[tauri::command]
fn open_external_url(app: tauri::AppHandle, url: String) -> Result<(), String> {
    app.shell()
        .open(&url, None::<String>)
        .map_err(|e| format!("Failed to open URL '{url}': {e}"))
}

// ─── Entry point ──────────────────────────────────────────────────────────────

fn main() {
    tauri::Builder::default()
        // ── Plugins ──────────────────────────────────────────────────────────
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_shell::init())
        // ── IPC commands ─────────────────────────────────────────────────────
        .invoke_handler(tauri::generate_handler![
            // Server URL
            get_server_url,
            set_server_url,
            clear_server_url,
            // Auth token
            get_auth_token,
            set_auth_token,
            clear_auth_token,
            // Health check
            test_server_connection,
            // Utilities
            get_app_version,
            open_external_url,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
