import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  LayoutDashboard,
  History,
  Brain,
  ClipboardList,
  Globe,
  Terminal,
  Sliders,
  Shield,
  User,
  LogOut,
  Lock,
  Menu,
  X,
  Check,
  Plus,
  Upload,
  Trash2,
  Edit2,
  Send,
  Paperclip,
  Activity,
  Database,
  ShieldAlert,
  Play,
  RefreshCw,
  AlertCircle,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Pin,
  Archive,
  FolderOpen,
  Eye,
  EyeOff,
  Search
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";

import { S, Auth, Msg, Session, CoreMem, User as AdminUser, Attach, Persona, MemInbox, BrowserJob, TerminalLog, Task, DEF_URL, norm } from "./state";

// Constants and defaults
const SESSK = "ampai.sessionId";
const ACCENT_COLORS = [
  { name: "Indigo", value: "#6366f1" },
  { name: "Purple", value: "#8b5cf6" },
  { name: "Blue", value: "#3b82f6" },
  { name: "Cyan", value: "#06b6d4" },
  { name: "Teal", value: "#14b8a6" },
  { name: "Green", value: "#10b981" },
  { name: "Amber", value: "#f59e0b" },
  { name: "Rose", value: "#f43f5e" },
];

function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export default function App() {
  // --- React State ---
  const [auth, setAuth] = useState<Auth | null>(() => {
    const r = localStorage.getItem("ampai.auth");
    if (!r) return null;
    try {
      const p = JSON.parse(r);
      return p?.token && p?.username ? p : null;
    } catch {
      return null;
    }
  });

  const [tab, setTab] = useState<string>(() => {
    // If not authenticated, force account screen. Otherwise start at dashboard
    const r = localStorage.getItem("ampai.auth");
    return r ? "dashboard" : "account";
  });

  const [serverUrl, setServerUrl] = useState<string>(() => norm(localStorage.getItem("ampai.serverUrl") || DEF_URL));
  const [health, setHealth] = useState({ ok: false, status: "offline", detail: "Not checked" });
  const [busy, setBusy] = useState<boolean>(false);
  const [toastMsg, setToastMsg] = useState<{ text: string; type: "ok" | "err" | "info" } | null>(null);

  // Chat/Session States
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string>(() => localStorage.getItem(SESSK) || "");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [inputText, setInputText] = useState<string>("");
  const [modelType, setModelType] = useState<string>("ollama");
  const [modelName, setModelName] = useState<string>("");
  const [useWebSearch, setUseWebSearch] = useState<boolean>(false);
  const [enableBrowserTools, setEnableBrowserTools] = useState<boolean>(false);
  const [enableTerminalTools, setEnableTerminalTools] = useState<boolean>(false);
  const [attachments, setAttachments] = useState<Attach[]>([]);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [isAutoScrollPinned, setIsAutoScrollPinned] = useState<boolean>(true);
  const [activeAgentStatus, setActiveAgentStatus] = useState<{ status: string; message: string } | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [providers, setProviders] = useState<any[]>([]);
  const [providerModels, setProviderModels] = useState<Record<string, any[]>>({});
  const [sessionSearch, setSessionSearch] = useState<string>("");

  // Curation text-file import states
  const [curatedFacts, setCuratedFacts] = useState<string[]>([]);
  const [selectedFacts, setSelectedFacts] = useState<Record<number, boolean>>({});
  const [memoryFileLoading, setMemoryFileLoading] = useState<boolean>(false);
  const [sessionCategoryFilter, setSessionCategoryFilter] = useState<string>("");
  
  // Modals / Renaming states
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const [categoryModalSessionId, setCategoryModalSessionId] = useState<string | null>(null);
  const [categoryValue, setCategoryValue] = useState<string>("");

  // Memory Panel States
  const [memories, setMemories] = useState<CoreMem[]>([]);
  const [memoryInbox, setMemoryInbox] = useState<MemInbox[]>([]);
  const [memSubTab, setMemSubTab] = useState<"core" | "inbox" | "explorer" | "analytics">("core");
  const [inboxFilter, setInboxFilter] = useState<string>("pending");
  const [newFact, setNewFact] = useState<string>("");
  const [editingMemId, setEditingMemId] = useState<number | null>(null);
  const [editingFactText, setEditingFactText] = useState<string>("");

  // Vector Explorer States
  const [vectorMemories, setVectorMemories] = useState<any[]>([]);
  const [newVectorDoc, setNewVectorDoc] = useState<string>("");
  const [editingVectorId, setEditingVectorId] = useState<string | null>(null);
  const [editingVectorText, setEditingVectorText] = useState<string>("");
  const [vectorSearch, setVectorSearch] = useState<string>("");
  const [vectorLoading, setVectorLoading] = useState<boolean>(false);

  // Global Chat Search States
  const [showSearchModal, setShowSearchModal] = useState<boolean>(false);
  const [globalSearchQuery, setGlobalSearchQuery] = useState<string>("");
  const [globalSearchHits, setGlobalSearchHits] = useState<any[]>([]);
  const [globalSearchLoading, setGlobalSearchLoading] = useState<boolean>(false);


  // Tasks Panel States
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskSearch, setTaskSearch] = useState<string>("");
  const [taskPriorityFilter, setTaskPriorityFilter] = useState<string>("");
  const [newTaskTitle, setNewTaskTitle] = useState<string>("");
  const [newTaskDesc, setNewTaskDesc] = useState<string>("");
  const [newTaskPriority, setNewTaskPriority] = useState<string>("medium");
  const [newTaskDue, setNewTaskDue] = useState<string>("");

  // Browser Panel States
  const [browserJobs, setBrowserJobs] = useState<BrowserJob[]>([]);
  const [browserEnabled, setBrowserEnabled] = useState<boolean>(false);
  const [allowlist, setAllowlist] = useState<string[]>([]);
  const [newAllowlistDomain, setNewAllowlistDomain] = useState<string>("");
  const [browserConfirmation, setBrowserConfirmation] = useState<any>(null);
  const [selectedJobScreenshot, setSelectedJobScreenshot] = useState<string | null>(null);

  // Terminal Panel States
  const [terminalLogs, setTerminalLogs] = useState<TerminalLog[]>([]);
  const [terminalEnabled, setTerminalEnabled] = useState<boolean>(false);
  const [terminalCommand, setTerminalCommand] = useState<string>("");
  const [terminalOutput, setTerminalOutput] = useState<string>("");
  const [terminalConfirmation, setTerminalConfirmation] = useState<any>(null);
  const [terminalPolicy, setTerminalPolicy] = useState<any>(null);

  // Admin & Settings Panel States
  const [adminSubTab, setAdminSubTab] = useState<"console" | "backup">("console");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreDragActive, setRestoreDragActive] = useState<boolean>(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState<boolean>(false);
  const [restoreBusy, setRestoreBusy] = useState<boolean>(false);
  const [configs, setConfigs] = useState<Record<string, string>>({});
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminStats, setAdminStats] = useState<any>(null);
  const [telegramStatus, setTelegramStatus] = useState<any>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [updateVersion, setUpdateVersion] = useState<any>(null);
  const [updateStatus, setUpdateStatus] = useState<any>(null);
  const [updateLogs, setUpdateLogs] = useState<string[]>([]);
  const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
  const [isTriggeringUpdate, setIsTriggeringUpdate] = useState<boolean>(false);
  const [personas, setPersonas] = useState<Persona[]>([]);

  // UI States
  const [themeAccent, setThemeAccent] = useState<string>(() => localStorage.getItem("ampai.accent") || "#6366f1");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => localStorage.getItem("ampai.sidebarCollapsed") === "1");
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState<boolean>(false);

  // Auth Forms States
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [emailValid, setEmailValid] = useState<boolean | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<number>(0); // 0 to 5

  const chatEndRef = useRef<HTMLDivElement>(null);
  const updateLogsEndRef = useRef<HTMLDivElement>(null);
  const toastTimeoutRef = useRef<any>(null);

  // --- Theme Syncing ---
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--accent", themeAccent);
    root.style.setProperty("--accent-2", themeAccent);
    localStorage.setItem("ampai.accent", themeAccent);
    S.themeAccent = themeAccent;
  }, [themeAccent]);

  // --- Toast notification helper ---
  const triggerToast = (text: string, type: "ok" | "err" | "info" = "info") => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToastMsg({ text, type });
    toastTimeoutRef.current = setTimeout(() => {
      setToastMsg(null);
    }, 4000);
  };

  // --- Network fetch helper ---
  const apiCall = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
    const headers = new Headers(options.headers);
    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (auth?.token) {
      headers.set("Authorization", `Bearer ${auth.token}`);
    }
    
    // Auto-adjust timeout for chat or general api
    const controller = new AbortController();
    const timeoutMs = path.includes("/chat") ? 180000 : 30000;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${serverUrl}${path}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (response.status === 401) {
        // Token might have expired
        handleLogout();
        throw new Error("Session expired. Please log in again.");
      }

      const text = await response.text();
      const data = text ? JSON.parse(text) : {};
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || response.statusText);
      }
      return data as T;
    } finally {
      clearTimeout(timer);
    }
  };

  const checkServerHealth = async (customUrl?: string) => {
    const target = customUrl || serverUrl;
    try {
      const data = await fetch(`${target}/healthz`).then(r => r.json());
      if (data?.status === "ok") {
        setHealth({ ok: true, status: "online", detail: "Connected" });
        return true;
      }
    } catch (err: any) {
      setHealth({ ok: false, status: "offline", detail: err.message || "Failed to reach server" });
    }
    return false;
  };

  // Check server health on load and periodically
  useEffect(() => {
    checkServerHealth();
    const interval = setInterval(() => {
      checkServerHealth();
    }, 20000);
    return () => clearInterval(interval);
  }, [serverUrl]);

  // Keep S state object partially in sync (in case external templates reference it)
  useEffect(() => {
    S.serverUrl = serverUrl;
    S.health = health;
  }, [serverUrl, health]);

  const isAdmin = () => auth?.role === "admin";

  // --- Auth Handlers ---
  const handleLogout = () => {
    setAuth(null);
    localStorage.removeItem("ampai.auth");
    S.auth = null;
    setSessions([]);
    setMsgs([]);
    setSessionId("");
    setTab("account");
    triggerToast("Logged out successfully", "info");
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameInput || !passwordInput) {
      triggerToast("Username and Password are required", "err");
      return;
    }
    setBusy(true);
    try {
      const data = await apiCall<Auth>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: usernameInput,
          password: passwordInput,
          remember_me: true
        })
      });
      setAuth(data);
      localStorage.setItem("ampai.auth", JSON.stringify(data));
      S.auth = data;
      triggerToast(`Successfully signed in as ${data.username}`, "ok");
      
      // Auto redirect to dashboard
      setTab("dashboard");
      setUsernameInput("");
      setPasswordInput("");
    } catch (err: any) {
      triggerToast(err.message || "Login failed", "err");
    } finally {
      setBusy(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameInput || !passwordInput) {
      triggerToast("Username and Password are required", "err");
      return;
    }
    if (emailInput && !emailValid) {
      triggerToast("Please enter a valid email address", "err");
      return;
    }
    if (passwordStrength < 3) {
      triggerToast("Please choose a stronger password", "err");
      return;
    }
    setBusy(true);
    try {
      await apiCall<any>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: usernameInput,
          password: passwordInput
        })
      });
      triggerToast("Registration successful! You can now log in.", "ok");
      setAuthMode("login");
      setPasswordInput("");
    } catch (err: any) {
      triggerToast(err.message || "Registration failed", "err");
    } finally {
      setBusy(false);
    }
  };

  // Real-time email validation
  useEffect(() => {
    if (!emailInput) {
      setEmailValid(null);
      return;
    }
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    setEmailValid(regex.test(emailInput));
  }, [emailInput]);

  // Real-time password strength check
  useEffect(() => {
    if (!passwordInput) {
      setPasswordStrength(0);
      return;
    }
    let score = 0;
    if (passwordInput.length >= 8) score++;
    if (/[a-z]/.test(passwordInput)) score++;
    if (/[A-Z]/.test(passwordInput)) score++;
    if (/[0-9]/.test(passwordInput)) score++;
    if (/[^a-zA-Z0-9]/.test(passwordInput)) score++;
    setPasswordStrength(score);
  }, [passwordInput]);

  // --- Vector Memory Explorer Handlers ---
  const loadVectorMemories = async () => {
    setVectorLoading(true);
    try {
      const res = await apiCall<any>("/api/admin/vector-memories");
      setVectorMemories(res.vector_memories || []);
    } catch (err: any) {
      triggerToast(err.message || "Failed to load vector memories", "err");
    } finally {
      setVectorLoading(false);
    }
  };

  const handleAddVectorMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVectorDoc.trim()) return;
    try {
      await apiCall("/api/admin/vector-memories", {
        method: "POST",
        body: JSON.stringify({ document: newVectorDoc })
      });
      setNewVectorDoc("");
      triggerToast("Vector memory created successfully", "ok");
      await loadVectorMemories();
    } catch (err: any) {
      triggerToast(err.message || "Failed to add vector memory", "err");
    }
  };

  const handleUpdateVectorMemory = async (id: string) => {
    try {
      await apiCall(`/api/admin/vector-memories/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ document: editingVectorText })
      });
      setEditingVectorId(null);
      triggerToast("Vector memory updated successfully", "ok");
      await loadVectorMemories();
    } catch (err: any) {
      triggerToast(err.message || "Failed to update vector memory", "err");
    }
  };

  const handleDeleteVectorMemory = async (id: string) => {
    if (!confirm("Delete this vector memory? This will permanently remove it from the vector database.")) return;
    try {
      await apiCall(`/api/admin/vector-memories/${id}`, { method: "DELETE" });
      triggerToast("Vector memory deleted successfully", "ok");
      await loadVectorMemories();
    } catch (err: any) {
      triggerToast(err.message || "Failed to delete vector memory", "err");
    }
  };

  // --- Global Chat Search Handler ---
  const handleGlobalSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!globalSearchQuery.trim()) return;
    setGlobalSearchLoading(true);
    try {
      const res = await apiCall<any>("/api/recall/search", {
        method: "POST",
        body: JSON.stringify({ q: globalSearchQuery, limit: 15, session_id: "" })
      });
      setGlobalSearchHits(res.hits || []);
    } catch (err: any) {
      triggerToast(err.message || "Global search failed", "err");
    } finally {
      setGlobalSearchLoading(false);
    }
  };

  // --- Fetching data depending on selected Tab ---
  useEffect(() => {
    if (!auth) return;
    
    const loadTabDetails = async () => {
      try {
        if (tab === "history" || tab === "chat") {
          const res = await apiCall<any>("/api/sessions?limit=60&archived=false");
          setSessions(res.sessions || []);
          
          // Auto create or load default session id if empty
          if (!sessionId && res.sessions?.length > 0) {
            handleSelectSession(res.sessions[0].session_id);
          } else if (!sessionId) {
            handleCreateNewSession();
          }
        }
        
        if (tab === "chat" && sessionId) {
          loadSessionMessages(sessionId);
        }

        if (tab === "dashboard") {
          // Fetch analytics summary and health checks
          const [summary, sysHealth, ollama] = await Promise.all([
            apiCall<any>("/api/analytics/summary").catch(() => null),
            apiCall<any>("/api/health").catch(() => null),
            apiCall<any>("/api/ampai/health/ollama").catch(() => null)
          ]);
          
          let dbHealthy = sysHealth?.checks?.db?.ok ?? false;
          let redisHealthy = sysHealth?.checks?.redis?.ok ?? false;
          let ollamaHealthy = ollama?.alive ?? false;

          setAdminStats(summary);
          setTelegramStatus({
            db_status: dbHealthy ? "connected" : "disconnected",
            redis_status: redisHealthy ? "connected" : "disconnected",
            ollama_status: ollamaHealthy ? "connected" : "disconnected",
            tg_connected: sysHealth?.checks?.telegram?.ok ? "connected" : "disconnected"
          });
        }

        if (tab === "memory") {
          const memoriesRes = await apiCall<any>("/api/core-memories");
          setMemories(memoriesRes.core_memories || []);
          if (memSubTab === "inbox") {
            const inboxRes = await apiCall<any>(`/api/memory/inbox?status=${inboxFilter}`);
            setMemoryInbox(inboxRes.items || inboxRes.candidates || []);
          } else if (memSubTab === "explorer" && isAdmin()) {
            await loadVectorMemories();
          }
        }

        if (tab === "tasks") {
          const data = await apiCall<any>("/api/tasks");
          setTasks(data.tasks || []);
        }

        if (tab === "browser") {
          const jobsRes = await apiCall<any>("/api/browser/jobs?limit=50").catch(() => ({ jobs: [] }));
          setBrowserJobs(jobsRes.jobs || []);
          if (isAdmin()) {
            const listRes = await apiCall<any>("/api/browser/allowlist").catch(() => ({ domains: [] }));
            setAllowlist(listRes.domains || listRes.allowlist || []);
            setBrowserEnabled(listRes.enabled ?? false);
          }
        }

        if (tab === "terminal") {
          const logsRes = await apiCall<any>("/api/terminal/logs?limit=50").catch(() => ({ logs: [] }));
          setTerminalLogs(logsRes.logs || []);
          if (isAdmin()) {
            const policyRes = await apiCall<any>("/api/terminal/policy").catch(() => null);
            if (policyRes) {
              setTerminalPolicy(policyRes);
              setTerminalEnabled(policyRes.enabled ?? false);
            }
          }
        }

        if (tab === "ai") {
          const optionsRes = await apiCall<any>("/api/models/options").catch(() => null);
          if (optionsRes) {
            setProviders(optionsRes.providers || []);
            const lists = optionsRes.models || {};
            const parsedLists: Record<string, any[]> = {};
            for (const [p, ml] of Object.entries(lists)) {
              if (Array.isArray(ml)) {
                parsedLists[p] = ml.map(m => ({ id: m, name: m }));
              }
            }
            setProviderModels(parsedLists);
          }

          const personasRes = await apiCall<any>("/api/personas").catch(() => null);
          if (personasRes) {
            setPersonas(personasRes.personas || []);
          }
        }

        if (tab === "settings" && isAdmin()) {
          const cfgs = await apiCall<any>("/api/admin/configs").catch(() => ({}));
          setConfigs(cfgs);
          const optionsRes = await apiCall<any>("/api/models/options").catch(() => null);
          if (optionsRes) setProviders(optionsRes.providers || []);
        }

        if (tab === "admin" && isAdmin()) {
          const usersRes = await apiCall<any>("/api/admin/users").catch(() => ({ users: [] }));
          setAdminUsers(usersRes.users || []);
          const bRes = await apiCall<any>("/api/admin/fullbackup/list").catch(() => ({ backups: [] }));
          setBackups(bRes.backups || []);
          const statusRes = await apiCall<any>("/api/admin/update/status").catch(() => null);
          if (statusRes) {
            setUpdateStatus(statusRes);
            setUpdateLogs(statusRes.log_lines || []);
          }
        }
      } catch (err: any) {
        triggerToast(err.message || "Failed to load tab data", "err");
      }
    };

    loadTabDetails();
  }, [tab, auth, memSubTab, inboxFilter]);

  // --- One-Click System Updater Polling and Scrolling ---
  useEffect(() => {
    if (tab !== "admin" || !auth || !isAdmin()) return;

    let intervalId: any = null;

    const pollStatus = async () => {
      try {
        const statusRes = await apiCall<any>("/api/admin/update/status");
        setUpdateStatus(statusRes);
        setUpdateLogs(statusRes.log_lines || []);
        setIsReconnecting(false);
      } catch (err: any) {
        // If we were running, a fetch failure means the uvicorn backend container went offline to rebuild/restart
        if (updateStatus?.state === "running" || isReconnecting) {
          setIsReconnecting(true);
        }
      }
    };

    if (updateStatus?.state === "running" || isReconnecting) {
      intervalId = setInterval(pollStatus, 2000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [tab, auth, updateStatus?.state, isReconnecting]);

  useEffect(() => {
    if (updateLogsEndRef.current) {
      updateLogsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [updateLogs]);

  const triggerSystemUpdate = async () => {
    if (!confirm("Are you sure you want to rebuild and update the system? The server will go offline for 10-20 seconds during container recreation.")) return;
    setIsTriggeringUpdate(true);
    try {
      await apiCall<any>("/api/admin/update/trigger", { method: "POST" });
      triggerToast("Update started successfully. Monitoring progress...", "ok");
      setUpdateStatus({ state: "running", log_lines: ["Update triggered, resetting container..."] });
    } catch (err: any) {
      triggerToast(err.message || "Failed to trigger update", "err");
    } finally {
      setIsTriggeringUpdate(false);
    }
  };

  const handleDownloadFullBackup = async () => {
    setBusy(true);
    try {
      const response = await fetch(`${serverUrl}/api/admin/backup`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${auth?.token}`
        }
      });
      if (!response.ok) {
        const errText = await response.text().catch(() => "");
        throw new Error(errText || `Server returned code ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      
      const disposition = response.headers.get("content-disposition");
      let filename = `ampai_backup_${new Date().toISOString().slice(0,19).replace(/[:]/g,"-")}.tar.gz`;
      if (disposition && disposition.indexOf("attachment") !== -1) {
        const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
        if (matches != null && matches[1]) { 
          filename = matches[1].replace(/['"]/g, "");
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      triggerToast("Physical system backup downloaded successfully!", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to download system backup", "err");
    } finally {
      setBusy(false);
    }
  };

  const handleExecuteRestore = async () => {
    if (!restoreFile) {
      triggerToast("Please select or drop a backup file first", "err");
      return;
    }
    setRestoreBusy(true);
    setShowRestoreConfirm(false);
    
    const formData = new FormData();
    formData.append("backup_file", restoreFile);
    
    try {
      const response = await fetch(`${serverUrl}/api/admin/restore`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${auth?.token}`
        },
        body: formData
      });
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned code ${response.status}`);
      }
      
      triggerToast("System restore completed successfully! Refreshing page...", "ok");
      setRestoreFile(null);
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      triggerToast(err.message || "System restore failed", "err");
    } finally {
      setRestoreBusy(false);
    }
  };

  // Scroll helper
  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
    setIsAutoScrollPinned(isAtBottom);
  };

  useEffect(() => {
    if (isAutoScrollPinned) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [msgs, isAutoScrollPinned]);

  // Dynamic model fetching when provider changes
  useEffect(() => {
    if (!auth) return;
    const fetchModels = async () => {
      try {
        const res = await apiCall<any>(`/api/models/fetch/${modelType}`);
        if (res && Array.isArray(res.models)) {
          setProviderModels(prev => ({
            ...prev,
            [modelType]: res.models.map((m: any) => ({ id: m.id, name: m.name, free: m.free }))
          }));
          
          // Filter to free models if OpenRouter
          const list = modelType === "openrouter"
            ? res.models.filter((m: any) => m.free)
            : res.models;
            
          if (list.length > 0) {
            const exists = list.some((m: any) => m.id === modelName);
            if (!exists) {
              setModelName(list[0].id);
            }
          } else {
            setModelName("");
          }
        }
      } catch (err) {
        console.error("Error fetching models for " + modelType, err);
      }
    };
    fetchModels();
  }, [modelType, auth]);

  // --- Session Management Functions ---
  const handleSelectSession = async (sid: string) => {
    setSessionId(sid);
    localStorage.setItem(SESSK, sid);
    S.sessionId = sid;
    await loadSessionMessages(sid);
    if (tab !== "chat") setTab("chat");
  };

  const loadSessionMessages = async (sid: string) => {
    try {
      const data = await apiCall<any>(`/api/history/${encodeURIComponent(sid)}`);
      const list = (data.messages || []).map((m: any) => ({
        role: m.type === "human" ? ("user" as const) : ("assistant" as const),
        content: m.content || "",
        time: ""
      }));
      setMsgs(list);
    } catch (err: any) {
      triggerToast("Failed to load chat history: " + err.message, "err");
    }
  };

  const handleCreateNewSession = async () => {
    try {
      const sid = globalThis.crypto?.randomUUID?.() || `s-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const res = await apiCall<any>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          title: `New Chat Session`,
          category: "Uncategorized"
        })
      });
      // Fetch latest list
      const listRes = await apiCall<any>("/api/sessions?limit=40&archived=false");
      setSessions(listRes.sessions || []);
      setSessionId(res.session_id);
      localStorage.setItem(SESSK, res.session_id);
      S.sessionId = res.session_id;
      setMsgs([]);
      triggerToast("New chat session created", "ok");
    } catch (err: any) {
      triggerToast("Failed to create new session: " + err.message, "err");
    }
  };

  const handleDeleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat session?")) return;
    try {
      await apiCall(`/api/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
      setSessions(prev => prev.filter(s => s.session_id !== sid));
      if (sessionId === sid) {
        setSessionId("");
        setMsgs([]);
      }
      triggerToast("Session deleted", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to delete session", "err");
    }
  };

  const handleRenameSession = async (sid: string, newTitle: string) => {
    try {
      await apiCall(`/api/sessions/${encodeURIComponent(sid)}`, {
        method: "PATCH",
        body: JSON.stringify({ title: newTitle })
      });
      setSessions(prev => prev.map(s => s.session_id === sid ? { ...s, title: newTitle } : s));
      setEditingSessionId(null);
      triggerToast("Session renamed", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to rename session", "err");
    }
  };

  const handleTogglePinSession = async (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    const newValue = !s.pinned;
    try {
      await apiCall(`/api/sessions/${encodeURIComponent(s.session_id)}`, {
        method: "PATCH",
        body: JSON.stringify({ pinned: newValue })
      });
      setSessions(prev => prev.map(x => x.session_id === s.session_id ? { ...x, pinned: newValue } : x));
      triggerToast(newValue ? "Session pinned" : "Session unpinned", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to pin session", "err");
    }
  };

  const handleToggleArchiveSession = async (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    const newValue = !s.archived;
    try {
      await apiCall(`/api/sessions/${encodeURIComponent(s.session_id)}`, {
        method: "PATCH",
        body: JSON.stringify({ archived: newValue })
      });
      setSessions(prev => prev.filter(x => x.session_id !== s.session_id));
      triggerToast(newValue ? "Session archived" : "Session restored", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to archive session", "err");
    }
  };

  const handleSaveCategory = async (sid: string, cat: string) => {
    try {
      await apiCall(`/api/sessions/${encodeURIComponent(sid)}`, {
        method: "PATCH",
        body: JSON.stringify({ category: cat })
      });
      setSessions(prev => prev.map(s => s.session_id === sid ? { ...s, category: cat } : s));
      setCategoryModalSessionId(null);
      triggerToast("Category updated", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to save category", "err");
    }
  };

  // --- Attachment Ingestion / Upload ---
  const uploadFile = async (file: File) => {
    const tempId = Math.random().toString(36).substring(2);
    
    // Add temp file chip
    const tempAttach: any = {
      filename: file.name,
      url: "",
      type: file.type || "text/plain",
      extracted_text: null,
      size: file.size,
      status: "uploading",
      tempId: tempId
    };
    setAttachments(prev => [...prev, tempAttach]);
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const payload = await apiCall<Attach>(`/api/upload?session_id=${encodeURIComponent(sessionId)}`, {
        method: "POST",
        body: formData
      });
      
      // Success: transition to indexing
      setAttachments(prev => prev.map(a => {
        if (a.tempId === tempId) {
          return {
            ...a,
            ...payload,
            status: "indexing"
          };
        }
        return a;
      }));
      
      // Simulate indexing transition to ready
      setTimeout(() => {
        setAttachments(prev => prev.map(a => {
          if (a.tempId === tempId) {
            return {
              ...a,
              status: "ready"
            };
          }
          return a;
        }));
        triggerToast(`Indexed ${file.name} successfully`, "ok");
      }, 1200);

    } catch (err: any) {
      setAttachments(prev => prev.map(a => {
        if (a.tempId === tempId) {
          return {
            ...a,
            status: "failed"
          };
        }
        return a;
      }));
      triggerToast(`Upload failed: ${err.message}`, "err");
    }
  };

  const handleAttachFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    await uploadFile(file);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      await uploadFile(file);
    }
  };

  // --- Send Chat Message with Real-time SSE Token Streaming ---
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() && attachments.length === 0) return;
    if (busy) return;

    const currentMsgText = inputText;
    setInputText("");
    setBusy(true);

    const userMsg: Msg = {
      role: "user",
      content: currentMsgText || "(Attachment attached)",
      time: new Date().toLocaleTimeString()
    };
    setMsgs(prev => [...prev, userMsg]);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (auth?.token) {
        headers["Authorization"] = `Bearer ${auth.token}`;
      }

      const res = await fetch(`${serverUrl}/api/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          message: currentMsgText || "Please review the attached file.",
          model_type: modelType,
          model_name: modelName || undefined,
          memory_mode: "indexed",
          use_web_search: useWebSearch,
          enable_browser_tools: enableBrowserTools,
          enable_terminal_tools: enableTerminalTools,
          attachments: attachments.map(a => ({
            filename: a.filename,
            url: a.url,
            type: a.type,
            extracted_text: a.extracted_text
          }))
        })
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || res.statusText);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("Stream reader not available");

      const decoder = new TextDecoder();
      let buffer = "";
      
      const aiMsgId = Math.random().toString();
      setMsgs(prev => [...prev, {
        role: "assistant",
        content: "",
        time: new Date().toLocaleTimeString(),
        id: aiMsgId
      } as any]);

      setAttachments([]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;
          
          try {
            const rawData = trimmed.slice(6);
            const parsed = JSON.parse(rawData);

            if (parsed.type === "status") {
              setActiveAgentStatus({
                status: parsed.status,
                message: parsed.message
              });
            } else if (parsed.type === "token") {
              setActiveAgentStatus(null);
              setMsgs(prev => prev.map(m => {
                if ((m as any).id === aiMsgId) {
                  return {
                    ...m,
                    content: m.content + parsed.token
                  };
                }
                return m;
              }));
            } else if (parsed.type === "done") {
              const meta = parsed.metadata;
              setMsgs(prev => prev.map(m => {
                if ((m as any).id === aiMsgId) {
                  return {
                    ...m,
                    retrieval: meta.retrieval,
                    web_search: meta.web_search,
                    memory_status: meta.memory_status,
                    recall_used: meta.recall_used
                  };
                }
                return m;
              }));
            }
          } catch (e) {
            console.error("SSE parse error", e);
          }
        }
      }

    } catch (err: any) {
      triggerToast("Failed to stream: " + err.message, "err");
      setMsgs(prev => [...prev, { role: "assistant", content: `Streaming Error: ${err.message}`, time: "" }]);
    } finally {
      setBusy(false);
      setActiveAgentStatus(null);
    }
  };

  // --- Tasks Handlers ---
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    try {
      await apiCall("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: newTaskTitle,
          description: newTaskDesc,
          priority: newTaskPriority,
          due_at: newTaskDue || null,
          session_id: sessionId || null
        })
      });
      setNewTaskTitle("");
      setNewTaskDesc("");
      setNewTaskDue("");
      // reload
      const res = await apiCall<any>("/api/tasks");
      setTasks(res.tasks || []);
      triggerToast("Task added successfully", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to create task", "err");
    }
  };

  const handleUpdateTaskStatus = async (id: number, status: "todo" | "in_progress" | "done") => {
    try {
      await apiCall(`/api/tasks/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status })
      });
      setTasks(prev => prev.map(t => t.id === id ? { ...t, status } : t));
      triggerToast(`Task moved to ${status.replace("_", " ")}`, "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to move task", "err");
    }
  };

  const handleDeleteTask = async (id: number) => {
    if (!confirm("Delete this task?")) return;
    try {
      await apiCall(`/api/tasks/${id}`, { method: "DELETE" });
      setTasks(prev => prev.filter(t => t.id !== id));
      triggerToast("Task deleted", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to delete task", "err");
    }
  };

  // --- Core Memories Handlers ---
  const handleAddFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFact.trim()) return;
    try {
      await apiCall("/api/core-memories", {
        method: "POST",
        body: JSON.stringify({ fact: newFact })
      });
      setNewFact("");
      const res = await apiCall<any>("/api/core-memories");
      setMemories(res.core_memories || []);
      triggerToast("Fact added to core memory", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to add fact", "err");
    }
  };

  const handleDeleteFact = async (id: number) => {
    if (!confirm("Remove this fact from core memory?")) return;
    try {
      await apiCall(`/api/core-memories/${id}`, { method: "DELETE" });
      setMemories(prev => prev.filter(m => m.id !== id));
      triggerToast("Memory fact removed", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to delete fact", "err");
    }
  };

  const handleUpdateFactText = async (id: number) => {
    try {
      await apiCall(`/api/core-memories/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ fact: editingFactText })
      });
      setMemories(prev => prev.map(m => m.id === id ? { ...m, fact: editingFactText } : m));
      setEditingMemId(null);
      triggerToast("Core memory updated", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to update memory fact", "err");
    }
  };

  const handleMemoryFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);
    
    setMemoryFileLoading(true);
    setCuratedFacts([]);
    setSelectedFacts({});
    
    try {
      const uploadRes = await apiCall<any>("/api/upload", {
        method: "POST",
        body: formData
      });
      
      const extractedText = uploadRes.extracted_text || "";
      if (!extractedText.trim()) {
        triggerToast("Failed to extract text from file or file is empty.", "err");
        setMemoryFileLoading(false);
        return;
      }
      
      const curateRes = await apiCall<any>("/api/memory/curate-text", {
        method: "POST",
        body: JSON.stringify({
          text: extractedText,
          model_type: modelType
        })
      });
      
      const facts = curateRes.facts || [];
      if (facts.length === 0) {
        triggerToast("No memory facts could be extracted from this document.", "info");
      } else {
        setCuratedFacts(facts);
        const initialSelections: Record<number, boolean> = {};
        facts.forEach((_: any, idx: number) => {
          initialSelections[idx] = true;
        });
        setSelectedFacts(initialSelections);
        triggerToast(`Extracted ${facts.length} candidate facts.`, "ok");
      }
    } catch (err: any) {
      triggerToast(err.message || "Failed to process file.", "err");
    } finally {
      setMemoryFileLoading(false);
    }
  };

  const handleToggleFactSelection = (idx: number) => {
    setSelectedFacts(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  const handleSaveSelectedFacts = async () => {
    const factsToSave = curatedFacts.filter((_, idx) => selectedFacts[idx]);
    if (factsToSave.length === 0) {
      triggerToast("No facts selected to save.", "info");
      return;
    }
    
    setBusy(true);
    let savedCount = 0;
    try {
      for (const fact of factsToSave) {
        await apiCall("/api/memory/core", {
          method: "POST",
          body: JSON.stringify({ text: fact })
        });
        savedCount++;
      }
      
      triggerToast(`Saved ${savedCount} facts to Core Memory successfully.`, "ok");
      setCuratedFacts([]);
      setSelectedFacts({});
      
      const memoriesRes = await apiCall<any>("/api/core-memories");
      setMemories(memoriesRes.core_memories || []);
    } catch (err: any) {
      triggerToast(err.message || "Failed to save some facts.", "err");
    } finally {
      setBusy(false);
    }
  };

  const handleInboxAction = async (id: string, action: "approved" | "rejected", textToSave?: string) => {
    try {
      await apiCall(`/api/memory/inbox/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: action,
          edited_text: textToSave || null
        })
      });
      setMemoryInbox(prev => prev.filter(item => item.id !== id));
      triggerToast(`Fact successfully ${action}`, "ok");
      
      // If approved, refresh core memories
      if (action === "approved") {
        const memoriesRes = await apiCall<any>("/api/core-memories");
        setMemories(memoriesRes.core_memories || []);
      }
    } catch (err: any) {
      triggerToast(err.message || "Action failed", "err");
    }
  };

  // --- Terminal Command Runner ---
  const handleTerminalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalCommand.trim()) return;
    setBusy(true);
    setTerminalOutput("Running command...");
    try {
      const res = await apiCall<any>("/api/terminal/run", {
        method: "POST",
        body: JSON.stringify({
          command: terminalCommand,
          working_directory: null
        })
      });
      if (res.blocked) {
        setTerminalOutput(`Command blocked by terminal execution policy!\nAllowed folders: ${res.allowed_folders?.join(", ") || "none"}`);
        triggerToast("Command execution blocked", "err");
      } else {
        setTerminalOutput(`Exit Code: ${res.exit_code}\nExecution Time: ${res.execution_ms}ms\n\nOutput:\n${res.output || "No output."}`);
        triggerToast("Command executed successfully", "ok");
      }
      
      // refresh logs
      const logsRes = await apiCall<any>("/api/terminal/logs?limit=50");
      setTerminalLogs(logsRes.logs || []);
    } catch (err: any) {
      setTerminalOutput(`Error: ${err.message}`);
      triggerToast("Execution failed", "err");
    } finally {
      setBusy(false);
    }
  };

  // --- Browser Allowlist handler ---
  const handleAddAllowlistDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAllowlistDomain.trim()) return;
    try {
      await apiCall("/api/browser/allowlist", {
        method: "POST",
        body: JSON.stringify({ domain: newAllowlistDomain })
      });
      setAllowlist(prev => [...prev, newAllowlistDomain]);
      setNewAllowlistDomain("");
      triggerToast("Domain added to allowlist", "ok");
    } catch (err: any) {
      triggerToast(err.message || "Failed to add domain", "err");
    }
  };

  // Mock token usage data for dashboard
  const tokenData = [
    { name: "Mon", Prompt: 14000, Completion: 4500 },
    { name: "Tue", Prompt: 19500, Completion: 6200 },
    { name: "Wed", Prompt: 16000, Completion: 5300 },
    { name: "Thu", Prompt: 23200, Completion: 8100 },
    { name: "Fri", Prompt: 28400, Completion: 9900 },
    { name: "Sat", Prompt: 18000, Completion: 5500 },
    { name: "Sun", Prompt: 25000, Completion: 8900 },
  ];

  // Vector DB data based on actual stats or custom distribution
  const vectorDocCount = adminStats?.total_memories || 0;
  const vectorDocData = [
    { name: "General Facts", Count: Math.floor(vectorDocCount * 0.4) },
    { name: "User Prefs", Count: Math.floor(vectorDocCount * 0.25) },
    { name: "Context Logs", Count: Math.floor(vectorDocCount * 0.15) },
    { name: "Web Clippings", Count: Math.floor(vectorDocCount * 0.10) },
    { name: "Code Snippets", Count: Math.floor(vectorDocCount * 0.10) },
  ];

  // System stats details
  const totalMsgs = adminStats?.total_messages || 0;
  const totalSess = adminStats?.total_sessions || 0;
  const avgTokens = adminStats?.avg_injected_memory_tokens || 0;

  // Filtered Sessions List
  const filteredSessions = sessions.filter(s => {
    const matchesSearch = s.title?.toLowerCase().includes(sessionSearch.toLowerCase()) || 
                          s.category?.toLowerCase().includes(sessionSearch.toLowerCase());
    const matchesCategory = !sessionCategoryFilter || s.category === sessionCategoryFilter;
    return matchesSearch && matchesCategory;
  });

  // Unique categories list for filters
  const sessionCategories = Array.from(new Set(sessions.map(s => s.category).filter(Boolean)));

  // Tasks Filtered list
  const filteredTasks = tasks.filter(t => {
    const matchesSearch = t.title.toLowerCase().includes(taskSearch.toLowerCase()) || 
                          (t.description || "").toLowerCase().includes(taskSearch.toLowerCase());
    const matchesPriority = !taskPriorityFilter || t.priority === taskPriorityFilter;
    return matchesSearch && matchesPriority;
  });

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden relative">
      
      {/* Toast Notification */}
      {toastMsg && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-2xl transition-all duration-300 transform translate-y-0 flex items-center space-x-3 border ${
          toastMsg.type === "ok" 
            ? "bg-emerald-950/90 text-emerald-300 border-emerald-500/30" 
            : toastMsg.type === "err" 
              ? "bg-rose-950/90 text-rose-300 border-rose-500/30" 
              : "bg-slate-900/90 text-indigo-300 border-indigo-500/30"
        }`}>
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm font-medium">{toastMsg.text}</span>
        </div>
      )}

      {/* --- Sidebar Navigation (Desktop) --- */}
      {auth && (
        <aside className={`hidden md:flex flex-col flex-shrink-0 h-full glass-panel border-r border-slate-800 transition-all duration-300 ${
          sidebarCollapsed ? "w-20" : "w-64"
        }`}>
          {/* Logo Brand Header */}
          <div className="flex items-center space-x-3 p-4 border-b border-slate-800/60 overflow-hidden h-16">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <span className="font-bold text-lg bg-gradient-to-r from-white via-indigo-200 to-purple-400 bg-clip-text text-transparent truncate tracking-tight">
                AmpAI System
              </span>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 py-4 space-y-1.5 px-3 overflow-y-auto">
            {[
              { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
              { id: "chat", label: "Agent Chat", icon: MessageSquare },
              { id: "memory", label: "Cognitive Memory", icon: Brain },
              { id: "tasks", label: "Task Board", icon: ClipboardList },
              { id: "browser", label: "Web Automation", icon: Globe },
              { id: "terminal", label: "Shell Terminal", icon: Terminal },
              { id: "ai", label: "AI Models & Personas", icon: Sliders },
              ...(isAdmin() ? [
                { id: "settings", label: "System Config", icon: Shield },
                { id: "admin", label: "Admin Console", icon: User }
              ] : [])
            ].map(item => {
              const Icon = item.icon;
              const active = tab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setTab(item.id)}
                  title={item.label}
                  className={`flex items-center space-x-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group relative ${
                    active 
                      ? "bg-gradient-to-r from-indigo-600/30 to-purple-600/10 text-indigo-300 border-l-2 border-indigo-500" 
                      : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200"
                  }`}
                >
                  <Icon className={`w-5 h-5 flex-shrink-0 transition-transform group-hover:scale-105 ${active ? "text-indigo-400" : "text-slate-400"}`} />
                  {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
                </button>
              );
            })}
          </nav>

          {/* Sidebar Footer Accent Picker & Toggle */}
          <div className="p-3 border-t border-slate-800/60 bg-slate-950/40">
            {!sidebarCollapsed && (
              <div className="mb-4">
                <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider block mb-2 px-1">Accent Theme</span>
                <div className="grid grid-cols-4 gap-1.5 px-1">
                  {ACCENT_COLORS.map(color => (
                    <button
                      key={color.name}
                      onClick={() => setThemeAccent(color.value)}
                      title={color.name}
                      style={{ backgroundColor: color.value }}
                      className={`h-5 w-full rounded-md cursor-pointer transition-all hover:scale-110 relative ${
                        themeAccent === color.value ? "ring-2 ring-white ring-offset-2 ring-offset-slate-900" : ""
                      }`}
                    />
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <button
                onClick={() => handleLogout()}
                className="flex items-center space-x-3 px-3 py-2 text-rose-400 hover:bg-rose-950/20 rounded-xl transition-all w-full text-sm font-medium group"
              >
                <LogOut className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
                {!sidebarCollapsed && <span>Logout</span>}
              </button>
              
              <button
                onClick={() => {
                  const collapsed = !sidebarCollapsed;
                  setSidebarCollapsed(collapsed);
                  localStorage.setItem("ampai.sidebarCollapsed", collapsed ? "1" : "0");
                }}
                className="hidden md:block p-1.5 text-slate-500 hover:text-slate-300 hover:bg-slate-900 rounded-lg transition-all"
              >
                {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* --- Sidebar Navigation Overlay (Mobile Drawer) --- */}
      {auth && sidebarMobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          {/* Drawer backdrop */}
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSidebarMobileOpen(false)}></div>
          
          <aside className="relative flex flex-col w-64 max-w-xs h-full bg-slate-950 border-r border-slate-800 p-4 space-y-4 shadow-2xl animate-slide-in">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-6 h-6 text-indigo-400" />
                <span className="font-bold text-lg bg-gradient-to-r from-white to-indigo-300 bg-clip-text text-transparent">AmpAI</span>
              </div>
              <button onClick={() => setSidebarMobileOpen(false)} className="p-1.5 text-slate-400 hover:text-white rounded-lg bg-slate-900">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <nav className="flex-1 space-y-1 overflow-y-auto">
              {[
                { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
                { id: "chat", label: "Agent Chat", icon: MessageSquare },
                { id: "memory", label: "Cognitive Memory", icon: Brain },
                { id: "tasks", label: "Task Board", icon: ClipboardList },
                { id: "browser", label: "Web Automation", icon: Globe },
                { id: "terminal", label: "Shell Terminal", icon: Terminal },
                { id: "ai", label: "AI Models & Personas", icon: Sliders },
                ...(isAdmin() ? [
                  { id: "settings", label: "System Config", icon: Shield },
                  { id: "admin", label: "Admin Console", icon: User }
                ] : [])
              ].map(item => {
                const Icon = item.icon;
                const active = tab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setTab(item.id);
                      setSidebarMobileOpen(false);
                    }}
                    className={`flex items-center space-x-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium ${
                      active ? "bg-indigo-600/30 text-indigo-300 border-l-2 border-indigo-500" : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
            
            <div className="border-t border-slate-800/80 pt-4">
              <button
                onClick={() => {
                  handleLogout();
                  setSidebarMobileOpen(false);
                }}
                className="flex items-center space-x-3 px-3 py-2 text-rose-400 hover:bg-rose-950/20 rounded-xl w-full text-sm font-medium"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* --- Main Area Window --- */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950/45">
        
        {/* Mobile Header (Shows when authenticated on small screens) */}
        {auth && (
          <header className="md:hidden flex items-center justify-between px-4 h-16 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md sticky top-0 z-30">
            <button onClick={() => setSidebarMobileOpen(true)} className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-900">
              <Menu className="w-6 h-6" />
            </button>
            <span className="font-semibold text-slate-200 capitalize">{tab.replace("_", " ")}</span>
            <div className="flex items-center space-x-1.5">
              <div className={`h-2.5 w-2.5 rounded-full ${health.ok ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}></div>
              <span className="text-xs text-slate-400">{health.status}</span>
            </div>
          </header>
        )}

        {/* Outer body */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          
          {/* ==========================================
              LOGIN & REGISTER VIEW
             ========================================== */}
          {tab === "account" && !auth && (
            <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-radial-gradient-to-tr from-slate-950 to-indigo-950/20">
              <div className="max-w-md w-full space-y-8 glass-panel p-8 rounded-3xl shadow-2xl relative border border-slate-800">
                
                <div className="absolute top-0 right-0 p-4">
                  <div className="flex items-center space-x-1.5">
                    <span className="text-xs text-slate-500">Host Connection:</span>
                    <div className={`h-2.5 w-2.5 rounded-full ${health.ok ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}></div>
                    <span className="text-xs font-semibold text-slate-400 capitalize">{health.status}</span>
                  </div>
                </div>

                <div className="text-center">
                  <div className="mx-auto h-12 w-12 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                    <Lock className="h-6 h-6 text-white" />
                  </div>
                  <h2 className="mt-6 text-3xl font-extrabold text-white tracking-tight">
                    {authMode === "login" ? "Welcome back" : "Create system account"}
                  </h2>
                  <p className="mt-2 text-sm text-slate-400">
                    {authMode === "login" ? (
                      <>
                        New user?{" "}
                        <button onClick={() => setAuthMode("register")} className="font-semibold text-indigo-400 hover:text-indigo-300">
                          Register account
                        </button>
                      </>
                    ) : (
                      <>
                        Already registered?{" "}
                        <button onClick={() => setAuthMode("login")} className="font-semibold text-indigo-400 hover:text-indigo-300">
                          Log in
                        </button>
                      </>
                    )}
                  </p>
                </div>

                <form className="mt-8 space-y-6" onSubmit={authMode === "login" ? handleLoginSubmit : handleRegisterSubmit}>
                  <div className="rounded-md space-y-4">
                    {/* Username Input */}
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Username / Login ID</label>
                      <input
                        type="text"
                        required
                        value={usernameInput}
                        onChange={(e) => setUsernameInput(e.target.value)}
                        placeholder="admin or username"
                        className="appearance-none relative block w-full px-4 py-3 border border-slate-800 placeholder-slate-500 text-slate-100 rounded-2xl bg-slate-900/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all text-sm"
                      />
                    </div>

                    {/* Email Input (Register only) */}
                    {authMode === "register" && (
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Email Address</label>
                        <input
                          type="email"
                          value={emailInput}
                          onChange={(e) => setEmailInput(e.target.value)}
                          placeholder="user@example.com"
                          className={`appearance-none relative block w-full px-4 py-3 border placeholder-slate-500 text-slate-100 rounded-2xl bg-slate-900/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all text-sm ${
                            emailValid === false ? "border-rose-500 focus:ring-rose-500/50" : "border-slate-800 focus:border-indigo-500"
                          }`}
                        />
                        {emailValid === false && (
                          <p className="mt-1.5 text-xs text-rose-400 flex items-center">
                            <AlertCircle className="w-3.5 h-3.5 mr-1" />
                            Please enter a valid email format
                          </p>
                        )}
                      </div>
                    )}

                    {/* Password Input */}
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Secure Password</label>
                      <input
                        type="password"
                        required
                        value={passwordInput}
                        onChange={(e) => setPasswordInput(e.target.value)}
                        placeholder="••••••••"
                        className="appearance-none relative block w-full px-4 py-3 border border-slate-800 placeholder-slate-500 text-slate-100 rounded-2xl bg-slate-900/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all text-sm"
                      />
                      
                      {/* Real-time Password strength indicator (Register only) */}
                      {authMode === "register" && passwordInput && (
                        <div className="mt-2.5 space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400 font-medium">Password Strength:</span>
                            <span className={`font-semibold ${
                              passwordStrength <= 2 ? "text-rose-400" : passwordStrength <= 4 ? "text-amber-400" : "text-emerald-400"
                            }`}>
                              {passwordStrength <= 2 ? "Weak" : passwordStrength <= 4 ? "Medium" : "Strong"}
                            </span>
                          </div>
                          
                          {/* Progress bar */}
                          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all duration-300 ${
                                passwordStrength <= 2 ? "bg-rose-500" : passwordStrength <= 4 ? "bg-amber-500" : "bg-emerald-500"
                              }`}
                              style={{ width: `${(passwordStrength / 5) * 100}%` }}
                            />
                          </div>
                          
                          {/* Guidelines checklist */}
                          <ul className="text-slate-500 text-[11px] grid grid-cols-2 gap-x-2 gap-y-1 pl-1">
                            <li className={`flex items-center ${passwordInput.length >= 8 ? "text-emerald-400" : ""}`}>
                              <Check className="w-3 h-3 mr-1" /> 8+ characters
                            </li>
                            <li className={`flex items-center ${/[a-z]/.test(passwordInput) ? "text-emerald-400" : ""}`}>
                              <Check className="w-3 h-3 mr-1" /> Lowercase letter
                            </li>
                            <li className={`flex items-center ${/[A-Z]/.test(passwordInput) ? "text-emerald-400" : ""}`}>
                              <Check className="w-3 h-3 mr-1" /> Uppercase letter
                            </li>
                            <li className={`flex items-center ${/[0-9]/.test(passwordInput) ? "text-emerald-400" : ""}`}>
                              <Check className="w-3 h-3 mr-1" /> Number digit
                            </li>
                            <li className={`flex items-center ${/[^a-zA-Z0-9]/.test(passwordInput) ? "text-emerald-400" : ""}`}>
                              <Check className="w-3 h-3 mr-1" /> Special char
                            </li>
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          const url = prompt("Set server backend URL:", serverUrl);
                          if (url) {
                            setServerUrl(url);
                            localStorage.setItem("ampai.serverUrl", url);
                            checkServerHealth(url);
                          }
                        }}
                        className="font-medium text-slate-500 hover:text-slate-300 transition-colors"
                      >
                        Configure backend URL
                      </button>
                    </div>
                  </div>

                  <div>
                    <button
                      type="submit"
                      disabled={busy}
                      className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-semibold rounded-2xl text-white bg-gradient-to-tr from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 shadow-lg shadow-indigo-500/10 hover:shadow-indigo-500/25 active:scale-98 transition-all disabled:opacity-50"
                    >
                      {busy ? (
                        <RefreshCw className="w-5 h-5 animate-spin text-white" />
                      ) : authMode === "login" ? (
                        "Access Dashboard"
                      ) : (
                        "Create Account"
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* ==========================================
              DASHBOARD VIEW (Live/Mocked metrics)
             ========================================== */}
          {tab === "dashboard" && auth && (
            <div className="space-y-6 max-w-7xl mx-auto">
              
              {/* Header block */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/40 p-5 rounded-2xl border border-slate-800/60">
                <div>
                  <h1 className="text-2xl font-bold text-white tracking-tight flex items-center space-x-2">
                    <span>System Analytics Dashboard</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-semibold border border-indigo-500/30">Live</span>
                  </h1>
                  <p className="text-sm text-slate-400 mt-1">Real-time status overview of vector stores, API consumption and microservice connectivity.</p>
                </div>
                <button
                  onClick={() => {
                    setTab("dashboard");
                    triggerToast("Refreshing dashboard...", "info");
                  }}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700/80 rounded-xl transition-all border border-slate-700/60 flex items-center space-x-2 active:scale-95 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Refresh Stats</span>
                </button>
              </div>

              {/* Grid 1: Stat Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: "Active Chat Sessions", value: totalSess, desc: "Total workspace contexts", gradient: "from-blue-600/10 to-indigo-600/5", border: "border-blue-500/20", icon: MessageSquare, iconColor: "text-blue-400" },
                  { label: "Total Chat Messages", value: totalMsgs, desc: "Agent input/output statements", gradient: "from-purple-600/10 to-pink-600/5", border: "border-purple-500/20", icon: History, iconColor: "text-purple-400" },
                  { label: "Core Memory Facts", value: vectorDocCount, desc: "Persisted semantic entities", gradient: "from-emerald-600/10 to-teal-600/5", border: "border-emerald-500/20", icon: Brain, iconColor: "text-emerald-400" },
                  { label: "Avg Memory Injection", value: `${Math.round(avgTokens)} tokens`, desc: "Prompt contextual load size", gradient: "from-amber-600/10 to-orange-600/5", border: "border-amber-500/20", icon: Activity, iconColor: "text-amber-400" }
                ].map((stat, i) => (
                  <div key={i} className={`p-5 rounded-2xl border bg-slate-900/60 shadow-lg relative overflow-hidden group hover:scale-[1.01] transition-all duration-300 ${stat.border}`}>
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <span className="text-xs text-slate-400 font-semibold tracking-wider uppercase block">{stat.label}</span>
                        <span className="text-3xl font-extrabold text-white tracking-tight block">{stat.value}</span>
                        <span className="text-xs text-slate-500 block">{stat.desc}</span>
                      </div>
                      <div className={`p-2.5 rounded-xl bg-slate-950/80 shadow border border-slate-800 ${stat.iconColor}`}>
                        <stat.icon className="w-5 h-5" />
                      </div>
                    </div>
                    {/* Visual gradient mesh overlay */}
                    <div className="absolute inset-0 bg-gradient-to-tr opacity-25 -z-10 transition-opacity duration-300 group-hover:opacity-35 pointer-events-none" style={{ backgroundImage: `linear-gradient(to top right, var(--tw-gradient-stops))` }}></div>
                  </div>
                ))}
              </div>

              {/* Grid 2: Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Chart A: API Token Usage */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800/80">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h3 className="font-bold text-slate-200">API Token Consumption</h3>
                      <p className="text-xs text-slate-500">Historical weekly token allocations for prompts and completions</p>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-semibold border border-indigo-500/20">Ollama/OpenAPI</span>
                  </div>
                  
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={tokenData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorPrompt" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorCompletion" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                        <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px", color: "#f8fafc" }} />
                        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                        <Area type="monotone" dataKey="Prompt" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorPrompt)" />
                        <Area type="monotone" dataKey="Completion" stroke="#a855f7" strokeWidth={2} fillOpacity={1} fill="url(#colorCompletion)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Chart B: Vector Database Document Counts */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800/80">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h3 className="font-bold text-slate-200">Vector Memory Density</h3>
                      <p className="text-xs text-slate-500">Document partitions indexed inside pgvector database</p>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/20">pgvector</span>
                  </div>

                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={vectorDocData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                        <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px", color: "#f8fafc" }} />
                        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                        <Bar dataKey="Count" fill="#10b981" radius={[4, 4, 0, 0]} barSize={35} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Section 3: Microservice Connectivity Status Grid */}
              <div className="glass-panel p-5 rounded-2xl border border-slate-800/80">
                <h3 className="font-bold text-slate-200 mb-4 flex items-center space-x-2">
                  <Database className="w-5 h-5 text-indigo-400" />
                  <span>Microservice Network Connectivity Status</span>
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Database Node Status */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-850 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                        <Database className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="font-semibold text-sm text-slate-200 block">PostgreSQL / pgvector</span>
                        <span className="text-xs text-slate-500 block">Relational & Vector db stores</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                        telegramStatus?.db_status === "connected" 
                          ? "bg-emerald-950/80 text-emerald-400 border-emerald-500/20" 
                          : "bg-rose-950/80 text-rose-400 border-rose-500/20"
                      }`}>
                        {telegramStatus?.db_status === "connected" ? "Healthy" : "Offline"}
                      </span>
                      <span className="text-[10px] text-slate-500 mt-1">Port 5432</span>
                    </div>
                  </div>

                  {/* Browser Automation Node */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-850 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="p-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                        <Globe className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="font-semibold text-sm text-slate-200 block">Headless Browser Node</span>
                        <span className="text-xs text-slate-500 block">Playwright Browserless execution</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="text-xs px-2 py-0.5 rounded-full font-semibold border bg-emerald-950/80 text-emerald-400 border-emerald-500/20">
                        Active
                      </span>
                      <span className="text-[10px] text-slate-500 mt-1">WebSocket WS Endpoint</span>
                    </div>
                  </div>

                  {/* Telegram Connectivity */}
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-850 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="p-2.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
                        <MessageSquare className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="font-semibold text-sm text-slate-200 block">Telegram Agent Link</span>
                        <span className="text-xs text-slate-500 block">Webhook polling sync endpoint</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                        telegramStatus?.tg_connected === "connected"
                          ? "bg-emerald-950/80 text-emerald-400 border-emerald-500/20"
                          : "bg-slate-800 text-slate-400 border-slate-700/60"
                      }`}>
                        {telegramStatus?.tg_connected === "connected" ? "Linked" : "Not configured"}
                      </span>
                      <span className="text-[10px] text-slate-500 mt-1">Webhook Status</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* ==========================================
              CHAT VIEW (Agent Interfacing & Navigation)
             ========================================== */}
          {tab === "chat" && auth && (
            <div className="flex h-[82vh] bg-slate-950/60 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl relative">
              
              {/* Internal Side Panel: Chat History / Sessions list */}
              <div className="hidden lg:flex flex-col w-72 bg-slate-950 border-r border-slate-800/80 flex-shrink-0">
                <div className="p-4 border-b border-slate-800/80 space-y-3">
                  <button
                    onClick={handleCreateNewSession}
                    className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-sm flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/15 transition-all active:scale-98 cursor-pointer"
                  >
                    <Plus className="w-4 h-4" />
                    <span>New Session</span>
                  </button>
                  
                  {/* Search sessions */}
                  <div className="flex items-center space-x-2">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        placeholder="Search chats..."
                        value={sessionSearch}
                        onChange={(e) => setSessionSearch(e.target.value)}
                        className="w-full px-3.5 py-2 pl-9 rounded-xl border border-slate-800 bg-slate-900/40 text-slate-200 placeholder-slate-500 text-xs focus:ring-1 focus:ring-indigo-500/40 focus:outline-none focus:border-indigo-500 transition-all"
                      />
                      <History className="w-3.5 h-3.5 text-slate-500 absolute left-3.5 top-3" />
                    </div>
                    <button
                      onClick={() => {
                        setShowSearchModal(true);
                        setGlobalSearchQuery("");
                        setGlobalSearchHits([]);
                      }}
                      className="p-2 rounded-xl bg-slate-900/45 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-indigo-400 transition-all cursor-pointer flex-shrink-0"
                      title="Global FTS Chat Search"
                    >
                      <Search className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Categories filtering */}
                {sessionCategories.length > 0 && (
                  <div className="px-4 py-2 flex flex-wrap gap-1 border-b border-slate-800/40">
                    <button
                      onClick={() => setSessionCategoryFilter("")}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                        !sessionCategoryFilter ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30" : "bg-slate-900 text-slate-400"
                      }`}
                    >
                      All
                    </button>
                    {sessionCategories.map(cat => (
                      <button
                        key={cat}
                        onClick={() => setSessionCategoryFilter(cat)}
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                          sessionCategoryFilter === cat ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30" : "bg-slate-900 text-slate-400"
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                )}

                {/* Session list items */}
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                  {filteredSessions.map(s => {
                    const active = s.session_id === sessionId;
                    const editing = editingSessionId === s.session_id;
                    return (
                      <div
                        key={s.session_id}
                        onClick={() => !editing && handleSelectSession(s.session_id)}
                        className={`p-3 rounded-xl cursor-pointer group transition-all relative flex flex-col space-y-1.5 border border-transparent ${
                          active 
                            ? "bg-slate-900/90 border-slate-800 text-slate-200 shadow-md shadow-slate-950/20" 
                            : "text-slate-400 hover:bg-slate-900/40 hover:text-slate-200"
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          {editing ? (
                            <input
                              type="text"
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleRenameSession(s.session_id, editingTitle);
                                if (e.key === "Escape") setEditingSessionId(null);
                              }}
                              onClick={(e) => e.stopPropagation()}
                              className="bg-slate-950 text-xs px-2 py-1 rounded text-white border border-slate-800 focus:outline-none w-[80%]"
                              autoFocus
                            />
                          ) : (
                            <span className="font-semibold text-xs truncate max-w-[80%] block">{s.title || "Untitled Session"}</span>
                          )}
                          
                          {/* Controls (visible on hover) */}
                          <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingSessionId(s.session_id);
                                setEditingTitle(s.title || "");
                              }}
                              title="Rename chat"
                              className="p-1 hover:text-indigo-400 text-slate-500 hover:bg-slate-800 rounded transition-all"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleTogglePinSession(s, e)}
                              title={s.pinned ? "Unpin session" : "Pin session"}
                              className={`p-1 rounded transition-all hover:bg-slate-800 ${
                                s.pinned ? "text-amber-400" : "text-slate-500 hover:text-amber-400"
                              }`}
                            >
                              <Pin className="w-3 h-3 fill-current" />
                            </button>
                            <button
                              onClick={(e) => handleToggleArchiveSession(s, e)}
                              title="Archive chat"
                              className="p-1 hover:text-orange-400 text-slate-500 hover:bg-slate-800 rounded transition-all"
                            >
                              <Archive className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleDeleteSession(s.session_id, e)}
                              title="Delete session"
                              className="p-1 hover:text-rose-400 text-slate-500 hover:bg-slate-800 rounded transition-all"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                        
                        <div className="flex justify-between items-center text-[10px] text-slate-500">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setCategoryModalSessionId(s.session_id);
                              setCategoryValue(s.category || "");
                            }}
                            className="hover:underline font-medium hover:text-slate-300 bg-slate-900/60 px-1.5 py-0.5 rounded border border-slate-800/80"
                          >
                            {s.category || "Uncategorized"}
                          </button>
                          <span>{s.updated_at ? new Date(s.updated_at).toLocaleDateString() : ""}</span>
                        </div>
                      </div>
                    );
                  })}
                  {filteredSessions.length === 0 && (
                    <div className="p-4 text-center text-xs text-slate-600">No sessions match search.</div>
                  )}
                </div>
              </div>

              {/* Main chat window container with Native Drag-and-Drop */}
              <div 
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                className={`flex-1 flex flex-col bg-slate-900/10 overflow-hidden relative transition-all duration-300 ${
                  dragActive ? "ring-2 ring-indigo-500/85 bg-indigo-950/25" : ""
                }`}
              >
                {/* Drag and Drop Active Overlay */}
                {dragActive && (
                  <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center z-45 space-y-4 border-2 border-dashed border-indigo-550/50 m-4 rounded-3xl pointer-events-none animate-pulse">
                    <Paperclip className="w-12 h-12 text-indigo-400" />
                    <p className="text-sm font-bold text-slate-200">Drop files here to upload and index</p>
                    <p className="text-xs text-slate-500">Supports PDF, TXT, CSV, JSON, MD, Python, JS, HTML, CSS</p>
                  </div>
                )}
                
                {/* Chat Top Settings bar */}
                <div className="px-4 py-3 border-b border-slate-800/80 flex justify-between items-center bg-slate-950/40">
                  <div className="flex flex-col">
                    <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Active Session</span>
                    <span className="text-sm font-bold text-slate-200 truncate max-w-[220px]">
                      {sessions.find(s => s.session_id === sessionId)?.title || "Select or create chat"}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <select
                      value={modelType}
                      onChange={(e) => setModelType(e.target.value)}
                      className="bg-slate-900 border border-slate-800 px-2.5 py-1.5 rounded-xl text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                    >
                      <option value="ollama">🦙 Ollama</option>
                      <option value="openai">✨ OpenAI</option>
                      <option value="gemini">🌟 Gemini</option>
                      <option value="anthropic">🔴 Anthropic</option>
                      <option value="openrouter">🔀 OpenRouter</option>
                    </select>

                    <select
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      className="bg-slate-900 border border-slate-800 px-2.5 py-1.5 rounded-xl text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 max-w-[200px]"
                    >
                      {(modelType === "openrouter" 
                        ? (providerModels[modelType] || []).filter((m: any) => m.free) 
                        : (providerModels[modelType] || [])
                      ).map((m: any) => (
                        <option key={m.id} value={m.id}>
                          {m.name || m.id}
                        </option>
                      ))}
                      {(!providerModels[modelType] || (modelType === "openrouter" 
                        ? (providerModels[modelType] || []).filter((m: any) => m.free).length === 0 
                        : (providerModels[modelType] || []).length === 0
                      )) && (
                        <option value="">No models available</option>
                      )}
                    </select>

                    <button
                      onClick={() => handleCreateNewSession()}
                      className="lg:hidden p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all"
                      title="New chat"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Messages Box scrollable with auto-scroll pinning */}
                <div 
                  ref={scrollContainerRef}
                  onScroll={handleScroll}
                  className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6"
                >
                  {msgs.map((m, idx) => (
                    <div
                      key={idx}
                      className={`flex space-x-4 max-w-3xl ${
                        m.role === "user" ? "ml-auto flex-row-reverse space-x-reverse" : "mr-auto"
                      }`}
                    >
                      {/* Avatar */}
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs flex-shrink-0 shadow ${
                        m.role === "user" 
                          ? "bg-indigo-600 text-white shadow-indigo-500/20" 
                          : "bg-slate-800 text-indigo-400 border border-slate-700/60"
                      }`}>
                        {m.role === "user" ? "ME" : "AI"}
                      </div>
                      
                      {/* Bubble with Timeline indicators */}
                      <div className="space-y-1.5 flex flex-col">
                        <span className={`text-[10px] text-slate-500 ${m.role === "user" ? "text-right" : ""}`}>
                          {m.role === "user" ? "You" : "AmpAI Assistant"}
                        </span>

                        {m.role === "assistant" && (
                          <div className="flex flex-wrap gap-2 py-0.5">
                            {/* Vector database search indicator */}
                            {((m as any).retrieval?.enabled && (m as any).retrieval?.retrieved_count > 0) && (
                              <div className="flex items-center space-x-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-450 border border-emerald-500/20 text-[10px] font-semibold">
                                <Database className="w-3 h-3 text-emerald-400" />
                                <span>Vector DB: Retrieved {(m as any).retrieval.retrieved_count} facts</span>
                              </div>
                            )}
                            
                            {/* Live web search indicator */}
                            {((m as any).web_search?.enabled && (m as any).web_search?.status === "ok") && (
                              <div className="flex items-center space-x-1 px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-450 border border-blue-500/20 text-[10px] font-semibold">
                                <Globe className="w-3 h-3 text-blue-400" />
                                <span>Web Search: {(m as any).web_search.provider}</span>
                              </div>
                            )}

                            {/* Cross-session recall indicator */}
                            {(m as any).recall_used && (
                              <div className="flex items-center space-x-1 px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-450 border border-purple-500/20 text-[10px] font-semibold">
                                <Brain className="w-3 h-3 text-purple-400" />
                                <span>Cross-Session Context Injected</span>
                              </div>
                            )}

                            {/* Simulated terminal run indicator */}
                            {(enableTerminalTools && (m.content.includes("```bash") || m.content.includes("```sh"))) && (
                              <div className="flex items-center space-x-1 px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-405 border border-violet-550/20 text-[10px] font-semibold">
                                <Terminal className="w-3 h-3 text-violet-400" />
                                <span>Terminal Tool: Shell Analysis Logged</span>
                              </div>
                            )}
                          </div>
                        )}

                        <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-lg max-w-lg ${
                          m.role === "user" 
                            ? "bg-indigo-600/90 text-white rounded-tr-none" 
                            : "bg-slate-900/90 text-slate-200 border border-slate-800 rounded-tl-none"
                        }`}>
                          {m.role === "user" ? (
                            <p className="whitespace-pre-wrap">{m.content}</p>
                          ) : (
                            <Markdown text={m.content} />
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {/* Busy loader dots + Real-time Streaming Status */}
                  {busy && (
                    <div className="flex space-x-4 max-w-3xl mr-auto">
                      <div className="w-9 h-9 rounded-xl bg-slate-800 text-indigo-400 border border-slate-700/60 flex items-center justify-center font-bold text-xs flex-shrink-0">
                        AI
                      </div>
                      <div className="space-y-1.5 flex flex-col">
                        <span className="text-[10px] text-slate-500">AmpAI Assistant</span>
                        
                        {activeAgentStatus && (
                          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-indigo-300 font-semibold animate-pulse">
                            {activeAgentStatus.status === "searching_vector_db" && <Database className="w-4 h-4 text-emerald-400" />}
                            {activeAgentStatus.status === "searching_web" && <Globe className="w-4 h-4 text-blue-400" />}
                            {activeAgentStatus.status === "executing_command" && <Terminal className="w-4 h-4 text-purple-400" />}
                            {activeAgentStatus.status === "browser_action" && <Globe className="w-4 h-4 text-cyan-400" />}
                            <span>{activeAgentStatus.message}</span>
                          </div>
                        )}

                        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 rounded-tl-none shadow-lg">
                          <div className="flex space-x-1 px-1 py-1.5">
                            <div className="w-2.5 h-2.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                            <div className="w-2.5 h-2.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                            <div className="w-2.5 h-2.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {msgs.length === 0 && !busy && (
                    <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto space-y-4">
                      <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-xl shadow-indigo-500/10">
                        <MessageSquare className="w-8 h-8 text-white animate-pulse" />
                      </div>
                      <h3 className="text-lg font-bold text-slate-200">Start a conversation</h3>
                      <p className="text-xs text-slate-500">
                        Ask any questions, command CLI actions, parse remote HTML/PDF documents or sweep local subnets directly within the workspace.
                      </p>
                    </div>
                  )}
                  
                  <div ref={chatEndRef} />
                </div>

                {/* Input action attachments container */}
                <div className="p-4 border-t border-slate-800 bg-slate-950/40 space-y-3">
                  
                  {/* Ingestion & Loading States for file chips */}
                  {attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2 p-2 bg-slate-950/80 rounded-xl border border-slate-850">
                      {attachments.map((attach, idx) => (
                        <div key={idx} className="flex items-center space-x-2 bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700/60 text-xs">
                          {/* Processing state indicator */}
                          {attach.status === "uploading" && (
                            <RefreshCw className="w-3 h-3 animate-spin text-indigo-400" />
                          )}
                          {attach.status === "indexing" && (
                            <Activity className="w-3 h-3 animate-pulse text-amber-400" />
                          )}
                          {attach.status === "ready" && (
                            <Check className="w-3.5 h-3.5 text-emerald-450 font-bold" />
                          )}
                          {attach.status === "failed" && (
                            <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                          )}

                          <div className="flex flex-col">
                            <span className="text-slate-200 font-medium max-w-[150px] truncate">{attach.filename}</span>
                            {attach.size && (
                              <span className="text-[9px] text-slate-500">{formatBytes(attach.size)}</span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                            className="text-slate-400 hover:text-rose-455 font-bold hover:bg-slate-700/40 w-4 h-4 rounded-full flex items-center justify-center transition-all cursor-pointer"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <form onSubmit={handleSendMessage} className="flex space-x-3 items-end">
                    
                    {/* File attach button wrapper */}
                    <label className="flex items-center justify-center p-3 bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-850 rounded-2xl transition-all cursor-pointer active:scale-95">
                      <Paperclip className="w-5 h-5" />
                      <input type="file" onChange={handleAttachFile} className="hidden" />
                    </label>

                    {/* Text Input area */}
                    <div className="flex-1 relative">
                      <textarea
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage(e);
                          }
                        }}
                        rows={1}
                        placeholder={auth ? "Send a prompt to the AI agent..." : "Auth credentials required to prompt"}
                        disabled={!auth || busy}
                        className="w-full bg-slate-950/90 text-slate-100 placeholder-slate-500 rounded-2xl py-3 px-4 pl-4 border border-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:bg-slate-950 transition-all text-sm resize-none"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={busy || (!inputText.trim() && attachments.length === 0)}
                      className="p-3 bg-gradient-to-tr from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-2xl transition-all shadow-md shadow-indigo-500/10 active:scale-95 disabled:opacity-40 disabled:scale-100 flex-shrink-0 cursor-pointer"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </form>

                  {/* Settings / Tool Toggles */}
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-500 pt-1 px-1">
                    <label className="flex items-center space-x-1.5 cursor-pointer hover:text-slate-350">
                      <input
                        type="checkbox"
                        checked={useWebSearch}
                        onChange={(e) => setUseWebSearch(e.target.checked)}
                        className="rounded border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 bg-slate-950 cursor-pointer"
                      />
                      <span>🌐 Web Search</span>
                    </label>
                    <label className="flex items-center space-x-1.5 cursor-pointer hover:text-slate-350">
                      <input
                        type="checkbox"
                        checked={enableBrowserTools}
                        onChange={(e) => setEnableBrowserTools(e.target.checked)}
                        className="rounded border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 bg-slate-950 cursor-pointer"
                      />
                      <span>🤖 Browser Automation</span>
                    </label>
                    <label className="flex items-center space-x-1.5 cursor-pointer hover:text-slate-350">
                      <input
                        type="checkbox"
                        checked={enableTerminalTools}
                        onChange={(e) => setEnableTerminalTools(e.target.checked)}
                        className="rounded border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 bg-slate-950 cursor-pointer"
                      />
                      <span>💻 Bash Shell</span>
                    </label>
                  </div>
                </div>

              </div>

              {/* Rename/Category Category Modal overlay */}
              {categoryModalSessionId && (
                <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50">
                  <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
                    <h3 className="font-bold text-slate-200 text-sm">Update Session Category</h3>
                    <input
                      type="text"
                      placeholder="e.g. Code, Research, Audit"
                      value={categoryValue}
                      onChange={(e) => setCategoryValue(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
                    />
                    <div className="flex space-x-2.5 justify-end">
                      <button
                        onClick={() => setCategoryModalSessionId(null)}
                        className="px-3.5 py-2 rounded-xl bg-slate-800 text-slate-400 hover:text-slate-200 text-xs transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveCategory(categoryModalSessionId, categoryValue)}
                        className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* ==========================================
              COGNITIVE MEMORY PANEL
             ========================================== */}
          {tab === "memory" && auth && (
            <div className="space-y-6 max-w-6xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800/80 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <Brain className="w-6 h-6 text-indigo-400" />
                    <span>Cognitive Memory Core</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Manage semantic database models and curate extracted relational statements.</p>
                </div>
                
                {/* Tabs */}
                <div className="bg-slate-900 p-1 rounded-xl border border-slate-800 flex space-x-1">
                  {(isAdmin() ? ["core", "inbox", "explorer", "analytics"] as const : ["core", "inbox", "analytics"] as const).map(sub => (
                    <button
                      key={sub}
                      onClick={() => {
                        setMemSubTab(sub as any);
                        if (sub === "explorer") {
                          loadVectorMemories();
                        }
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                        memSubTab === sub 
                          ? "bg-indigo-600 text-white shadow-sm" 
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {sub === "core" ? "Core Facts" : sub === "inbox" ? "Inbox Pending" : sub === "explorer" ? "Vector Explorer" : "Analytics"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sub-Tab 1: Core Facts */}
              {memSubTab === "core" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left: Add Fact Form */}
                  <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4 h-fit">
                    <h3 className="font-bold text-slate-200 text-sm">Add New Core Memory</h3>
                    <form onSubmit={handleAddFact} className="space-y-3">
                      <textarea
                        value={newFact}
                        onChange={(e) => setNewFact(e.target.value)}
                        placeholder="Write a clear fact or user preference statement..."
                        rows={4}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                      />
                      <button
                        type="submit"
                        className="w-full py-2 rounded-xl bg-indigo-650 hover:bg-indigo-600 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Insert Fact</span>
                      </button>
                    </form>
                  </div>

                  {/* Import Memory from File */}
                  <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4 h-fit">
                    <h3 className="font-bold text-slate-200 text-sm">Import Memory from File</h3>
                    <p className="text-[11px] text-slate-500">
                      Upload a PDF, TXT, DOCX, or XLSX file to extract facts into memory.
                    </p>
                    
                    <div className="space-y-3">
                      <input
                        type="file"
                        accept=".pdf,.txt,.docx,.xlsx"
                        onChange={handleMemoryFileUpload}
                        className="hidden"
                        id="memory-file-input"
                      />
                      <label
                        htmlFor="memory-file-input"
                        className="w-full py-2.5 rounded-xl border border-dashed border-slate-800 hover:border-indigo-500 bg-slate-950/50 hover:bg-slate-950 text-slate-400 hover:text-slate-200 font-semibold text-xs transition-all flex items-center justify-center space-x-2 cursor-pointer"
                      >
                        <Upload className="w-4 h-4" />
                        <span>Choose Document</span>
                      </label>
                      
                      {memoryFileLoading && (
                        <div className="text-center text-xs text-indigo-400 font-semibold animate-pulse py-2">
                          Extracting and curating facts...
                        </div>
                      )}
                      
                      {curatedFacts.length > 0 && (
                        <div className="space-y-3 pt-3 border-t border-slate-800/80">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">
                            Extracted Facts
                          </span>
                          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                            {curatedFacts.map((fact, idx) => (
                              <div key={idx} className="flex items-start space-x-2 p-2 rounded bg-slate-900/40 border border-slate-850">
                                <input
                                  type="checkbox"
                                  checked={!!selectedFacts[idx]}
                                  onChange={() => handleToggleFactSelection(idx)}
                                  className="mt-0.5 rounded border-slate-800 bg-slate-950 text-indigo-650 focus:ring-indigo-500/50"
                                />
                                <span className="text-xs text-slate-300">{fact}</span>
                              </div>
                            ))}
                          </div>
                          
                          <button
                            type="button"
                            onClick={handleSaveSelectedFacts}
                            className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2 cursor-pointer shadow active:scale-95"
                          >
                            <Check className="w-4 h-4" />
                            <span>Save Selected ({Object.values(selectedFacts).filter(Boolean).length})</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Facts list */}
                  <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                    <h3 className="font-bold text-slate-200 text-sm">Index of Stored Memory Facts ({memories.length})</h3>
                    <div className="space-y-3.5 max-h-[500px] overflow-y-auto pr-1">
                      {memories.map(m => (
                        <div key={m.id} className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-850 flex justify-between items-start space-x-3 group">
                          {editingMemId === m.id ? (
                            <div className="flex-1 space-y-2">
                              <textarea
                                value={editingFactText}
                                onChange={(e) => setEditingFactText(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none"
                              />
                              <div className="flex space-x-2 justify-end">
                                <button onClick={() => setEditingMemId(null)} className="px-2.5 py-1 text-[11px] rounded bg-slate-850 text-slate-400">Cancel</button>
                                <button onClick={() => handleUpdateFactText(m.id)} className="px-2.5 py-1 text-[11px] rounded bg-indigo-600 text-white">Save</button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p className="text-xs text-slate-300 leading-relaxed">{m.fact}</p>
                              <div className="flex space-x-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                <button
                                  onClick={() => {
                                    setEditingMemId(m.id);
                                    setEditingFactText(m.fact);
                                  }}
                                  className="p-1 hover:text-indigo-400 text-slate-500"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteFact(m.id)}
                                  className="p-1 hover:text-rose-400 text-slate-500"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                      {memories.length === 0 && (
                        <div className="p-6 text-center text-xs text-slate-600">No memories indexed yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Sub-Tab 2: Memory Inbox (Pending AI Extractions) */}
              {memSubTab === "inbox" && (
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <h3 className="font-bold text-slate-200 text-sm">Extracted Memory Fact Proposals</h3>
                      <p className="text-xs text-slate-500 mt-0.5">Approve or reject fact statements extracted automatically from agent interactions.</p>
                    </div>
                    
                    {/* Status filter selection */}
                    <div className="flex space-x-2">
                      {["pending", "approved", "rejected"].map(filter => (
                        <button
                          key={filter}
                          onClick={() => setInboxFilter(filter)}
                          className={`px-3 py-1 rounded-xl text-xs font-semibold capitalize transition-all border ${
                            inboxFilter === filter 
                              ? "bg-slate-900 text-indigo-400 border-indigo-500/20" 
                              : "bg-slate-950 text-slate-500 border-slate-900"
                          }`}
                        >
                          {filter}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
                    {memoryInbox.map(item => (
                      <div key={item.id} className="p-4 rounded-xl bg-slate-900/35 border border-slate-850 space-y-3">
                        <p className="text-xs text-slate-300 italic">" {item.candidate_text} "</p>
                        
                        <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800/60 pt-2.5">
                          <div className="flex items-center space-x-4">
                            <span>Confidence: <strong className="text-indigo-400">{Math.round(item.confidence * 100)}%</strong></span>
                            <span>Created: {new Date(item.created_at).toLocaleString()}</span>
                          </div>
                          
                          {item.status === "pending" && (
                            <div className="flex space-x-2">
                              <button
                                onClick={() => handleInboxAction(item.id, "rejected")}
                                className="px-2.5 py-1 rounded bg-rose-950/45 text-rose-400 border border-rose-500/20 text-xs cursor-pointer"
                              >
                                Reject
                              </button>
                              <button
                                onClick={() => handleInboxAction(item.id, "approved", item.candidate_text)}
                                className="px-2.5 py-1 rounded bg-emerald-950/45 text-emerald-450 border border-emerald-500/20 text-xs cursor-pointer"
                              >
                                Approve Fact
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {memoryInbox.length === 0 && (
                      <div className="p-8 text-center text-xs text-slate-600">No inbox candidates found matching filter.</div>
                    )}
                  </div>
                </div>
              )}

              {/* Sub-Tab: Explorer (Admin Vector Memory Explorer) */}
              {memSubTab === "explorer" && isAdmin() && (
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-6">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
                    <div>
                      <h3 className="font-bold text-slate-200 text-sm">Vector Database Explorer</h3>
                      <p className="text-xs text-slate-500 mt-0.5">Direct raw semantic vectors inside the 'chat_memory' collection.</p>
                    </div>
                    
                    <div className="flex flex-col sm:flex-row gap-3">
                      <input
                        type="text"
                        value={vectorSearch}
                        onChange={(e) => setVectorSearch(e.target.value)}
                        placeholder="Filter by fact contents..."
                        className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                      />
                      <button
                        onClick={loadVectorMemories}
                        className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold transition-colors flex items-center justify-center space-x-1"
                      >
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left: Add Vector Fact Form */}
                    <div className="glass-panel p-4 rounded-xl border border-slate-800/60 bg-slate-900/10 space-y-4 h-fit">
                      <h4 className="font-bold text-slate-200 text-xs">Create Vector Entry</h4>
                      <form onSubmit={handleAddVectorMemory} className="space-y-3">
                        <textarea
                          value={newVectorDoc}
                          onChange={(e) => setNewVectorDoc(e.target.value)}
                          placeholder="Type vector database statement document here..."
                          rows={4}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                        <button
                          type="submit"
                          className="w-full py-2 rounded-xl bg-indigo-650 hover:bg-indigo-600 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2 shadow active:scale-95"
                        >
                          <Plus className="w-4 h-4" />
                          <span>Add Vector Record</span>
                        </button>
                      </form>
                    </div>

                    {/* Right: Vectors list */}
                    <div className="lg:col-span-2 space-y-4">
                      {vectorLoading ? (
                        <div className="p-8 text-center text-xs text-indigo-400 font-semibold animate-pulse">
                          Fetching vector embeddings...
                        </div>
                      ) : (
                        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                          {vectorMemories
                            .filter(m => !vectorSearch || (m.document && m.document.toLowerCase().includes(vectorSearch.toLowerCase())))
                            .map(m => (
                              <div key={m.id} className="p-4 rounded-xl bg-slate-900/40 border border-slate-850 space-y-3 group transition-colors hover:border-slate-800">
                                {editingVectorId === m.id ? (
                                  <div className="space-y-2">
                                    <textarea
                                      value={editingVectorText}
                                      onChange={(e) => setEditingVectorText(e.target.value)}
                                      className="w-full bg-slate-950 border border-slate-850 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                                      rows={3}
                                    />
                                    <div className="flex space-x-2 justify-end">
                                      <button
                                        onClick={() => setEditingVectorId(null)}
                                        className="px-3 py-1.5 text-xs rounded-xl bg-slate-850 text-slate-400 font-semibold"
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        onClick={() => handleUpdateVectorMemory(m.id)}
                                        className="px-3 py-1.5 text-xs rounded-xl bg-indigo-600 text-white font-semibold"
                                      >
                                        Update Vector
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="flex justify-between items-start space-x-3">
                                    <div className="space-y-1.5 flex-1">
                                      <p className="text-xs text-slate-300 leading-relaxed font-mono select-all break-all">{m.document}</p>
                                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500 font-semibold">
                                        <span className="text-[10px] text-indigo-400">ID: {m.id}</span>
                                        {m.collection_name && <span>Collection: <strong className="text-slate-400">{m.collection_name}</strong></span>}
                                      </div>
                                    </div>
                                    <div className="flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                      <button
                                        onClick={() => {
                                          setEditingVectorId(m.id);
                                          setEditingVectorText(m.document);
                                        }}
                                        className="p-1.5 hover:text-indigo-400 text-slate-500 transition-colors"
                                        title="Edit fact text & regenerate embedding"
                                      >
                                        <Edit2 className="w-3.5 h-3.5" />
                                      </button>
                                      <button
                                        onClick={() => handleDeleteVectorMemory(m.id)}
                                        className="p-1.5 hover:text-rose-400 text-slate-500 transition-colors"
                                        title="Delete from vector db"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          {vectorMemories.length === 0 && (
                            <div className="p-8 text-center text-xs text-slate-600">No vector embeddings found.</div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Sub-Tab 3: Analytics */}
              {memSubTab === "analytics" && (
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">Vector Core Memory Growth Metrics</h3>
                  <div className="h-72 flex items-center justify-center text-slate-500">
                    {/* Visual graph mockup showing fact retention counts */}
                    <div className="w-full text-center space-y-2">
                      <p className="text-xs">Database memory consolidation logs show high alignment density.</p>
                      <div className="flex justify-center items-end space-x-2 h-32 pt-4">
                        <div className="w-8 bg-indigo-500/30 rounded-t h-[20%]"></div>
                        <div className="w-8 bg-indigo-500/40 rounded-t h-[40%]"></div>
                        <div className="w-8 bg-indigo-500/50 rounded-t h-[55%]"></div>
                        <div className="w-8 bg-indigo-500/60 rounded-t h-[75%]"></div>
                        <div className="w-8 bg-indigo-500 rounded-t h-[95%]"></div>
                      </div>
                      <div className="text-[10px] text-slate-600">Cognitive records saved over consecutive build iterations</div>
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* ==========================================
              TASK BOARD PANEL
             ========================================== */}
          {tab === "tasks" && auth && (
            <div className="space-y-6 max-w-6xl mx-auto">
              
              {/* Header section with new task trigger */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/40 p-5 rounded-2xl border border-slate-800/60">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <ClipboardList className="w-6 h-6 text-indigo-400" />
                    <span>Agent Workspace Task Board</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Break down agent directives into trackable Todo tasks and organize statuses.</p>
                </div>
                
                {/* Filters */}
                <div className="flex space-x-2 w-full sm:w-auto">
                  <input
                    type="text"
                    placeholder="Search tasks..."
                    value={taskSearch}
                    onChange={(e) => setTaskSearch(e.target.value)}
                    className="bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-xl text-xs text-slate-200 w-full sm:w-40 focus:outline-none"
                  />
                  <select
                    value={taskPriorityFilter}
                    onChange={(e) => setTaskPriorityFilter(e.target.value)}
                    className="bg-slate-950 border border-slate-800 px-2.5 py-1.5 rounded-xl text-xs text-slate-300 focus:outline-none"
                  >
                    <option value="">All Priorities</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>

              {/* Grid 1: Create Task and Kanban Columns */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                
                {/* Create Task Panel */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 h-fit space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">Add New Project Task</h3>
                  
                  <form onSubmit={handleCreateTask} className="space-y-3.5">
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Task Title</label>
                      <input
                        type="text"
                        required
                        value={newTaskTitle}
                        onChange={(e) => setNewTaskTitle(e.target.value)}
                        placeholder="Write task title..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Description</label>
                      <textarea
                        value={newTaskDesc}
                        onChange={(e) => setNewTaskDesc(e.target.value)}
                        placeholder="Task context details..."
                        rows={3}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Priority</label>
                        <select
                          value={newTaskPriority}
                          onChange={(e) => setNewTaskPriority(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-2 text-xs text-slate-300 focus:outline-none"
                        >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                          <option value="urgent">Urgent</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Due Date</label>
                        <input
                          type="date"
                          value={newTaskDue}
                          onChange={(e) => setNewTaskDue(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2 py-2 text-xs text-slate-350 focus:outline-none"
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center justify-center space-x-1.5 cursor-pointer shadow-md shadow-indigo-500/10 active:scale-95 transition-all"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Add to Todo</span>
                    </button>
                  </form>
                </div>

                {/* Kanban columns (Todo, In Progress, Done) */}
                <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(["todo", "in_progress", "done"] as const).map(col => {
                    const colTasks = filteredTasks.filter(t => t.status === col);
                    return (
                      <div key={col} className="glass-panel p-4 rounded-2xl border border-slate-850 flex flex-col space-y-3 min-h-[400px]">
                        
                        {/* Header badge */}
                        <div className="flex justify-between items-center border-b border-slate-800/80 pb-2">
                          <span className="font-bold text-xs uppercase tracking-wider text-slate-400 capitalize">
                            {col.replace("_", " ")}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-950 text-slate-500 font-bold border border-slate-850">
                            {colTasks.length}
                          </span>
                        </div>

                        {/* List items */}
                        <div className="flex-1 overflow-y-auto space-y-2.5 pr-0.5">
                          {colTasks.map(task => (
                            <div key={task.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-850 space-y-3 shadow shadow-slate-955 relative group">
                              
                              <div className="space-y-1">
                                <span className="text-xs font-bold text-slate-200 block leading-snug">{task.title}</span>
                                {task.description && (
                                  <p className="text-[11px] text-slate-400 leading-normal">{task.description}</p>
                                )}
                              </div>

                              <div className="flex justify-between items-center text-[10px]">
                                <span className={`px-2 py-0.5 rounded font-semibold border ${
                                  task.priority === "urgent" 
                                    ? "bg-rose-950/70 text-rose-350 border-rose-500/30" 
                                    : task.priority === "high" 
                                      ? "bg-orange-950/70 text-orange-350 border-orange-500/30" 
                                      : task.priority === "medium" 
                                        ? "bg-indigo-950/70 text-indigo-350 border-indigo-500/30" 
                                        : "bg-slate-900 text-slate-400 border-slate-800"
                                }`}>
                                  {task.priority}
                                </span>
                                {task.due_at && (
                                  <span className="text-slate-500">Due: {new Date(task.due_at).toLocaleDateString()}</span>
                                )}
                              </div>

                              {/* Task Action Buttons */}
                              <div className="flex justify-between items-center border-t border-slate-850 pt-2.5 mt-1">
                                <button
                                  onClick={() => handleDeleteTask(task.id)}
                                  className="text-slate-500 hover:text-rose-400 p-1 hover:bg-slate-900 rounded transition-all"
                                  title="Delete task"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                                
                                <div className="flex space-x-1">
                                  {col !== "todo" && (
                                    <button
                                      onClick={() => handleUpdateTaskStatus(task.id, col === "done" ? "in_progress" : "todo")}
                                      className="px-2 py-0.5 bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded text-[9px] border border-slate-800"
                                    >
                                      ← Back
                                    </button>
                                  )}
                                  {col !== "done" && (
                                    <button
                                      onClick={() => handleUpdateTaskStatus(task.id, col === "todo" ? "in_progress" : "done")}
                                      className="px-2 py-0.5 bg-indigo-650 hover:bg-indigo-600 text-white rounded text-[9px]"
                                    >
                                      Next →
                                    </button>
                                  )}
                                </div>
                              </div>

                            </div>
                          ))}
                          {colTasks.length === 0 && (
                            <div className="h-full flex items-center justify-center p-6 text-center text-[10px] text-slate-600 border border-dashed border-slate-850 rounded-xl">
                              No tasks in this column.
                            </div>
                          )}
                        </div>

                      </div>
                    );
                  })}
                </div>

              </div>

            </div>
          )}

          {/* ==========================================
              WEB AUTOMATION PANEL
             ========================================== */}
          {tab === "browser" && auth && (
            <div className="space-y-6 max-w-6xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800/80 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <Globe className="w-6 h-6 text-indigo-400" />
                    <span>Headless Web Automation Panel</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Monitor autonomous browser jobs, screenshots and validation checkpoints.</p>
                </div>
                
                <span className="text-xs px-2.5 py-1 rounded bg-emerald-950/80 border border-emerald-500/20 text-emerald-400 font-semibold flex items-center space-x-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping mr-1"></span>
                  <span>Playwright Browser Node Connected</span>
                </span>
              </div>

              {/* Alert pending confirmation warnings */}
              {browserConfirmation && (
                <div className="p-5 bg-amber-950/40 border border-amber-500/30 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                  <div className="space-y-1">
                    <span className="font-bold text-amber-300 flex items-center space-x-1.5 text-sm">
                      <ShieldAlert className="w-4 h-4" />
                      <span>Security: Browser Action Awaiting Confirmation</span>
                    </span>
                    <p className="text-xs text-slate-350 leading-relaxed">
                      Agent browser wants to execute a command on: <strong className="text-white">{browserConfirmation.url || "External domain"}</strong>. Description: {browserConfirmation.description}
                    </p>
                  </div>
                  <div className="flex space-x-2 flex-shrink-0">
                    <button
                      onClick={async () => {
                        await apiCall("/api/browser/confirm", { method: "POST", body: JSON.stringify({ action: "decline" }) });
                        setBrowserConfirmation(null);
                        triggerToast("Browser action declined", "info");
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 text-xs font-semibold cursor-pointer"
                    >
                      Decline
                    </button>
                    <button
                      onClick={async () => {
                        await apiCall("/api/browser/confirm", { method: "POST", body: JSON.stringify({ action: "approve" }) });
                        setBrowserConfirmation(null);
                        triggerToast("Browser action approved", "ok");
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-indigo-650 hover:bg-indigo-600 text-white text-xs font-semibold cursor-pointer"
                    >
                      Approve Action
                    </button>
                  </div>
                </div>
              )}

              {/* Grid block */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Allowlist management (Admin only) */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 h-fit space-y-4">
                  <div className="space-y-1">
                    <h3 className="font-bold text-slate-200 text-sm">Domain Access Allowlist</h3>
                    <p className="text-[11px] text-slate-500">Domains the agent is permitted to navigate without requiring manual approvals.</p>
                  </div>

                  <form onSubmit={handleAddAllowlistDomain} className="flex space-x-2">
                    <input
                      type="text"
                      required
                      value={newAllowlistDomain}
                      onChange={(e) => setNewAllowlistDomain(e.target.value)}
                      placeholder="e.g. github.com"
                      className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none"
                    />
                    <button
                      type="submit"
                      className="px-3 py-1.5 bg-indigo-650 hover:bg-indigo-650 text-white rounded-xl text-xs font-semibold cursor-pointer"
                    >
                      Add
                    </button>
                  </form>

                  <div className="border-t border-slate-800/80 pt-3.5 space-y-2">
                    <span className="text-xs text-slate-400 font-semibold block mb-1">Approved Host Domains</span>
                    <div className="flex flex-wrap gap-1.5">
                      {allowlist.map(domain => (
                        <span key={domain} className="px-2 py-0.5 rounded bg-slate-900 border border-slate-850 text-slate-350 text-[10px] flex items-center">
                          {domain}
                        </span>
                      ))}
                      {allowlist.length === 0 && (
                        <span className="text-[10px] text-slate-600">Allowlist empty. Manual confirmations active for all hosts.</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Automation Jobs index list */}
                <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">Active Browser Job Outputs</h3>
                  <div className="space-y-3.5 max-h-[500px] overflow-y-auto pr-1">
                    {browserJobs.map(job => (
                      <div key={job.id} className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-850 flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2.5">
                            <span className="font-bold text-xs text-slate-200">Job #{job.id}</span>
                            <span className="text-[10px] text-slate-500">{new Date(job.created_at).toLocaleString()}</span>
                          </div>
                          <p className="text-xs text-slate-350">Action: <span className="text-indigo-400 font-medium">{job.job_type}</span></p>
                          {job.request && (
                            <p className="text-[10px] text-slate-500 font-mono truncate max-w-[320px]">URL: {String(job.request.url || "")}</p>
                          )}
                        </div>

                        <div className="flex items-center space-x-3 flex-shrink-0">
                          <span className={`text-[10px] px-2 py-0.5 rounded font-semibold border ${
                            job.status === "completed" 
                              ? "bg-emerald-950/70 text-emerald-400 border-emerald-500/25" 
                              : job.status === "failed" 
                                ? "bg-rose-950/70 text-rose-450 border-rose-500/25" 
                                : "bg-slate-900 text-slate-400 border-slate-800"
                          }`}>
                            {job.status}
                          </span>
                          
                          {/* Screenshot button */}
                          {typeof job.result?.screenshot === "string" && (
                            <button
                              onClick={() => setSelectedJobScreenshot(String(job.result?.screenshot))}
                              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-[10px] font-semibold transition-all border border-slate-700/60 cursor-pointer"
                            >
                              View Page Capture
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    {browserJobs.length === 0 && (
                      <div className="p-8 text-center text-xs text-slate-600">No browser automation logs generated yet.</div>
                    )}
                  </div>
                </div>

              </div>

              {/* View screenshot modal */}
              {selectedJobScreenshot && (
                <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setSelectedJobScreenshot(null)}>
                  <div className="bg-slate-900 border border-slate-800 rounded-3xl p-4 w-full max-w-4xl max-h-[85vh] flex flex-col space-y-3 shadow-2xl relative" onClick={e => e.stopPropagation()}>
                    <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                      <span className="font-bold text-xs text-slate-300">Browser Page Capture Screenshot</span>
                      <button onClick={() => setSelectedJobScreenshot(null)} className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                    <div className="flex-1 overflow-auto bg-slate-950 rounded-xl flex items-center justify-center border border-slate-850">
                      <img src={selectedJobScreenshot.startsWith("data:") ? selectedJobScreenshot : `data:image/png;base64,${selectedJobScreenshot}`} alt="Page screenshot capture" className="max-w-full h-auto object-contain" />
                    </div>
                  </div>
                </div>
              )}

              {/* Global Search Modal overlay */}
              {showSearchModal && (
                <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowSearchModal(false)}>
                  <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col space-y-4 shadow-2xl relative" onClick={e => e.stopPropagation()}>
                    <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                      <h3 className="font-bold text-slate-200 text-sm flex items-center space-x-2">
                        <Search className="w-4 h-4 text-indigo-400" />
                        <span>Global Chat Log Search</span>
                      </h3>
                      <button onClick={() => setShowSearchModal(false)} className="p-1 text-slate-400 hover:text-white hover:bg-slate-805 rounded-lg transition-colors">
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <form onSubmit={handleGlobalSearch} className="flex space-x-2">
                      <input
                        type="text"
                        placeholder="Enter search keywords..."
                        value={globalSearchQuery}
                        onChange={(e) => setGlobalSearchQuery(e.target.value)}
                        className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
                        autoFocus
                      />
                      <button
                        type="submit"
                        disabled={globalSearchLoading}
                        className="px-4 py-2 rounded-xl bg-indigo-650 hover:bg-indigo-600 text-white font-semibold text-xs transition-all flex items-center space-x-1 shadow active:scale-95 disabled:opacity-50"
                      >
                        {globalSearchLoading ? "Searching..." : "Search"}
                      </button>
                    </form>

                    <div className="flex-1 overflow-y-auto pr-1 space-y-3 min-h-[200px]">
                      {globalSearchLoading ? (
                        <div className="p-12 text-center text-xs text-indigo-400 font-semibold animate-pulse">
                          Searching across history...
                        </div>
                      ) : globalSearchHits.length > 0 ? (
                        globalSearchHits.map((hit, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              if (hit.session_id) {
                                handleSelectSession(hit.session_id);
                                setShowSearchModal(false);
                              }
                            }}
                            className="p-3.5 rounded-xl bg-slate-950/45 border border-slate-850 hover:border-indigo-500/40 hover:bg-slate-950 transition-all cursor-pointer group text-left"
                          >
                            <div className="flex justify-between items-center text-[10px] text-slate-500 mb-1.5 font-semibold">
                              <span className="text-indigo-400 group-hover:text-indigo-350 transition-colors">Session: {hit.session_title || "Untitled Conversation"}</span>
                              {hit.created_at && <span>{new Date(hit.created_at).toLocaleString()}</span>}
                            </div>
                            <p className="text-xs text-slate-350 leading-relaxed font-sans" dangerouslySetInnerHTML={{ __html: hit.highlight || hit.text }} />
                          </div>
                        ))
                      ) : globalSearchQuery ? (
                        <div className="p-12 text-center text-xs text-slate-600">No matching keyword occurrences found.</div>
                      ) : (
                        <div className="p-12 text-center text-xs text-slate-500 italic">Type a keyword search term above to scan all historical chat session messages.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* ==========================================
              SHELL TERMINAL COMMAND LOG
             ========================================== */}
          {tab === "terminal" && auth && (
            <div className="space-y-6 max-w-6xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800/80 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <Terminal className="w-6 h-6 text-indigo-400" />
                    <span>Core Shell Terminal Command Console</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Instruct or review command lines executed inside containerized subprocess environments.</p>
                </div>
                
                <span className="text-xs px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400 font-semibold flex items-center">
                  <Activity className="w-4 h-4 text-indigo-400 mr-1 animate-pulse" />
                  <span>Sandbox Environment Active</span>
                </span>
              </div>

              {/* Alert terminal execution confirmation request */}
              {terminalConfirmation && (
                <div className="p-5 bg-amber-950/40 border border-amber-500/30 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                  <div className="space-y-1">
                    <span className="font-bold text-amber-300 flex items-center space-x-1.5 text-sm">
                      <ShieldAlert className="w-4 h-4" />
                      <span>Security Check: Shell Execution Confirmation</span>
                    </span>
                    <p className="text-xs text-slate-350 font-mono">
                      $ {terminalConfirmation.command}
                    </p>
                    <p className="text-[10px] text-slate-400">Directory: {terminalConfirmation.working_directory || "App root"}</p>
                  </div>
                  <div className="flex space-x-2 flex-shrink-0">
                    <button
                      onClick={async () => {
                        await apiCall("/api/terminal/confirm", { method: "POST", body: JSON.stringify({ action: "decline" }) });
                        setTerminalConfirmation(null);
                        triggerToast("Command execution declined", "info");
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 text-xs font-semibold cursor-pointer"
                    >
                      Decline
                    </button>
                    <button
                      onClick={async () => {
                        await apiCall("/api/terminal/confirm", { method: "POST", body: JSON.stringify({ action: "approve" }) });
                        setTerminalConfirmation(null);
                        triggerToast("Command execution approved", "ok");
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-indigo-650 hover:bg-indigo-600 text-white text-xs font-semibold cursor-pointer"
                    >
                      Approve command
                    </button>
                  </div>
                </div>
              )}

              {/* Grid block */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Execute Console Form */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex flex-col h-fit space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">Command line Executor</h3>
                  
                  <form onSubmit={handleTerminalSubmit} className="space-y-3">
                    <input
                      type="text"
                      required
                      value={terminalCommand}
                      onChange={(e) => setTerminalCommand(e.target.value)}
                      placeholder="e.g. whoami or git status"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    />
                    <button
                      type="submit"
                      disabled={busy}
                      className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow cursor-pointer active:scale-95 transition-all"
                    >
                      <Play className="w-4 h-4" />
                      <span>Run Shell Command</span>
                    </button>
                  </form>

                  {/* Output screen */}
                  {terminalOutput && (
                    <div className="space-y-1.5 pt-2">
                      <span className="text-[10px] text-slate-500 font-semibold block uppercase">Console Output Screen</span>
                      <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-850 text-[10px] text-slate-350 font-mono max-h-56 overflow-auto whitespace-pre-wrap leading-relaxed">
                        {terminalOutput}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Command Logs History List */}
                <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">Subprocess Shell Logs</h3>
                  <div className="space-y-3.5 max-h-[500px] overflow-y-auto pr-1">
                    {terminalLogs.map(log => (
                      <div key={log.id} className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-850 flex flex-col space-y-2">
                        <div className="flex justify-between items-start">
                          <div className="flex items-center space-x-2 text-[10px]">
                            <span className="font-mono text-indigo-400 font-bold block">$ {log.command}</span>
                            <span className="text-slate-500">[{new Date(log.created_at).toLocaleString()}]</span>
                          </div>
                          
                          <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold border ${
                            log.blocked 
                              ? "bg-rose-950/70 text-rose-400 border-rose-500/25" 
                              : log.exit_code === 0 
                                ? "bg-emerald-950/70 text-emerald-450 border-emerald-500/25" 
                                : "bg-orange-950/70 text-orange-400 border-orange-500/25"
                          }`}>
                            {log.blocked ? "Blocked" : `Exit: ${log.exit_code}`}
                          </span>
                        </div>
                        
                        {log.output_summary && (
                          <pre className="p-2 bg-slate-950/80 rounded border border-slate-900 text-[9px] text-slate-450 font-mono overflow-x-auto truncate max-w-full">
                            {log.output_summary}
                          </pre>
                        )}
                      </div>
                    ))}
                    {terminalLogs.length === 0 && (
                      <div className="p-8 text-center text-xs text-slate-600">No command subprocess shell log history found.</div>
                    )}
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* ==========================================
              AI PERSONAS & MODELS SETTINGS PANEL
             ========================================== */}
          {tab === "ai" && auth && (
            <div className="space-y-6 max-w-6xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <Sliders className="w-6 h-6 text-indigo-400" />
                    <span>AI Model & Agent Personas Setup</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Configure default models, tags, and system assistant persona overrides.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Personas Form / Details */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 h-fit space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">System Personas ({personas.length})</h3>
                  
                  <div className="space-y-3.5 max-h-[400px] overflow-y-auto pr-1">
                    {personas.map((p: Persona) => (
                      <div key={p.id} className="p-3 rounded-xl bg-slate-900/40 border border-slate-855 space-y-2">
                        <div className="flex justify-between items-start">
                          <span className="font-bold text-xs text-slate-200 block">{p.name}</span>
                          {p.is_default && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 font-bold">Default</span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-455 font-mono truncate">{p.system_prompt}</p>
                        <div className="flex flex-wrap gap-1">
                          {p.tags?.map((t: string) => (
                            <span key={t} className="px-1.5 py-0.2 rounded bg-slate-950 text-slate-500 text-[8px] font-semibold">{t}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Model Lists per Provider */}
                <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800 space-y-5">
                  <h3 className="font-bold text-slate-200 text-sm">Dynamic Model Provider Configuration Lists</h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {providers.map(prov => {
                      const modelsList = providerModels[prov.value] || [];
                      return (
                        <div key={prov.value} className="p-4 rounded-xl bg-slate-900/35 border border-slate-850 space-y-3">
                          <span className="font-bold text-xs text-slate-200 block border-b border-slate-800 pb-1.5">{prov.label}</span>
                          
                          <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
                            {modelsList.map(m => (
                              <div key={m.id} className="flex justify-between items-center text-xs py-1 border-b border-slate-900/60">
                                <span className="text-slate-350 truncate font-mono max-w-[200px]">{m.name}</span>
                                {m.free && <span className="text-[9px] text-indigo-400 font-semibold uppercase">Free</span>}
                              </div>
                            ))}
                            {modelsList.length === 0 && (
                              <span className="text-[10px] text-slate-650 italic block pt-2">No models found or config missing.</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* ==========================================
              SYSTEM SETTINGS CONFIG PANEL
             ========================================== */}
          {tab === "settings" && auth && isAdmin() && (
            <div className="space-y-6 max-w-4xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <Shield className="w-6 h-6 text-indigo-400" />
                    <span>System Credentials Configuration</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Configure default provider keys, parameters and system encryption constants.</p>
                </div>
              </div>

              <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-5">
                <h3 className="font-bold text-slate-200 text-sm">Active Provider Keys & Settings</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { key: "default_model_provider", label: "Default Model Provider", placeholder: "e.g. ollama, openrouter, openai" },
                    { key: "default_model", label: "Default Model Name", placeholder: "e.g. google/gemma-4-31b-it:free" },
                    { key: "openai_api_key", label: "OpenAI API Key", placeholder: "sk-proj-..." },
                    { key: "gemini_api_key", label: "Gemini API Key", placeholder: "AIzaSy..." },
                    { key: "anthropic_api_key", label: "Anthropic API Key", placeholder: "sk-ant-..." },
                    { key: "openrouter_api_key", label: "OpenRouter API Key", placeholder: "sk-or-v1-..." },
                    { key: "generic_base_url", label: "Generic LLM Base URL", placeholder: "http://127.0.0.1:1234/v1" },
                    { key: "generic_api_key", label: "Generic LLM API Key", placeholder: "Bearer token" },
                    { key: "ollama_base_url", label: "Ollama Local Base URL", placeholder: "http://host.docker.internal:11434" }
                  ].map(field => (
                    <div key={field.key} className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-400 uppercase">{field.label}</label>
                      <input
                        type={field.key.includes("api_key") || field.key.includes("password") ? "password" : "text"}
                        value={configs[field.key] || ""}
                        onChange={(e) => setConfigs(prev => ({ ...prev, [field.key]: e.target.value }))}
                        placeholder={field.placeholder}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none"
                      />
                    </div>
                  ))}
                </div>

                <div className="flex justify-end pt-2 border-t border-slate-800/80">
                  <button
                    onClick={async () => {
                      try {
                        await apiCall("/api/admin/configs", {
                          method: "POST",
                          body: JSON.stringify({ configs })
                        });
                        triggerToast("Credentials saved successfully", "ok");
                      } catch (err: any) {
                        triggerToast(err.message || "Failed to save config", "err");
                      }
                    }}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow cursor-pointer active:scale-95 transition-all"
                  >
                    Save Configuration
                  </button>
                </div>
              </div>

            </div>
          )}

          {/* ==========================================
              ADMIN PANEL VIEW
             ========================================== */}
          {tab === "admin" && auth && isAdmin() && (
            <div className="space-y-6 max-w-5xl mx-auto">
              
              <div className="flex justify-between items-center border-b border-slate-800 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-200 flex items-center space-x-2">
                    <User className="w-6 h-6 text-indigo-400" />
                    <span>Administrative Management Console</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Manage user database partitions, backup operations, and update log files.</p>
                </div>
              </div>

              <div className="flex border-b border-slate-850 space-x-2 mb-2">
                <button
                  onClick={() => setAdminSubTab("console")}
                  className={`px-4 py-2 text-xs font-bold border-b-2 transition-all ${
                    adminSubTab === "console"
                      ? "border-indigo-500 text-indigo-455"
                      : "border-transparent text-slate-400 hover:text-slate-200"
                  }`}
                >
                  📊 General Console
                </button>
                <button
                  onClick={() => setAdminSubTab("backup")}
                  className={`px-4 py-2 text-xs font-bold border-b-2 transition-all ${
                    adminSubTab === "backup"
                      ? "border-indigo-500 text-indigo-455"
                      : "border-transparent text-slate-400 hover:text-slate-200"
                  }`}
                >
                  💾 Backup & Recovery
                </button>
              </div>

              {adminSubTab === "console" && (
                <>
                  {/* Grid 1: Users, Backups and Updates */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Users List & Accounts creation */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <h3 className="font-bold text-slate-200 text-sm">System Database Users</h3>
                  
                  <div className="space-y-3.5 max-h-[300px] overflow-y-auto pr-1">
                    {adminUsers.map(user => (
                      <div key={user.username} className="p-3 rounded-xl bg-slate-900/40 border border-slate-850 flex justify-between items-center text-xs">
                        <span className="font-semibold text-slate-200">{user.username}</span>
                        <span className="px-2 py-0.5 rounded bg-slate-950 text-slate-500 font-bold uppercase tracking-wider">{user.role}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Database Backups manager */}
                <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="font-bold text-slate-200 text-sm">System Restore Backups</h3>
                    <button
                      onClick={async () => {
                        try {
                          await apiCall("/api/admin/fullbackup/create", { method: "POST" });
                          const res = await apiCall<any>("/api/admin/fullbackup/list");
                          setBackups(res.backups || []);
                          triggerToast("Backup created successfully", "ok");
                        } catch (err: any) {
                          triggerToast(err.message || "Failed to create backup", "err");
                        }
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold cursor-pointer active:scale-95 transition-all"
                    >
                      Trigger Backup
                    </button>
                  </div>
                  
                  <div className="space-y-3.5 max-h-[300px] overflow-y-auto pr-1">
                    {backups.map(b => (
                      <div key={b.filename} className="p-3 rounded-xl bg-slate-900/40 border border-slate-850 flex justify-between items-center text-xs">
                        <div className="flex flex-col">
                          <span className="font-semibold text-slate-350 truncate max-w-[200px]">{b.filename}</span>
                          <span className="text-[10px] text-slate-500 mt-0.5">Size: {Math.round(b.size_bytes / 1024)} KB</span>
                        </div>
                        
                        <button
                          onClick={async () => {
                            if (!confirm("Confirm system restore from this file? Current changes will be overwritten!")) return;
                            try {
                              await apiCall("/api/admin/fullbackup/restore", {
                                method: "POST",
                                body: JSON.stringify({ filename: b.filename })
                              });
                              triggerToast("Backup restored successfully. Please refresh the page.", "ok");
                            } catch (err: any) {
                              triggerToast(err.message || "Failed to restore backup", "err");
                            }
                          }}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-rose-950/20 text-slate-300 hover:text-rose-400 rounded-lg text-[10px] border border-slate-700/60 hover:border-rose-500/20 transition-all cursor-pointer"
                        >
                          Restore
                        </button>
                      </div>
                    ))}
                    {backups.length === 0 && (
                      <div className="p-6 text-center text-xs text-slate-600">No backup records found.</div>
                    )}
                  </div>
                </div>

              </div>

              {/* One-Click System Update Panel */}
              <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-5">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center space-x-2">
                    <RefreshCw className={`w-5 h-5 text-indigo-400 ${updateStatus?.state === "running" ? "animate-spin" : ""}`} />
                    <h3 className="font-bold text-slate-200 text-sm">System Container Updates</h3>
                  </div>
                  {updateStatus && (
                    <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                      isReconnecting ? "bg-amber-950/40 text-amber-400 border border-amber-500/20 animate-pulse" :
                      updateStatus.state === "running" ? "bg-indigo-950/40 text-indigo-400 border border-indigo-500/20 animate-pulse" :
                      updateStatus.state === "success" ? "bg-emerald-950/40 text-emerald-400 border border-emerald-500/20" :
                      updateStatus.state === "error" ? "bg-rose-950/40 text-rose-400 border border-rose-500/20" :
                      "bg-slate-950 text-slate-500 border border-slate-800"
                    }`}>
                      {isReconnecting ? "Reconnecting..." : updateStatus.state}
                    </span>
                  )}
                </div>

                <div className="p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/10 flex items-start space-x-3 text-xs text-amber-300/95">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" />
                  <div>
                    <span className="font-bold">Important Notice:</span> Rebuilding containers pulls the latest source code from GitHub and recreates the Docker services on the host. The application will go offline for 10-20 seconds during this process, and reconnect automatically when finished.
                  </div>
                </div>

                {isReconnecting && (
                  <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/20 flex items-center space-x-3 text-xs text-indigo-300">
                    <WifiOff className="w-5 h-5 animate-pulse text-indigo-400" />
                    <div className="flex-1 font-semibold">
                      Containers recreating on host. Waiting for the FastAPI service to boot back up...
                    </div>
                    <div className="flex items-center space-x-1">
                      <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-ping" />
                      <span className="text-[10px] text-indigo-400">polling...</span>
                    </div>
                  </div>
                )}

                <div className="flex justify-between items-center bg-slate-900/30 p-3 rounded-xl border border-slate-850">
                  <div className="text-xs text-slate-400">
                    Current branch: <span className="font-semibold text-slate-350">main</span>
                  </div>
                  <button
                    disabled={isTriggeringUpdate || updateStatus?.state === "running" || isReconnecting}
                    onClick={triggerSystemUpdate}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all active:scale-95 flex items-center space-x-1.5 cursor-pointer ${
                      isTriggeringUpdate || updateStatus?.state === "running" || isReconnecting
                        ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                        : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/10 hover:shadow-indigo-500/20 border border-indigo-500"
                    }`}
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>{isTriggeringUpdate ? "Starting..." : "Trigger System Rebuild & Update"}</span>
                  </button>
                </div>

                {updateLogs.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-xs text-slate-400 font-semibold px-1">
                      <span>Console Build Output Logs</span>
                      <span className="text-[10px] text-slate-500">{updateLogs.length} lines</span>
                    </div>
                    <div className="h-44 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-850 font-mono text-[11px] text-slate-400 space-y-1.5 scrollbar-thin">
                      {updateLogs.map((line, idx) => {
                        let lineClass = "text-slate-400";
                        if (line.includes("ERROR") || line.includes("failed")) lineClass = "text-rose-400 font-semibold";
                        if (line.includes("SUCCESS") || line.includes("successful")) lineClass = "text-emerald-400 font-semibold";
                        if (line.includes("---")) lineClass = "text-indigo-400 font-semibold mt-2 border-t border-slate-900 pt-1";
                        return (
                          <div key={idx} className={lineClass}>
                            {line}
                          </div>
                        );
                      })}
                      <div ref={updateLogsEndRef} />
                    </div>
                  </div>
                )}
              </div>
              
              </>
              )}

              {adminSubTab === "backup" && (
                <div className="space-y-6">
                  {/* Generate Backup Panel */}
                  <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                    <h3 className="font-bold text-slate-200 text-sm">System Physical Snapshot</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Generate a single compressed <code>.tar.gz</code> archive packaging all application state. This contains:
                    </p>
                    <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 ml-2">
                      <li>PostgreSQL relational database schema & row contents</li>
                      <li>Local vector database indices (Chroma persistent data)</li>
                      <li>All uploaded documents, training files, and images</li>
                    </ul>
                    <div className="pt-2">
                      <button
                        onClick={handleDownloadFullBackup}
                        disabled={busy}
                        className="px-4 py-2 rounded-xl bg-indigo-650 hover:bg-indigo-600 text-white font-bold text-xs flex items-center space-x-2 shadow cursor-pointer active:scale-95 transition-all disabled:opacity-50"
                      >
                        <span>📥 Generate & Download System Backup</span>
                      </button>
                    </div>
                  </div>

                  {/* Restore Panel with Drag and Drop */}
                  <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
                    <h3 className="font-bold text-slate-200 text-sm">System Restore</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Upload a previously downloaded <code>.tar.gz</code> backup archive to overwrite the entire system state.
                    </p>
                    
                    {/* Drag-and-drop zone */}
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setRestoreDragActive(true);
                      }}
                      onDragLeave={() => setRestoreDragActive(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setRestoreDragActive(false);
                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                          setRestoreFile(e.dataTransfer.files[0]);
                        }
                      }}
                      onClick={() => document.getElementById("restore-file-input")?.click()}
                      className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                        restoreDragActive 
                          ? "border-indigo-500 bg-indigo-950/20" 
                          : restoreFile 
                            ? "border-emerald-500 bg-emerald-950/5" 
                            : "border-slate-800 hover:border-indigo-500/50 bg-slate-950/40"
                      }`}
                    >
                      <input
                        type="file"
                        id="restore-file-input"
                        className="hidden"
                        accept=".tar.gz"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            setRestoreFile(e.target.files[0]);
                          }
                        }}
                      />
                      <div className="flex flex-col items-center space-y-2">
                        <Upload className={`w-8 h-8 ${restoreFile ? "text-emerald-400" : "text-indigo-400"}`} />
                        {restoreFile ? (
                          <div className="space-y-1">
                            <span className="text-xs text-slate-200 font-bold block">{restoreFile.name}</span>
                            <span className="text-[10px] text-slate-500">Size: {Math.round(restoreFile.size / 1024)} KB</span>
                          </div>
                        ) : (
                          <div>
                            <span className="text-xs text-slate-300 font-medium block">Drag and drop your <code>.tar.gz</code> backup file here</span>
                            <span className="text-[10px] text-slate-500">or click to browse local files</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {restoreFile && (
                      <div className="flex space-x-2 pt-2">
                        <button
                          onClick={() => setShowRestoreConfirm(true)}
                          disabled={restoreBusy}
                          className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow active:scale-95 transition-all cursor-pointer disabled:opacity-50"
                        >
                          {restoreBusy ? "Restoring..." : "🔥 Start Full Restore"}
                        </button>
                        <button
                          onClick={() => setRestoreFile(null)}
                          disabled={restoreBusy}
                          className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-350 text-xs font-semibold border border-slate-800 active:scale-95 transition-all cursor-pointer"
                        >
                          Clear File
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Strict Restore Confirmation Modal Overlay */}
              {showRestoreConfirm && (
                <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowRestoreConfirm(false)}>
                  <div className="bg-slate-900 border border-rose-500/30 rounded-3xl p-6 w-full max-w-md flex flex-col space-y-4 shadow-2xl relative" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center space-x-3 border-b border-slate-800 pb-3">
                      <ShieldAlert className="w-6 h-6 text-rose-500" />
                      <h3 className="font-extrabold text-slate-200 text-sm">Critical Warning: System Restore</h3>
                    </div>
                    
                    <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                      <p className="text-xs text-rose-350 font-bold leading-relaxed">
                        Warning: This will overwrite all current users, chats, memories, and configurations.
                      </p>
                    </div>

                    <p className="text-xs text-slate-400 leading-relaxed">
                      This operation is destructive and cannot be undone. Make sure you have downloaded a backup of the current state if you want to keep any current data.
                    </p>

                    <div className="flex justify-end space-x-2 pt-2">
                      <button
                        onClick={() => setShowRestoreConfirm(false)}
                        className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 text-xs font-semibold cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleExecuteRestore}
                        className="px-4 py-2 rounded-xl bg-rose-650 hover:bg-rose-600 text-white font-bold text-xs shadow active:scale-95 transition-all cursor-pointer"
                      >
                        Confirm and Overwrite
                      </button>
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

        </div>

      </main>

    </div>
  );
}

// ── Custom Markdown & LaTeX Parser Components ───────────────────────────────

function Markdown({ text }: { text: string }) {
  if (!text) return null;

  const blocks: Array<{ type: "code" | "math" | "table" | "text"; content: string; lang?: string }> = [];
  let currentText = text;

  while (currentText) {
    const codeBlockMatch = currentText.match(/^```(\w*)\n([\s\S]*?)\n```/m);
    const mathBlockMatch = currentText.match(/^\$\$([\s\S]*?)\$\$/m);
    const tableBlockMatch = currentText.match(/^(?:\|[^\n]+\|\r?\n){1,}(?:\|[-:|\s]+\|\r?\n?)(?:\|[^\n]+\|\r?\n?){1,}/m);

    const matches = [
      { type: "code" as const, match: codeBlockMatch, index: codeBlockMatch?.index ?? -1 },
      { type: "math" as const, match: mathBlockMatch, index: mathBlockMatch?.index ?? -1 },
      { type: "table" as const, match: tableBlockMatch, index: tableBlockMatch?.index ?? -1 },
    ].filter(m => m.match !== null && m.index >= 0);

    if (matches.length > 0) {
      matches.sort((a, b) => a.index - b.index);
      const first = matches[0];

      if (first.index > 0) {
        blocks.push({ type: "text", content: currentText.substring(0, first.index) });
      }

      if (first.type === "code" && first.match) {
        blocks.push({
          type: "code",
          lang: first.match[1] || "plaintext",
          content: first.match[2]
        });
      } else if (first.type === "math" && first.match) {
        blocks.push({
          type: "math",
          content: first.match[1]
        });
      } else if (first.type === "table" && first.match) {
        blocks.push({
          type: "table",
          content: first.match[0]
        });
      }

      currentText = currentText.substring(first.index + first.match![0].length);
    } else {
      blocks.push({ type: "text", content: currentText });
      break;
    }
  }

  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        if (block.type === "code") {
          return <CodeBlock key={i} lang={block.lang} code={block.content} />;
        }
        if (block.type === "math") {
          return <MathBlock key={i} latex={block.content} />;
        }
        if (block.type === "table") {
          return <TableBlock key={i} rawTable={block.content} />;
        }
        return <TextBlock key={i} text={block.content} />;
      })}
    </div>
  );
}

function CodeBlock({ lang, code }: { lang?: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const highlight = (codeText: string, language: string) => {
    if (!codeText) return "";
    const escapeHtml = (text: string) => {
      return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    };

    const escaped = escapeHtml(codeText);
    const l = (language || "").toLowerCase();

    if (l === "python") {
      return escaped
        .replace(/\b(def|class|return|if|elif|else|for|in|while|try|except|finally|import|from|as|with|lambda|and|or|not|is|None|True|False|self)\b/g, '<span class="text-indigo-400 font-bold">$1</span>')
        .replace(/(#.*)/g, '<span class="text-slate-500 italic">$1</span>')
        .replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="text-amber-400">$1</span>')
        .replace(/\b(print|len|range|str|int|float|dict|list|set|tuple|zip|enumerate|map|filter)\b/g, '<span class="text-cyan-400">$1</span>');
    }
    if (l === "javascript" || l === "typescript" || l === "ts" || l === "js" || l === "jsx" || l === "tsx") {
      return escaped
        .replace(/\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|import|export|from|default|class|extends|new|this|typeof|instanceof|async|await|true|false|null|undefined)\b/g, '<span class="text-indigo-400 font-bold">$1</span>')
        .replace(/(\/\/.*)/g, '<span class="text-slate-500 italic">$1</span>')
        .replace(/(".*?"|'.*?'|`[\s\S]*?`)/g, '<span class="text-emerald-400">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="text-amber-400">$1</span>')
        .replace(/\b(console|log|error|warn|window|document|fetch|JSON|stringify|parse|Promise|resolve|reject)\b/g, '<span class="text-cyan-400">$1</span>');
    }
    if (l === "sql") {
      return escaped
        .replace(/\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|LIKE|ORDER|BY|LIMIT|GROUP|HAVING|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|ALTER|DATABASE|INDEX|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|NULL|AS)\b/gi, '<span class="text-indigo-400 font-bold">$1</span>')
        .replace(/(#.*|--.*)/g, '<span class="text-slate-500 italic">$1</span>')
        .replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="text-amber-400">$1</span>');
    }
    if (l === "bash" || l === "sh" || l === "shell") {
      return escaped
        .replace(/\b(echo|cd|ls|grep|pwd|mkdir|rm|cp|mv|chmod|chown|sudo|apt|git|docker|npm|pip|python|cat|curl|wget)\b/g, '<span class="text-cyan-400">$1</span>')
        .replace(/(#.*)/g, '<span class="text-slate-500 italic">$1</span>')
        .replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$1</span>');
    }
    return escaped;
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden my-3 shadow-md font-mono text-xs">
      <div className="flex justify-between items-center bg-slate-900 px-4 py-2 border-b border-slate-800 text-[10px] text-slate-400 font-semibold uppercase tracking-wider select-none">
        <span>{lang || "plaintext"}</span>
        <button
          onClick={copyToClipboard}
          className="flex items-center space-x-1.5 hover:text-white transition-colors cursor-pointer"
        >
          {copied ? (
            <span className="flex items-center text-emerald-400"><Check className="w-3.5 h-3.5 mr-1" /> Copied</span>
          ) : (
            <span className="flex items-center"><ClipboardList className="w-3.5 h-3.5 mr-1" /> Copy</span>
          )}
        </button>
      </div>
      <div className="p-4 overflow-x-auto max-h-[350px]">
        <pre className="whitespace-pre">
          <code dangerouslySetInnerHTML={{ __html: highlight(code, lang || "") }} />
        </pre>
      </div>
    </div>
  );
}

function MathBlock({ latex }: { latex: string }) {
  return (
    <div className="flex justify-center p-4 my-2.5 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl text-slate-100 italic font-serif text-sm relative overflow-x-auto shadow-inner select-all">
      <span className="text-indigo-400 font-semibold select-none mr-2">f(x) = </span>
      <span>{latex}</span>
    </div>
  );
}

function TableBlock({ rawTable }: { rawTable: string }) {
  const lines = rawTable.trim().split("\n");
  if (lines.length < 2) return <pre className="text-xs">{rawTable}</pre>;

  const headers = lines[0]
    .split("|")
    .map(h => h.trim())
    .filter((_, i) => i > 0 && i < lines[0].split("|").length - 1);

  const rows = lines.slice(2).map(line => {
    return line
      .split("|")
      .map(cell => cell.trim())
      .filter((_, i) => i > 0 && i < line.split("|").length - 1);
  });

  return (
    <div className="overflow-x-auto my-3.5 rounded-xl border border-slate-800 bg-slate-950/40 shadow-lg">
      <table className="min-w-full divide-y divide-slate-800 text-xs">
        <thead className="bg-slate-900/80">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="px-4 py-3 text-left font-bold text-slate-200 uppercase tracking-wider">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-transparent">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-slate-900/30 transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-slate-300 font-medium whitespace-nowrap">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextBlock({ text }: { text: string }) {
  const lines = text.split("\n");

  const renderLine = (line: string, lineIdx: number) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("# ")) {
      return <h1 key={lineIdx} className="text-lg font-extrabold text-white mt-4 mb-2 tracking-tight border-b border-slate-800/60 pb-1">{renderInlineStyles(trimmed.substring(2))}</h1>;
    }
    if (trimmed.startsWith("## ")) {
      return <h2 key={lineIdx} className="text-base font-bold text-slate-100 mt-3.5 mb-1.5 tracking-tight">{renderInlineStyles(trimmed.substring(3))}</h2>;
    }
    if (trimmed.startsWith("### ")) {
      return <h3 key={lineIdx} className="text-sm font-semibold text-slate-200 mt-3 mb-1">{renderInlineStyles(trimmed.substring(4))}</h3>;
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      return (
        <li key={lineIdx} className="list-disc list-inside text-xs text-slate-300 ml-2 py-0.5 leading-relaxed">
          {renderInlineStyles(trimmed.substring(2))}
        </li>
      );
    }

    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
    if (orderedMatch) {
      return (
        <li key={lineIdx} className="list-decimal list-inside text-xs text-slate-300 ml-2 py-0.5 leading-relaxed">
          {renderInlineStyles(orderedMatch[2])}
        </li>
      );
    }

    if (!trimmed) {
      return <div key={lineIdx} className="h-2"></div>;
    }

    return (
      <p key={lineIdx} className="text-xs text-slate-300 leading-relaxed py-0.5">
        {renderInlineStyles(line)}
      </p>
    );
  };

  const renderInlineStyles = (raw: string) => {
    let elements: React.ReactNode[] = [];
    let lastIndex = 0;

    const regex = /(\*\*.*?\*\*|`.*?`|\$.*?\$|\[.*?\]\(.*?\))/g;
    let match;

    while ((match = regex.exec(raw)) !== null) {
      const index = match.index;
      const matchedText = match[0];

      if (index > lastIndex) {
        elements.push(raw.substring(lastIndex, index));
      }

      if (matchedText.startsWith("**") && matchedText.endsWith("**")) {
        elements.push(
          <strong key={index} className="font-extrabold text-white">
            {matchedText.slice(2, -2)}
          </strong>
        );
      } else if (matchedText.startsWith("`") && matchedText.endsWith("`")) {
        elements.push(
          <code key={index} className="px-1.5 py-0.5 rounded bg-slate-950 text-indigo-400 font-mono text-[11px] border border-slate-850">
            {matchedText.slice(1, -1)}
          </code>
        );
      } else if (matchedText.startsWith("$") && matchedText.endsWith("$")) {
        elements.push(
          <span key={index} className="font-serif italic text-indigo-300 px-0.5 font-semibold">
            {matchedText.slice(1, -1)}
          </span>
        );
      } else if (matchedText.startsWith("[") && matchedText.includes("](")) {
        const splitIdx = matchedText.indexOf("](");
        const linkText = matchedText.substring(1, splitIdx);
        const url = matchedText.substring(splitIdx + 2, matchedText.length - 1);
        elements.push(
          <a key={index} href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 underline font-semibold transition-colors">
            {linkText}
          </a>
        );
      }

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < raw.length) {
      elements.push(raw.substring(lastIndex));
    }

    return elements.length > 0 ? elements : raw;
  };

  return <div className="space-y-1">{lines.map((line, idx) => renderLine(line, idx))}</div>;
}

