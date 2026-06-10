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
  EyeOff
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

import { S, Auth, Msg, Session, CoreMem, User as AdminUser, Attach, Persona, MemInbox, BrowserJob, TerminalLog, Task } from "./state";

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

  const [serverUrl, setServerUrl] = useState<string>(() => localStorage.getItem("ampai.serverUrl") || "http://127.0.0.1:8001");
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
  const [providers, setProviders] = useState<any[]>([]);
  const [providerModels, setProviderModels] = useState<Record<string, any[]>>({});
  const [sessionSearch, setSessionSearch] = useState<string>("");
  const [sessionCategoryFilter, setSessionCategoryFilter] = useState<string>("");
  
  // Modals / Renaming states
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const [categoryModalSessionId, setCategoryModalSessionId] = useState<string | null>(null);
  const [categoryValue, setCategoryValue] = useState<string>("");

  // Memory Panel States
  const [memories, setMemories] = useState<CoreMem[]>([]);
  const [memoryInbox, setMemoryInbox] = useState<MemInbox[]>([]);
  const [memSubTab, setMemSubTab] = useState<"core" | "inbox" | "analytics">("core");
  const [inboxFilter, setInboxFilter] = useState<string>("pending");
  const [newFact, setNewFact] = useState<string>("");
  const [editingMemId, setEditingMemId] = useState<number | null>(null);
  const [editingFactText, setEditingFactText] = useState<string>("");

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
  const [configs, setConfigs] = useState<Record<string, string>>({});
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminStats, setAdminStats] = useState<any>(null);
  const [telegramStatus, setTelegramStatus] = useState<any>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [updateVersion, setUpdateVersion] = useState<any>(null);
  const [updateStatus, setUpdateStatus] = useState<any>(null);
  const [updateLogs, setUpdateLogs] = useState<string[]>([]);
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
          const bRes = await apiCall<any>("/api/admin/backups").catch(() => ({ backups: [] }));
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

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

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

  // --- Send Chat Message ---
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
      const response = await apiCall<any>("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          message: currentMsgText || "Please review the attached file.",
          model_type: modelType,
          model_name: modelName || undefined,
          memory_mode: "indexed",
          use_web_search: useWebSearch,
          enable_browser_tools: enableBrowserTools,
          enable_terminal_tools: enableTerminalTools,
          attachments: attachments
        })
      });

      const aiMsg: Msg = {
        role: "assistant",
        content: response.response || response.message || "No response details from agent.",
        time: new Date().toLocaleTimeString()
      };
      setMsgs(prev => [...prev, aiMsg]);
      setAttachments([]);
    } catch (err: any) {
      triggerToast("Failed to get agent response: " + err.message, "err");
      // Add error message as system notification
      setMsgs(prev => [...prev, { role: "assistant", content: `System Error: ${err.message}`, time: "" }]);
    } finally {
      setBusy(false);
    }
  };

  // --- Attachment Upload ---
  const handleAttachFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const formData = new FormData();
    formData.append("file", file);
    
    triggerToast(`Uploading ${file.name}...`, "info");
    try {
      const payload = await apiCall<Attach>(`/api/upload?session_id=${encodeURIComponent(sessionId)}`, {
        method: "POST",
        body: formData
      });
      setAttachments(prev => [...prev, payload]);
      triggerToast(`Uploaded ${file.name} successfully`, "ok");
    } catch (err: any) {
      triggerToast(`Upload failed: ${err.message}`, "err");
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
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search chats..."
                      value={sessionSearch}
                      onChange={(e) => setSessionSearch(e.target.value)}
                      className="w-full px-3.5 py-2 pl-9 rounded-xl border border-slate-800 bg-slate-900/40 text-slate-200 placeholder-slate-500 text-xs focus:ring-1 focus:ring-indigo-500/40 focus:outline-none focus:border-indigo-500 transition-all"
                    />
                    <History className="w-3.5 h-3.5 text-slate-500 absolute left-3.5 top-3" />
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

              {/* Main chat window container */}
              <div className="flex-1 flex flex-col bg-slate-900/10 overflow-hidden relative">
                
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

                    <button
                      onClick={() => handleCreateNewSession()}
                      className="lg:hidden p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all"
                      title="New chat"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Messages Box scrollable */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
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
                      
                      {/* Bubble */}
                      <div className="space-y-1 flex flex-col">
                        <span className={`text-[10px] text-slate-500 ${m.role === "user" ? "text-right" : ""}`}>
                          {m.role === "user" ? "You" : "AmpAI Assistant"}
                        </span>
                        <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-lg max-w-lg ${
                          m.role === "user" 
                            ? "bg-indigo-600/90 text-white rounded-tr-none" 
                            : "bg-slate-900/90 text-slate-200 border border-slate-800 rounded-tl-none"
                        }`}>
                          <p className="whitespace-pre-wrap">{m.content}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {/* Busy loader dots */}
                  {busy && (
                    <div className="flex space-x-4 max-w-3xl mr-auto">
                      <div className="w-9 h-9 rounded-xl bg-slate-800 text-indigo-400 border border-slate-700/60 flex items-center justify-center font-bold text-xs flex-shrink-0">
                        AI
                      </div>
                      <div className="space-y-1 flex flex-col">
                        <span className="text-[10px] text-slate-500">AmpAI Assistant</span>
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
                  
                  {/* Attachments list bar */}
                  {attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2 p-2 bg-slate-950/80 rounded-xl border border-slate-850">
                      {attachments.map((attach, idx) => (
                        <div key={idx} className="flex items-center space-x-2 bg-slate-800 px-3 py-1 rounded-lg border border-slate-700/60 text-xs">
                          <span className="text-slate-300 font-medium max-w-[150px] truncate">{attach.filename}</span>
                          <button
                            type="button"
                            onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                            className="text-slate-400 hover:text-rose-400 font-bold"
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
                  {(["core", "inbox", "analytics"] as const).map(sub => (
                    <button
                      key={sub}
                      onClick={() => setMemSubTab(sub)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                        memSubTab === sub 
                          ? "bg-indigo-600 text-white shadow-sm" 
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {sub === "core" ? "Core Facts" : sub === "inbox" ? "Inbox Pending" : "Analytics"}
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
                        className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Insert Fact</span>
                      </button>
                    </form>
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
                        type="password"
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
                          method: "PATCH",
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
                          await apiCall("/api/admin/backups", { method: "POST" });
                          const res = await apiCall<any>("/api/admin/backups");
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
                              await apiCall(`/api/admin/backups/${encodeURIComponent(b.filename)}/restore`, { method: "POST" });
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

            </div>
          )}

        </div>

      </main>

    </div>
  );
}
