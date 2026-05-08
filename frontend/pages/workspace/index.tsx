import React from "react";
import { createRoot } from "react-dom/client";
import { AiEditorWorkspace } from "../../components/ai-editor/AiEditorWorkspace";

const repositories = [
  { id: "repo-1", name: "ampai/frontend", defaultBranch: "main" },
  { id: "repo-2", name: "ampai/backend", defaultBranch: "main" },
  { id: "repo-3", name: "ampai/infra", defaultBranch: "develop" },
];

function WorkspacePage() {
  return <AiEditorWorkspace repositories={repositories} />;
}

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<WorkspacePage />);
}
