# Implementation Plan: UI Redesign Full-Page

## Overview

This plan implements three areas: (1) full-page navigation layout replacing the sidebar, (2) Docker update rewrite using GitHub archive only, and (3) model selector fix to show all providers with dynamic model fetching. Tasks are ordered for incremental progress — the Docker update fix is independent and can be done in parallel with UI changes.

## Tasks

- [ ] 1. Rewrite Docker updater to use archive-only path
  - [-] 1.1 Rewrite `_do_update_in_thread()` in `main.py` to remove the git fetch/reset path
    - Remove the `repo_root = _find_git_repo_root()` branch and all `subprocess.run(["git", ...])` calls
    - Go directly to GitHub archive download: `https://github.com/{slug}/archive/refs/heads/main.tar.gz`
    - Try `main` branch first, then `master` as fallback
    - Preserve `.env`, `*.db`, `*.db-journal`, `/data/`, `agent_data/`, `docker-compose.yml` during file copy
    - Keep backup creation (Step 1), dependency install (Step 3), validation (Step 4), and restart (Step 5) logic
    - Ensure lock is released in all error paths (wrap in try/finally)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

  - [ ]* 1.2 Write unit tests for the rewritten Docker updater
    - Test archive download failure sets state to "error" and releases lock
    - Test extraction failure sets state to "error" and releases lock
    - Test pip failure is non-fatal (continues to restart)
    - Test concurrent update returns 409
    - Test preserved files are not overwritten
    - _Requirements: 3.8, 3.9, 3.10, 3.11, 3.12_

- [ ] 2. Add missing providers to backend model fetch endpoint
  - [-] 2.1 Add groq, mistral, and cohere support to `GET /api/models/fetch/{provider}` in `routers/models_router.py`
    - Add `elif provider == "groq":` block — fetch from `https://api.groq.com/openai/v1/models` with Bearer token from `groq_api_key`
    - Add `elif provider == "mistral":` block — fetch from `https://api.mistral.ai/v1/models` with Bearer token from `mistral_api_key`
    - Add `elif provider == "cohere":` block — fetch from `https://api.cohere.ai/v1/models` with Bearer token from `cohere_api_key`
    - Return same model object structure: `{id, name, provider, context_length, free, local}`
    - _Requirements: 4.3, 5.1_

  - [ ]* 2.2 Write property test for model sorting (free first, then alphabetical)
    - **Property 9: Model sorting — free first, then alphabetical**
    - **Validates: Requirements 5.3**

- [~] 3. Checkpoint - Ensure backend changes work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Fix chat topbar model selector to use ALL_PROVIDERS
  - [~] 4.1 Update `chatTopbar()` in `desktop/src/main.ts` to use `ALL_PROVIDERS` for the provider dropdown
    - Import `ALL_PROVIDERS` from `./state` (already imported)
    - Replace the fallback `providers` array (7 hardcoded entries) with `ALL_PROVIDERS.map(p => ({value: p.value, label: p.label}))`
    - Ensure the `<select id="sel-provider">` renders all 10 providers from `ALL_PROVIDERS`
    - Keep the model dropdown rendering from `S.providerModels[S.modelType]`
    - Add "✦" symbol for free models in the model `<option>` text
    - _Requirements: 4.3, 6.1, 6.5_

  - [~] 4.2 Fix provider change handler in `bind()` to always fetch models and re-render
    - In the `sel-provider` change handler, after setting `S.modelType`, always call `api(/api/models/fetch/${S.modelType})`
    - On success, store result in `S.providerModels[S.modelType]` and call `render()`
    - On failure, show toast with error message and retain existing cached models
    - Add loading state: set a temporary flag before fetch, clear after
    - _Requirements: 4.2, 6.2, 6.3, 6.4_

  - [ ]* 4.3 Write property test for provider dropdown containing all ALL_PROVIDERS entries
    - **Property 5: Provider dropdown contains all ALL_PROVIDERS entries**
    - **Validates: Requirements 4.3, 6.1**

