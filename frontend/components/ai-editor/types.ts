export type RepositoryOption = {
  id: string;
  name: string;
  defaultBranch: string;
};

export type ChangedFile = {
  path: string;
  status: "added" | "modified" | "deleted";
  additions: number;
  deletions: number;
  excluded?: boolean;
};

export type ProposedChanges = {
  summary: string;
  files: ChangedFile[];
  patchPreview: string;
};

export type JobTimelineEvent = {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  startedAt?: string;
  endedAt?: string;
  details?: string;
};

export type PullRequestResult = {
  prUrl: string;
  branchName: string;
  commitSha: string;
  summary: string;
};

export type EditorErrorMode = "retry" | "manual" | "draft_pr";
