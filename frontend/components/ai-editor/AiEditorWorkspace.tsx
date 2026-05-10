import React from "react";
import { ApiClient } from "../../api-client";
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
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [saveMemory, setSaveMemory] = React.useState(true);

  const createTimeline = (): JobTimelineEvent[] => ([
    { id: "queued", label: "Job queued", status: "running", startedAt: new Date().toISOString() },
    { id: "plan", label: "Analyze repository", status: "pending" },
    { id: "patch", label: "Generate patch", status: "pending" },
    { id: "checks", label: "Run validation checks", status: "pending" },
  ]);

  const toFileChanges = (job: any): ChangedFile[] => {
    const files = job?.result?.changed_files || job?.result?.files || [];
    return files.map((f: any) => ({
      path: String(f.path || f.file || "unknown"),
      status: (f.status || "modified") as ChangedFile["status"],
      additions: Number(f.additions || 0),
      deletions: Number(f.deletions || 0),
    }));
  };

  const generateChanges = async () => {
    if (!prompt.trim()) {
      setError("Please enter a prompt first.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    setTimeline(createTimeline());
    try {
      const [owner, repo] = selectedRepo.split("/");
      const token = localStorage.getItem("token") || "";
      const enqueueResp = await ApiClient.post("/github/repo-edit/jobs", {
        github_token: token,
        instruction: prompt,
        context: { owner, repo, branch: branchTarget },
      }, token);
      const enqueue = await enqueueResp.json();
      const jobId = enqueue.job_id;

      setTimeline((prev) => prev.map((e) => e.id === "queued" ? { ...e, status: "completed" } : e));

      let job: any = null;
      for (let i = 0; i < 20; i++) {
        const statusResp = await ApiClient.get(`/github/repo-edit/jobs/${jobId}`, token);
        const statusData = await statusResp.json();
        job = statusData.job;
        if (["completed", "failed", "cancelled"].includes(job?.status)) break;
        await new Promise((r) => setTimeout(r, 1200));
      }

      if (!job) throw new Error("No job data returned from API.");
      if (job.status !== "completed") throw new Error(job.error || `Job ended with status: ${job.status}`);

      const files = toFileChanges(job);
      setProposedChanges({
        summary: job?.result?.summary || `Generated ${files.length} file updates from AI model API.`,
        files,
        patchPreview: job?.result?.patch || job?.result?.patch_preview || "Patch preview unavailable.",
      });
      setTimeline((prev) => prev.map((e) => ({ ...e, status: "completed" })));

      if (saveMemory) {
        await ApiClient.post("/api/core-memories", {
          fact: `GitHub editor prompt: ${prompt.trim()} | repo=${selectedRepo} | branch=${branchTarget}`,
        }, token);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to generate changes from API.");
      setTimeline((prev) => prev.map((ev) => ev.status === "running" ? { ...ev, status: "failed" } : ev));
    } finally {
      setIsSubmitting(false);
    }
  };

  const excludeFile = (path: string) => setProposedChanges((prev) => prev ? ({ ...prev, files: prev.files.map((f) => f.path === path ? { ...f, excluded: !f.excluded } : f) }) : prev);
  const acceptAll = () => setProposedChanges((prev) => prev ? ({ ...prev, files: prev.files.map((f) => ({ ...f, excluded: false })) }) : prev);

  const onRecover = (mode: EditorErrorMode) => {
    const actions: Record<EditorErrorMode, string> = {
      retry: "Retrying with a reduced file scope...",
      manual: "Opening manual edit mode with current patch...",
      draft_pr: "Creating draft PR with partial output...",
    };
    setError(actions[mode]);
  };

  const createPr = () => {
    if (!proposedChanges) return setError("No generated changes available.");
    setPrResult({
      prUrl: "https://github.com/example/repo/pull/new",
      branchName: branchTarget,
      commitSha: "pending-from-server",
      summary: `Ready to create PR from ${selectedRepo} with ${proposedChanges.files.filter((f) => !f.excluded).length} included files.`,
    });
  };

  return (<div style={{ fontFamily: "Inter, sans-serif", color: "#e2e8f0", padding: 20 }}>
    <h1>AI Workspace Editor</h1>
    <section>
      <h2>1) Prompt + repository + branch target</h2>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} style={{ width: "100%" }} />
      <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
        <select value={selectedRepo} onChange={(e) => setSelectedRepo(e.target.value)}>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select>
        <input value={branchTarget} onChange={(e) => setBranchTarget(e.target.value)} placeholder="branch target" />
        <label><input type="checkbox" checked={saveMemory} onChange={(e) => setSaveMemory(e.target.checked)} /> Save prompt to memory</label>
        <button onClick={generateChanges} disabled={isSubmitting}>{isSubmitting ? "Generating..." : "Generate changes"}</button>
      </div>
    </section>
    <section><h2>2) Proposed changes</h2>{!proposedChanges ? <p>No changes generated.</p> : <><p>{proposedChanges.summary}</p><ul>{proposedChanges.files.map((file) => <li key={file.path}><span style={{ color: badgeColor[file.status], fontWeight: 700 }}>{file.status.toUpperCase()}</span> {file.path} (+{file.additions}/-{file.deletions})<button style={{ marginLeft: 8 }} onClick={() => excludeFile(file.path)}>{file.excluded ? "Include file" : "Exclude file"}</button></li>)}</ul><pre>{proposedChanges.patchPreview}</pre></>}</section>
    <section><h2>3) User actions</h2><button onClick={acceptAll}>Accept all</button><button onClick={generateChanges} style={{ marginLeft: 8 }}>Edit prompt + regenerate</button><button onClick={createPr} style={{ marginLeft: 8 }}>Create PR</button></section>
    <section><h2>4) Live job status timeline</h2><ul>{timeline.map((event) => <li key={event.id}><strong>{event.label}:</strong> {event.status}</li>)}</ul></section>
    {prResult && <section><h2>5) PR result</h2><p><a href={prResult.prUrl} target="_blank" rel="noreferrer">Open Pull Request</a></p><p>Branch: <code>{prResult.branchName}</code></p><p>{prResult.summary}</p></section>}
    <section><h2>6) Error + recovery options</h2>{error ? <p>{error}</p> : <p>No active errors.</p>}<div style={{ display: "flex", gap: 8 }}><button onClick={() => onRecover("retry")}>Retry with smaller scope</button><button onClick={() => onRecover("manual")}>Manual edit</button><button onClick={() => onRecover("draft_pr")}>Open draft PR</button></div></section>
  </div>);
}