- [ ] 5. Fix AI Models page provider and model fetching
  - [~] 5.1 Update `aiTab()` in `desktop/src/tabs-ai.ts` to wire fetch-on-provider-select
    - Ensure `data-select-provider` click sets `S.modelType` and triggers model fetch
    - Ensure `data-fetch-models` click calls `api(/api/models/fetch/${provider})` and stores result
    - Display context length and FREE badge for OpenRouter models
    - Show model count per provider in provider cards from `S.providerModels`
    - _Requirements: 4.1, 4.4, 5.2, 5.5_

  - [~] 5.2 Add AI tab event bindings in `bindAI()` in `desktop/src/main.ts`
    - Bind `data-select-provider` click → set `S.modelType`, fetch models, re-render
    - Bind `data-fetch-models` click → fetch models for that provider, store in `S.providerModels`, re-render
    - Bind `data-select-model` click → set `S.modelName`, re-render
    - Bind `#custom-model-form` submit → set `S.modelName` from input value
    - Bind `#btn-refresh-all-models` click → fetch models for all providers with keys configured
    - _Requirements: 4.1, 4.2, 5.6_

  - [ ]* 5.3 Write property test for free model indicator rendering
    - **Property 7: Free models display visual indicators**
    - **Validates: Requirements 4.4, 6.5**

- [~] 6. Checkpoint - Ensure model selector works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Clean up render() for full-page navigation
  - [~] 7.1 Remove legacy sidebar code from `render()` in `desktop/src/main.ts`
    - Remove any remaining sidebar HTML generation (`.sidebar`, `.app-shell`, `.tab-bar`, `.tab-panels`)
    - Ensure `render()` has exactly two paths: chat-fullscreen (when `S.tab === "server"`) and page-overlay (all other tabs)
    - Keep the `more` menu overlay rendering within the chat-fullscreen path
    - Ensure `getPageContent()` handles all 14 tab identifiers
    - _Requirements: 1.1, 1.2, 1.4, 1.5_

  - [~] 7.2 Ensure nav bar renders correctly with active state highlighting
    - Verify `navItem()` adds `.active` class only to the current tab's nav button
    - Verify the More menu contains all secondary items (Account, Browser, Terminal, Personas, Settings, Personalise, Telegram, Admin, Update)
    - Admin-only items (Telegram, Admin, Update) should only appear when `isAdmin()` is true
    - _Requirements: 1.7, 2.2, 2.3, 2.5_

  - [ ]* 7.3 Write property test for navigation producing page-overlay with back button
    - **Property 1: Navigation produces page-overlay with back button**
    - **Validates: Requirements 1.2, 1.4**

  - [ ]* 7.4 Write property test for active tab highlighting in nav-bar
    - **Property 2: Active tab is highlighted in nav-bar**
    - **Validates: Requirements 2.5**

- [ ] 8. Update CSS for full-page layout
  - [~] 8.1 Review and clean up `desktop/src/styles.css` for page-based layout
    - Ensure `.chat-fullscreen`, `.page-overlay`, `.page-header`, `.page-body`, `.nav-bar`, `.nav-item`, `.more-menu-overlay`, `.more-menu`, `.more-menu-item` styles are complete and correct
    - Remove or deprecate `.sidebar`, `.sidebar-header`, `.tab-bar`, `.tab-panels`, `.tab-panel` styles if no longer used
    - Ensure `.nav-bar` height is no more than 48px (horizontal bottom bar)
    - Ensure `.nav-item` icons are compact with short labels
    - _Requirements: 1.3, 2.1_

- [ ] 9. Wire update UI feedback with polling
  - [~] 9.1 Update `bindUpdate()` in `desktop/src/main.ts` to implement status polling
    - On "Pull Update" button click, call `POST /api/admin/update/trigger`
    - Start polling `GET /api/admin/update/status` every 3 seconds while state is "running"
    - Update `S.updateStatus` and `S.updateLog` on each poll, then re-render
    - Stop polling when state changes to "success" or "error"
    - Disable the "Pull Update" button while update is running
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [~] 10. Final checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The Docker update fix (tasks 1.x) is independent of UI changes and can be implemented first
- Frontend uses TypeScript (Vite), backend uses Python (FastAPI)
- The `ALL_PROVIDERS` constant in `state.ts` already has all 10 providers defined

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "4.1"] },
    { "id": 2, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3"] },
    { "id": 4, "tasks": ["7.1", "8.1", "9.1"] },
    { "id": 5, "tasks": ["7.2", "7.3", "7.4"] }
  ]
}
```
