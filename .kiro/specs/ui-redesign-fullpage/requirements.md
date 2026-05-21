# Requirements Document

## Introduction

This feature addresses three major issues in the AmpAI application: a broken Docker update mechanism, a UI layout overhaul from sidebar panels to full-page views, and a model selector that fails to show all available providers and dynamically fetched models. The goal is to deliver a modern single-page-app navigation experience, a reliable in-container code update flow, and a comprehensive AI model discovery system.

## Glossary

- **Desktop_App**: The Vite/TypeScript frontend application located in `desktop/src/`, served via Tauri or a browser.
- **Backend**: The Python FastAPI server at the project root providing all API endpoints.
- **Nav_Bar**: A compact navigation bar (icon-based, top or side) replacing the current wide sidebar.
- **Full_Page_View**: A view that occupies the entire content area, replacing the previous view rather than appearing in a sidebar panel.
- **Chat_View**: The default full-screen view showing the conversation interface with the AI agent.
- **Page_Overlay**: A full-page view that replaces the Chat_View when a navigation item is selected.
- **Model_Selector**: The UI controls (provider dropdown and model dropdown) in the chat topbar for choosing the active AI provider and model.
- **Provider**: An AI service backend (e.g., Ollama, OpenRouter, OpenAI, Gemini, Anthropic, Groq, Mistral, Cohere, LM Studio, AnythingLLM).
- **Docker_Updater**: The backend subsystem responsible for downloading, extracting, and applying code updates inside a Docker container.
- **Update_Trigger_Endpoint**: The `POST /api/admin/update/trigger` API endpoint that initiates the update process.
- **GitHub_Archive**: A `.tar.gz` or `.zip` archive downloaded from the GitHub repository URL (`https://github.com/pranto48/ampai`).
- **Provider_Models_Endpoint**: The `GET /api/models/fetch/{provider}` API endpoint that dynamically fetches available models from a provider's API.
- **More_Menu**: A secondary navigation menu accessible from the Nav_Bar that shows additional sections (Browser, Terminal, Personas, Settings, Personalise, Telegram, Admin, Update).

## Requirements

### Requirement 1: Full-Page Navigation Layout

**User Story:** As a user, I want each section of the app to open as a full-page view instead of a sidebar panel, so that I have more screen space and a cleaner interface.

#### Acceptance Criteria

1. WHEN the Desktop_App loads, THE Desktop_App SHALL display the Chat_View as the default full-screen view with the Nav_Bar visible.
2. WHEN a user selects a navigation item from the Nav_Bar, THE Desktop_App SHALL replace the current view with the corresponding Full_Page_View.
3. THE Nav_Bar SHALL display navigation items as compact icons with short labels, occupying no more than 60 pixels in width (vertical) or 48 pixels in height (horizontal).
4. WHEN a Full_Page_View is active, THE Desktop_App SHALL display a back button that returns the user to the Chat_View.
5. THE Desktop_App SHALL support the following sections as Full_Page_Views: Chat, Account, History, Memory, AI Models, Tasks, Browser, Terminal, AI Personas, Settings, Personalise, Telegram, Admin, and Update.
6. WHEN the user navigates to a Full_Page_View, THE Desktop_App SHALL load the relevant data for that section from the Backend before rendering.
7. THE Nav_Bar SHALL display primary items (Chat, History, Memory, AI, Tasks) directly and group remaining items under a More_Menu.

### Requirement 2: Compact Navigation Bar

**User Story:** As a user, I want a compact navigation bar instead of the wide sidebar, so that the main content area is maximized.

#### Acceptance Criteria

1. THE Nav_Bar SHALL render as a fixed-position bar at the bottom of the viewport on mobile-width screens (below 768 pixels) and at the left side on wider screens.
2. THE Nav_Bar SHALL contain icon buttons for primary sections: Chat, History, Memory, AI Models, and Tasks.
3. THE Nav_Bar SHALL contain a More button that opens the More_Menu with remaining sections.
4. WHEN the More_Menu is open, THE Desktop_App SHALL display it as an overlay that closes when the user selects an item or taps outside.
5. THE Nav_Bar SHALL visually indicate the currently active section by highlighting the corresponding icon.

### Requirement 3: Docker Update via GitHub Archive Download

**User Story:** As an admin, I want the Pull Update button to reliably download the latest code from GitHub and apply it inside the Docker container, so that I can update the application without manual intervention.

#### Acceptance Criteria

