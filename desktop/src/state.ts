// ── Types ──────────────────────────────────────────────────────────────────
export type Health   = { ok:boolean; status:string; detail:string };
export type Auth     = { username:string; role:string; token:string };
export type Msg      = { role:"user"|"assistant"|"system"; content:string; time:string };
export type Session  = { session_id:string; category:string; title?:string; updated_at:string; pinned?:boolean; archived?:boolean };
export type CoreMem  = { id:number; fact:string };
export type User     = { username:string; role:string };
export type Attach   = { filename:string; url:string; type:string; extracted_text:string|null };
export type Persona  = { id:string; name:string; system_prompt:string; tags:string[]; is_default:boolean };
export type MemInbox = { id:string; candidate_text:string; edited_text:string|null; session_id:string; confidence:number; status:"pending"|"approved"|"rejected"; created_at:string };

// ── Browser Automation Types ───────────────────────────────────────────────
export type BrowserJob = {
  id: number;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  request: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  created_at: string;
  finished_at: string | null;
};

export type BrowserConfirmation = {
  action: string;
  description: string;
  url?: string;
  timestamp: string;
};

export interface BrowserState {
  enabled: boolean;
  allowlist: string[];
  jobs: BrowserJob[];
  currentScreenshot: string | null;
  confirmationPending: BrowserConfirmation | null;
}

// ── Terminal Types ──────────────────────────────────────────────────────────
export type TerminalPolicy = {
  enabled: boolean;
  require_confirmation: boolean;
  allowed_folders: string[];
  command_allowlist: string[];
  command_denylist: string[];
  timeout: number;
  max_output: number;
};

export type TerminalLog = {
  id: number;
  command: string;
  working_directory: string | null;
  exit_code: number | null;
  output_summary: string | null;
  execution_ms: number | null;
  blocked: boolean;
  created_at: string;
};

export type TerminalConfirmation = {
  command: string;
  working_directory: string | null;
  timestamp: string;
};

export interface TerminalState {
  enabled: boolean;
  policy: TerminalPolicy;
  logs: TerminalLog[];
  confirmationPending: TerminalConfirmation | null;
}

