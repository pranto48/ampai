import React from "react";
import {
  ChangedFile,
  EditorErrorMode,
  JobTimelineEvent,
  ProposedChanges,
  PullRequestResult,
  RepositoryOption,
} from "./types";

type Props = {
  repositories: RepositoryOption[];
};

const badgeColor: Record<ChangedFile["status"], string> = {
  added: "#059669",
  modified: "#1d4ed8",
  deleted: "#dc2626",
};

export function AiEditorWorkspace({ repositories }: Props) {
  const [prompt, setPrompt] = React.useState("");
  const [selectedRepo, setSelectedRepo] = React.useState(repositories[0]?.id ?? "");
  const [branchTarget, setBranchTarget] = React.useState("feature/ai-editor");
  const [proposedChanges, setProposedChanges] = React.useState<ProposedChanges | null>(null);
  const [timeline, setTimeline] = React.useState<JobTimelineEvent[]>([]);
  const [prResult, setPrResult] = React.useState<PullRequestResult | null>(null);
  const [error, setError] = React.useState<string>("");

  const triggerTimeline = () => {
    setTimeline([
      { id: "queued", label: "Job queued", status: "completed", startedAt: new Date().toISOString() },
      { id: "plan", label: "Analyze repository", status: "completed", startedAt: new Date().toISOString() },
      { id: "patch", label: "Generate patch", status: "running", startedAt: new Date().toISOString() },
      { id: "checks", label: "Run validation checks", status: "pending" },
    ]);
  };

  const generateChanges = () => {
    setError("");
    triggerTimeline();
    setProposedChanges({
      summary: "Generated 3 file updates to add a new onboarding sequence.",
      files: [
        { path: "frontend/pages/workspace/index.tsx", status: "added", additions: 211, deletions: 0 },
        { path: "frontend/components/ai-editor/AiEditorWorkspace.tsx", status: "modified", additions: 92, deletions: 24 },
        { path: "frontend/components/ai-editor/styles.css", status: "modified", additions: 56, deletions: 4 },
      ],
      patchPreview: `diff --git a/frontend/components/ai-editor/AiEditorWorkspace.tsx b/frontend/components/ai-editor/AiEditorWorkspace.tsx\n+ const [branchTarget, setBranchTarget] = React.useState(\"feature/ai-editor\");\n+ <button onClick={onCreatePr}>Create PR</button>`,
    });
    setTimeline((prev) => prev.map((event) => (event.status === "running" ? { ...event, status: "completed" } : event)));
  };

  const excludeFile = (path: string) => {
    setProposedChanges((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        files: prev.files.map((file) => (file.path === path ? { ...file, excluded: !file.excluded } : file)),
      };
    });
  };

  const acceptAll = () => {
    setProposedChanges((prev) => (prev ? { ...prev, files: prev.files.map((file) => ({ ...file, excluded: false })) } : prev));
  };

  const onRecover = (mode: EditorErrorMode) => {
    const actions: Record<EditorErrorMode, string> = {
      retry: "Retrying with a reduced file scope...",
      manual: "Opening manual edit mode with current patch...",
      draft_pr: "Creating draft PR with partial output...",
    };
    setError(actions[mode]);
  };

  const createPr = () => {
    if (!proposedChanges) {
      setError("No generated changes available. Generate or regenerate before creating a PR.");
      return;
    }
    setPrResult({
      prUrl: "https://github.com/example/repo/pull/42",
      branchName: branchTarget,
      commitSha: "4f8b1f824ad2450a2d5f1aa8b0ecdc5f189e37de",
      summary: `PR created from ${selectedRepo} with ${proposedChanges.files.filter((f) => !f.excluded).length} included files.`,
    });
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif", color: "#e2e8f0", padding: 20 }}>
      <h1>AI Workspace Editor</h1>

      <section>
        <h2>1) Prompt + repository + branch target</h2>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe what to change..." rows={4} style={{ width: "100%" }} />
        <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
          <select value={selectedRepo} onChange={(e) => setSelectedRepo(e.target.value)}>
            {repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}
          </select>
          <input value={branchTarget} onChange={(e) => setBranchTarget(e.target.value)} placeholder="branch target" />
          <button onClick={generateChanges}>Generate changes</button>
        </div>
      </section>

      <section>
        <h2>2) Proposed changes</h2>
        {!proposedChanges ? <p>No changes generated.</p> : <>
          <p>{proposedChanges.summary}</p>
          <ul>
            {proposedChanges.files.map((file) => (
              <li key={file.path}>
                <span style={{ color: badgeColor[file.status], fontWeight: 700 }}>{file.status.toUpperCase()}</span> {file.path} (+{file.additions}/-{file.deletions})
                <button style={{ marginLeft: 8 }} onClick={() => excludeFile(file.path)}>{file.excluded ? "Include file" : "Exclude file"}</button>
              </li>
            ))}
          </ul>
          <pre>{proposedChanges.patchPreview}</pre>
        </>}
      </section>

      <section>
        <h2>3) User actions</h2>
        <button onClick={acceptAll}>Accept all</button>
        <button onClick={generateChanges} style={{ marginLeft: 8 }}>Edit prompt + regenerate</button>
        <button onClick={createPr} style={{ marginLeft: 8 }}>Create PR</button>
      </section>

      <section>
        <h2>4) Live job status timeline</h2>
        <ul>
          {timeline.map((event) => <li key={event.id}><strong>{event.label}:</strong> {event.status} {event.details ? `- ${event.details}` : ""}</li>)}
        </ul>
      </section>

      {prResult && <section>
        <h2>5) PR result</h2>
        <p><a href={prResult.prUrl} target="_blank" rel="noreferrer">Open Pull Request</a></p>
        <p>Branch: <code>{prResult.branchName}</code></p>
        <p>Commit SHA: <code>{prResult.commitSha}</code></p>
        <p>{prResult.summary}</p>
      </section>}

      <section>
        <h2>6) Error + recovery options</h2>
        {error ? <p>{error}</p> : <p>No active errors.</p>}
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => onRecover("retry")}>Retry with smaller scope</button>
          <button onClick={() => onRecover("manual")}>Manual edit</button>
          <button onClick={() => onRecover("draft_pr")}>Open draft PR</button>
        </div>
      </section>
    </div>
  );
}