1. WHEN an admin triggers the Update_Trigger_Endpoint, THE Docker_Updater SHALL download the latest archive from `https://github.com/pranto48/ampai/archive/refs/heads/main.tar.gz`.
2. WHEN the archive download completes, THE Docker_Updater SHALL extract the archive contents to a temporary directory.
3. WHEN extraction completes, THE Docker_Updater SHALL back up the current application files to a timestamped backup directory before overwriting.
4. WHEN the backup completes, THE Docker_Updater SHALL copy the extracted files over the current application directory, preserving the `.env` file, database files, and user data.
5. WHEN file copy completes, THE Docker_Updater SHALL run `pip install -r requirements.txt` to install any new or updated Python dependencies.
6. WHEN dependency installation completes, THE Docker_Updater SHALL restart the FastAPI server process.
7. WHILE the update is running, THE Docker_Updater SHALL append progress messages to the update log accessible via `GET /api/admin/update/status`.
8. IF the archive download fails, THEN THE Docker_Updater SHALL log the error, set the update state to "error", and release the update lock.
9. IF file extraction fails, THEN THE Docker_Updater SHALL log the error, set the update state to "error", and release the update lock.
10. IF dependency installation fails, THEN THE Docker_Updater SHALL log the warning and continue with the server restart (non-fatal).
11. IF the server restart fails, THEN THE Docker_Updater SHALL log the error and set the update state to "error".
12. THE Docker_Updater SHALL prevent concurrent updates by acquiring a lock before starting and rejecting subsequent requests with HTTP 409 while an update is in progress.

### Requirement 4: Dynamic Model Fetching for All Providers

**User Story:** As a user, I want to see all available models from all configured providers in the model selector, so that I can choose the best model for my task.

#### Acceptance Criteria

1. WHEN the AI Models Full_Page_View loads, THE Desktop_App SHALL call the Provider_Models_Endpoint for the currently selected provider and display the returned models.
2. WHEN a user changes the provider in the Model_Selector, THE Desktop_App SHALL call the Provider_Models_Endpoint for the newly selected provider and update the model dropdown with the fetched models.
3. THE Model_Selector SHALL display all configured providers in the provider dropdown, including Ollama, OpenRouter, OpenAI, Gemini, Anthropic, Groq, Mistral, Cohere, LM Studio, and AnythingLLM.
4. WHEN models are fetched from OpenRouter, THE Desktop_App SHALL highlight models that are free (zero prompt and completion cost) with a visible "FREE" badge.
5. IF the Provider_Models_Endpoint returns an error for a provider, THEN THE Desktop_App SHALL display a toast notification with the error message and retain any previously loaded models for that provider.
6. THE Model_Selector in the chat topbar SHALL display the fetched models for the currently selected provider, not only hardcoded defaults.
7. WHEN the Desktop_App starts and a user is authenticated, THE Desktop_App SHALL fetch models for the default provider configured in settings.

### Requirement 5: OpenRouter Model Integration

**User Story:** As a user, I want OpenRouter models to be fetched dynamically and displayed with relevant metadata, so that I can discover and use free or paid models from OpenRouter.

#### Acceptance Criteria

1. WHEN the Provider_Models_Endpoint is called with provider "openrouter", THE Backend SHALL fetch the model list from `https://openrouter.ai/api/v1/models` using the configured OpenRouter API key if available.
2. THE Backend SHALL parse each model entry and return the model ID, display name, context length, free status (based on zero pricing), and a truncated description.
3. THE Backend SHALL sort OpenRouter models with free models listed first, then alphabetically by name.
4. WHEN no OpenRouter API key is configured, THE Backend SHALL still fetch the public model list from the OpenRouter API (the endpoint is publicly accessible).
5. THE Desktop_App SHALL display OpenRouter model context length alongside each model entry in the AI Models view.
6. WHEN a user selects an OpenRouter model, THE Desktop_App SHALL set both the provider to "openrouter" and the model name to the selected model ID.

### Requirement 6: Model Selector Topbar Integration

**User Story:** As a user, I want the chat topbar model selector to show dynamically fetched models instead of hardcoded defaults, so that I always see my actual available models.

#### Acceptance Criteria

1. THE chat topbar Model_Selector provider dropdown SHALL list all providers from the ALL_PROVIDERS constant, not a reduced subset.
2. WHEN the provider dropdown value changes, THE Desktop_App SHALL fetch models for the new provider and populate the model dropdown with the results.
3. IF models have not yet been fetched for the selected provider, THE Desktop_App SHALL show a loading indicator in the model dropdown until the fetch completes.
4. WHEN models are successfully fetched, THE Desktop_App SHALL cache them in the application state (`S.providerModels`) to avoid redundant API calls during the same session.
5. THE model dropdown SHALL display the model display name and append a "✦" symbol for free models.

### Requirement 7: Update UI Feedback

**User Story:** As an admin, I want to see real-time progress of the Docker update process, so that I know whether the update succeeded or failed.

#### Acceptance Criteria

1. WHEN the admin clicks the "Pull Update" button, THE Desktop_App SHALL call `POST /api/admin/update/trigger` and display a "running" status badge.
2. WHILE the update state is "running", THE Desktop_App SHALL poll `GET /api/admin/update/status` every 3 seconds and display the latest log lines.
3. WHEN the update state changes to "success", THE Desktop_App SHALL display a success badge and stop polling.
4. WHEN the update state changes to "error", THE Desktop_App SHALL display an error badge with the error message and stop polling.
5. WHILE the update is running, THE Desktop_App SHALL disable the "Pull Update" button to prevent duplicate triggers.