// ── Task Types ─────────────────────────────────────────────────────────────
export type Task = {
  id: number;
  title: string;
  description: string | null;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high" | "urgent";
  due_at: string | null;
  session_id: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskFilter = {
  status?: string;
  priority?: string;
  search?: string;
  due_from?: string;
  due_to?: string;
};

export interface TaskState {
  tasks: Task[];
  filter: TaskFilter;
}

// ── Constants ──────────────────────────────────────────────────────────────
export const GITHUB      = "pranto48/ampai";
export const APP_VERSION = "0.1.5";
export const SK          = "ampai.serverUrl";
export const AK          = "ampai.auth";
export const SESSK       = "ampai.sessionId";
export const ACCENT_K    = "ampai.accent";
export const DEF_URL     = (["tauri.localhost","localhost","127.0.0.1"].includes(window.location.hostname)||window.location.protocol.startsWith("tauri"))?"http://127.0.0.1:8001":window.location.origin;

export const ACCENT_COLORS=[
  {name:"Indigo",value:"#6366f1"},{name:"Purple",value:"#8b5cf6"},
  {name:"Blue",value:"#3b82f6"},{name:"Cyan",value:"#06b6d4"},
  {name:"Teal",value:"#14b8a6"},{name:"Green",value:"#10b981"},
  {name:"Amber",value:"#f59e0b"},{name:"Rose",value:"#f43f5e"},
];

export const ALL_PROVIDERS=[
  {value:"ollama",label:"🦙 Ollama",local:true,urlField:"ollama_base_url",keyField:""},
  {value:"openrouter",label:"🔀 OpenRouter",local:false,urlField:"",keyField:"openrouter_api_key"},
  {value:"openai",label:"✨ OpenAI",local:false,urlField:"",keyField:"openai_api_key"},
  {value:"gemini",label:"🌟 Gemini",local:false,urlField:"",keyField:"gemini_api_key"},
  {value:"anthropic",label:"🔴 Anthropic",local:false,urlField:"",keyField:"anthropic_api_key"},
  {value:"groq",label:"⚡ Groq",local:false,urlField:"",keyField:"groq_api_key"},
  {value:"mistral",label:"🌪️ Mistral",local:false,urlField:"",keyField:"mistral_api_key"},
  {value:"cohere",label:"🔵 Cohere",local:false,urlField:"",keyField:"cohere_api_key"},
  {value:"generic",label:"🏠 LM Studio",local:true,urlField:"generic_base_url",keyField:"generic_api_key"},
  {value:"anythingllm",label:"📚 AnythingLLM",local:true,urlField:"anythingllm_base_url",keyField:"anythingllm_api_key"},
];

// ── State ──────────────────────────────────────────────────────────────────
function norm(v:string):string{const t=(v||"").trim();if(!t)return DEF_URL;const s=/^https?:\/\//i.test(t)?t:`http://${t}`;try{return new URL(s).origin;}catch{return DEF_URL;}}
function newSid():string{const id=(globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`);localStorage.setItem(SESSK,id);return id;}
function readAuth():Auth|null{const r=localStorage.getItem(AK);if(!r)return null;try{const p=JSON.parse(r)as Auth;return p?.token&&p?.username?p:null;}catch{localStorage.removeItem(AK);return null;}}

export const S={
  serverUrl:norm(localStorage.getItem(SK)||DEF_URL),
  health:{ok:false,status:"offline",detail:"Not checked"} as Health,
  auth:readAuth(),
  sessionId:localStorage.getItem(SESSK)||newSid(),
  msgs:[] as Msg[],
  tab:"server",
  sessions:[] as Session[],
  sessionSearch:"",
  sessionCategoryFilter:"",
  sessionPage:1,
  sessionHasMore:true,
  sessionLoadingMore:false,
  sessionError:"",
  renamingSessionId:null as string|null,
  renamingSessionTitle:"",
  assigningCategorySessionId:null as string|null,
  assigningCategoryValue:"",
  memories:[] as CoreMem[],
  memSubTab:"core" as "core"|"inbox"|"analytics",
  memoryInbox:[] as MemInbox[],
  inboxStatusFilter:"pending",
  memoryAnalytics:null as any,
  editingMemId:null as number|null,
  editingMemFact:"",
  users:[] as User[],
  updateVersion:null as any,
  updateStatus:null as any,
  updateLog:[] as string[],
  backups:[] as any[],
  tgStatus:null as any,
  configs:{} as Record<string,string>,
  providers:[] as Array<{value:string;label:string}>,
  personas:[] as Persona[],
  editingPersona:null as Persona|null,
  personaModal:false,
  adminSubTab:"dashboard" as "dashboard"|"users"|"agent"|"backup"|"retention",
  adminStats:null as any,
  desktopUpdate:null as any,
  themeAccent:localStorage.getItem(ACCENT_K)||"#6366f1",
  sidebarCollapsed:localStorage.getItem("ampai.sidebarCollapsed")==="1",
  ollamaModels:[] as string[],
  modal:null as string|null,
  modelType:"ollama",
  modelName:"",
  memoryMode:"full",
  useWebSearch:false,
  enableBrowserTools:false,
  enableTerminalTools:false,
  attachments:[] as Attach[],
  busy:false,
  browserState:{
    enabled:false,
    allowlist:[],
    jobs:[],
    currentScreenshot:null,
    confirmationPending:null,
  } as BrowserState,
  terminalState:{
    enabled:false,
    policy:{
      enabled:false,
      require_confirmation:true,
      allowed_folders:[],
      command_allowlist:[],
      command_denylist:[],
      timeout:30,
      max_output:10000,
    },
    logs:[],
    confirmationPending:null,
  } as TerminalState,
  taskState:{
    tasks:[],
    filter:{},
  } as TaskState,
};
