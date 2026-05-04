import React, { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";

// Types
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

type Attachment = {
  filename: string;
  url: string;
  type: string;
  extracted_text: string | null;
};

type TaskSuggestion = {
  id: string;
  title: string;
  description: string;
  priority: string;
  due_at: string | null;
};

type Session = {
  session_id: string;
  category: string;
  owner: string;
  pinned: boolean;
};

type ModelOption = {
  value: string;
  label: string;
};

type Persona = {
  id: string;
  name: string;
  is_default: boolean;
};

type CuratorNudge = {
  id: number;
  nudge_type: string;
  payload?: { message?: string; title?: string };
  created_at: string;
};

// Main Chat Component
export default function ChatPage() {
  // State management
  const [sessionId, setSessionId] = useState<string>(() => {
    const existing = localStorage.getItem("ampai_session_id");
    if (existing) return existing;
    const generated = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    localStorage.setItem("ampai_session_id", generated);
    return generated;
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [taskSuggestions, setTaskSuggestions] = useState<TaskSuggestion[]>([]);

  // Configuration state
  const [modelType, setModelType] = useState("ollama");
  const [memoryMode, setMemoryMode] = useState("full");
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [personaId, setPersonaId] = useState("");
  const [memoryTopK, setMemoryTopK] = useState(5);
  const [recencyBias, setRecencyBias] = useState(0.35);
  const [categoryFilter, setCategoryFilter] = useState("");

  // Options
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([
    { value: "ollama", label: "🦙 Ollama" },
    { value: "openai", label: "✨ OpenAI" },
    { value: "gemini", label: "🌟 Gemini" },
    { value: "anthropic", label: "🔴 Anthropic" },
    { value: "anythingllm", label: "🏠 AnythingLLM" },
    { value: "openrouter", label: "🔀 OpenRouter" },
  ]);

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [nudges, setNudges] = useState<CuratorNudge[]>([]);
  const [localOnlyMode, setLocalOnlyMode] = useState(true);
  const [recallQuery, setRecallQuery] = useState("");
  const [recallSummary, setRecallSummary] = useState("");

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Authentication
  const token = localStorage.getItem("ampai_token") || "";

  // Scroll to bottom of messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Effect to scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load sessions
  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch(`/api/sessions?limit=60&offset=0`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) {
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error("Failed to load sessions:", error);
    }
  }, [token]);

  // Load session history
  const loadSessionHistory = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`/api/history/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) {
        const historyMessages = (data.messages || []).map((msg: any, index: number) => ({
          id: `msg-${index}`,
          role: msg.type === "human" ? "user" : "assistant",
          content: msg.content,
          timestamp: new Date(msg.timestamp || Date.now()),
        }));
        setMessages(historyMessages);
      }
    } catch (error) {
      console.error("Failed to load session history:", error);
    }
  }, [token]);

  // Load personas
  const loadPersonas = useCallback(async () => {
    try {
      const response = await fetch(`/api/personas`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) {
        setPersonas(data.personas || []);
      }
    } catch (error) {
      console.error("Failed to load personas:", error);
    }
  }, [token]);

  const loadNudges = useCallback(async () => {
    try {
      const response = await fetch(`/api/nudges?session_id=${encodeURIComponent(sessionId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) setNudges(data.nudges || []);
    } catch (error) {
      console.error("Failed to load nudges:", error);
    }
  }, [sessionId, token]);

  const loadConfigStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/configs/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) {
        setLocalOnlyMode(String(data.local_only_mode ?? "true").toLowerCase() !== "false");
      }
    } catch (error) {
      console.error("Failed to load config status:", error);
    }
  }, [token]);

  const loadModelOptions = useCallback(async () => {
    try {
      const response = await fetch(`/api/models/options`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok && Array.isArray(data.providers)) {
        setModelOptions(data.providers);
      }
    } catch (error) {
      console.error("Failed to load model options:", error);
    }
  }, [token]);

  // Initialize
  useEffect(() => {
    loadSessions();
    loadSessionHistory(sessionId);
    loadPersonas();
    loadNudges();
    loadConfigStatus();
    loadModelOptions();
  }, [loadSessions, loadSessionHistory, loadPersonas, loadNudges, loadConfigStatus, loadModelOptions, sessionId]);

  const ackNudge = useCallback(async (nudgeId: number) => {
    await fetch("/api/nudges/ack", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ nudge_id: nudgeId }),
    });
    loadNudges();
  }, [loadNudges, token]);

  const runRecallSearch = useCallback(async () => {
    if (!recallQuery.trim()) return;
    try {
      const response = await fetch("/api/recall/search", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ q: recallQuery.trim(), session_id: "", limit: 12 }),
      });
      const data = await response.json();
      if (response.ok) setRecallSummary(data.summary || "");
    } catch (error) {
      console.error("Recall search failed:", error);
    }
  }, [recallQuery, token]);

  // Handle sending a message
  const handleSend = async () => {
    if ((!inputValue.trim() && attachments.length === 0) || isLoading) return;

    // Add user message to chat
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: inputValue.trim() || "(attachment)",
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setAttachments([]);
    setIsLoading(true);

    try {
      // Prepare payload
      const payload: any = {
        session_id: sessionId,
        message: inputValue.trim() || "Please review the attached files.",
        model_type: modelType,
        memory_mode: memoryMode,
        use_web_search: useWebSearch,
        attachments: attachments,
        persona_id: personaId || null,
      };

      // Add memory parameters if in indexed mode
      if (memoryMode === "indexed") {
        payload.memory_top_k = memoryTopK;
        payload.recency_bias = recencyBias;
        if (categoryFilter) payload.category_filter = categoryFilter;
      }

      // Send request
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok) {
        // Add AI response to chat
        const aiMessage: Message = {
          id: `msg-${Date.now()}-ai`,
          role: "assistant",
          content: data.response || "No response",
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, aiMessage]);
        setTaskSuggestions(data.task_suggestions || []);

        // Refresh sessions
        loadSessions();
      } else {
        // Add error message
        const errorMessage: Message = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: `⚠️ ${data.detail || "Something went wrong. Check your AI model config."}`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      // Add error message
      const errorMessage: Message = {
        id: `msg-${Date.now()}-error`,
        role: "assistant",
        content: `⚠️ Failed to send message: ${error instanceof Error ? error.message : "Unknown error"}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle file attachment
  const handleAttachFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`/api/upload?session_id=${encodeURIComponent(sessionId)}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          setAttachments(prev => [...prev, data]);
        } else {
          console.error("Upload failed");
        }
      } catch (error) {
        console.error("Upload error:", error);
      }
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Handle key press (Enter to send, Shift+Enter for new line)
  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Create new chat session
  const handleNewChat = () => {
    const newSessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    setSessionId(newSessionId);
    setMessages([]);
    setAttachments([]);
    localStorage.setItem("ampai_session_id", newSessionId);
    loadSessions();
  };

  // Render message content with basic markdown support
  const renderMessageContent = (content: string) => {
    // Simple markdown: code blocks, bold, line breaks
    return (
      <div
        dangerouslySetInnerHTML={{
          __html: content
            .replace(/&/g, "&")
            .replace(/</g, "<")
            .replace(/>/g, ">")
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br />')
        }}
      />
    );
  };

  // Render attachment previews
  const renderAttachmentPreviews = () => {
    if (attachments.length === 0) return null;

    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
        {attachments.map((attachment, index) => (
          <div
            key={index}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: "rgba(99,102,241,.12)",
              border: "1px solid rgba(99,102,241,.25)",
              borderRadius: "999px",
              padding: "4px 10px",
              fontSize: ".78rem"
            }}
          >
            📎 <span style={{ maxWidth: "130px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {attachment.filename}
            </span>
            <button
              onClick={() => setAttachments(prev => prev.filter((_, i) => i !== index))}
              style={{
                background: "none",
                border: "none",
                color: "var(--red)",
                cursor: "pointer",
                fontSize: ".9rem",
                padding: "0 2px"
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    );
  };

  // Render task suggestions
  const renderTaskSuggestions = () => {
    if (taskSuggestions.length === 0) return null;

    return (
      <div style={{
        display: "none", // Hidden for now, can be enabled later
        marginTop: "10px",
        background: "var(--bg-2)",
        border: "1px solid var(--border)",
        borderRadius: "10px",
        padding: "10px"
      }}>
        <div style={{ fontSize: ".8rem", fontWeight: "600", marginBottom: "8px" }}>Suggested actions</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {taskSuggestions.map(suggestion => (
            <div
              key={suggestion.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px"
              }}
            >
              <div style={{ flex: 1, fontSize: ".82rem" }}>
                {suggestion.title || "Suggested task"}
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  try {
                    const response = await fetch(`/api/tasks/from-suggestion/${encodeURIComponent(suggestion.id)}`, {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${token}`,
                      },
                    });

                    if (response.ok) {
                      setTaskSuggestions(prev => prev.filter(s => s.id !== suggestion.id));
                    }
                  } catch (error) {
                    console.error("Failed to create task:", error);
                  }
                }}
              >
                Create Task
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Render chat messages
  const renderMessages = () => {
    if (messages.length === 0) {
      return (
        <div style={{
          display: "flex",
          gap: "12px",
          maxWidth: "80%",
          alignSelf: "flex-start"
        }}>
          <div style={{
            width: "34px",
            height: "34px",
            borderRadius: "50%",
            flexShrink: 0,
            background: "linear-gradient(135deg,#10b981,#3b82f6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: ".75rem",
            fontWeight: "700",
            color: "#fff"
          }}>
            AI
          </div>
          <div style={{
            padding: "12px 16px",
            borderRadius: "12px",
            border: "1px solid var(--border)",
            lineHeight: "1.6",
            fontSize: ".9rem",
            background: "var(--bg-3)",
            borderTopLeftRadius: "3px"
          }}>
            <strong>Hello! I'm AmpAI.</strong><br />
            I remember your conversations and use that memory to give you better, personalised answers.<br /><br />
            <span style={{ color: "var(--muted)", fontSize: ".85rem" }}>
              Start chatting — every message is saved and indexed for future recall.
            </span>
          </div>
        </div>
      );
    }

    return (
      <>
        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: "flex",
              gap: "12px",
              maxWidth: "78%",
              animation: "msgIn .25s ease",
              alignSelf: message.role === "user" ? "flex-end" : "flex-start",
              flexDirection: message.role === "user" ? "row-reverse" : "row"
            }}
          >
            <div style={{
              width: "34px",
              height: "34px",
              borderRadius: "50%",
              flexShrink: 0,
              background: message.role === "user"
                ? "linear-gradient(135deg,#6366f1,#a855f7)"
                : "linear-gradient(135deg,#10b981,#3b82f6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: ".75rem",
              fontWeight: "700",
              color: "#fff"
            }}>
              {message.role === "user"
                ? (localStorage.getItem("ampai_username") || "U")[0].toUpperCase()
                : "AI"}
            </div>
            <div style={{
              padding: "12px 16px",
              borderRadius: "12px",
              lineHeight: "1.6",
              fontSize: ".9rem",
              background: message.role === "user"
                ? "var(--accent)"
                : "var(--bg-3)",
              color: message.role === "user" ? "#fff" : "inherit",
              border: message.role === "user"
                ? "none"
                : "1px solid var(--border)",
              borderTopLeftRadius: message.role === "user" ? "3px" : "12px",
              borderTopRightRadius: message.role === "user" ? "12px" : "3px"
            }}>
              {renderMessageContent(message.content)}
            </div>
          </div>
        ))}
        {isLoading && (
          <div style={{
            display: "flex",
            gap: "12px",
            maxWidth: "78%",
            alignSelf: "flex-start"
          }}>
            <div style={{
              width: "34px",
              height: "34px",
              borderRadius: "50%",
              flexShrink: 0,
              background: "linear-gradient(135deg,#10b981,#3b82f6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: ".75rem",
              fontWeight: "700",
              color: "#fff"
            }}>
              <div style={{
                width: "16px",
                height: "16px",
                border: "2px solid #e0e0e0",
                borderLeftColor: "#3b82f6",
                borderRadius: "50%",
                animation: "spin 1s linear infinite"
              }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </>
    );
  };

  // Render memory context panel
  const renderMemoryContext = () => {
    // This would be implemented to show memory context
    return null;
  };

  // Render the full component
  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Session sidebar */}
      <div style={{
        width: "260px",
        minWidth: "260px",
        background: "var(--bg-2)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}>
        <div style={{
          padding: "14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          gap: "10px"
        }}>
          <button
            onClick={handleNewChat}
            style={{
              width: "100%",
              padding: "10px",
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              background: "var(--accent)",
              color: "#fff",
              fontFamily: "inherit",
              fontSize: ".875rem",
              fontWeight: "600"
            }}
          >
            ＋ New Chat
          </button>
          <input
            placeholder="Search sessions…"
            style={{
              width: "100%",
              padding: "8px 10px",
              borderRadius: "8px",
              background: "rgba(0,0,0,.2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              fontFamily: "inherit",
              fontSize: ".82rem",
              outline: "none"
            }}
          />
        </div>
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px"
        }}>
          {sessions.map(session => (
            <div
              key={session.session_id}
              onClick={() => {
                setSessionId(session.session_id);
                loadSessionHistory(session.session_id);
              }}
              style={{
                padding: "10px",
                borderRadius: "8px",
                cursor: "pointer",
                marginBottom: "4px",
                background: sessionId === session.session_id ? "rgba(99,102,241,.2)" : "transparent"
              }}
            >
              <div style={{ fontSize: ".85rem", fontWeight: "500" }}>
                {session.category || "Untitled Chat"}
              </div>
              <div style={{ fontSize: ".7rem", color: "var(--muted)", marginTop: "2px" }}>
                {session.session_id.substring(0, 8)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat main area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Chat topbar */}
        <div style={{
          padding: "12px 18px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          background: "var(--glass)",
          backdropFilter: "blur(12px)"
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: "600", fontSize: ".95rem" }}>
              {sessions.find(s => s.session_id === sessionId)?.category || "New Chat"}
            </div>
            <div style={{ fontSize: ".72rem", color: "var(--muted)" }}>
              {sessionId}
            </div>
            <div style={{ display: "flex", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
              {localOnlyMode && <span style={{ fontSize: ".7rem" }}>Local Mode Active</span>}
              {nudges.length > 0 && <span style={{ fontSize: ".7rem" }}>{nudges.length} Curator Nudges</span>}
            </div>
          </div>
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: "8px",
              background: "rgba(0,0,0,.25)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              fontFamily: "inherit",
              fontSize: ".82rem",
              outline: "none"
            }}
          >
            {modelOptions.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={memoryMode}
            onChange={(e) => setMemoryMode(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: "8px",
              background: "rgba(0,0,0,.25)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              fontFamily: "inherit",
              fontSize: ".82rem",
              outline: "none"
            }}
          >
            <option value="full">🧠 Full Memory</option>
            <option value="indexed">⚡ Indexed Memory</option>
            <option value="context_only">💬 Context Only</option>
            <option value="none">⛔ No Memory</option>
          </select>
          <label style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            fontSize: ".8rem",
            color: "var(--muted)",
            cursor: "pointer"
          }}>
            <input
              type="checkbox"
              checked={useWebSearch}
              onChange={(e) => setUseWebSearch(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            /> 🌐
          </label>
        </div>

        {/* Messages container */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          scrollBehavior: "smooth"
        }}>
          <div style={{ border: "1px solid var(--border)", borderRadius: "10px", padding: "8px", marginBottom: "10px" }}>
            <div style={{ fontSize: ".78rem", marginBottom: "6px" }}>Cross-session recall</div>
            <div style={{ display: "flex", gap: "6px" }}>
              <input value={recallQuery} onChange={(e) => setRecallQuery(e.target.value)} placeholder="Search prior sessions..." style={{ flex: 1 }} />
              <button onClick={runRecallSearch}>Search</button>
            </div>
            {recallSummary && <pre style={{ whiteSpace: "pre-wrap", marginTop: "8px", fontSize: ".76rem" }}>{recallSummary}</pre>}
          </div>
          {nudges.slice(0, 2).map((nudge) => (
            <div key={`nudge-${nudge.id}`} style={{ border: "1px solid var(--border)", borderRadius: "10px", padding: "10px" }}>
              <div style={{ fontSize: ".78rem", fontWeight: 600 }}>Curator nudge</div>
              <div style={{ fontSize: ".82rem", color: "var(--muted)", marginTop: "4px" }}>
                {nudge.payload?.message || nudge.payload?.title || "You have a pending follow-up."}
              </div>
              <button onClick={() => ackNudge(nudge.id)} style={{ marginTop: "8px" }}>Acknowledge</button>
            </div>
          ))}
          {renderMessages()}
        </div>

        {/* Input area */}
        <div style={{
          padding: "14px 18px",
          borderTop: "1px solid var(--border)",
          background: "linear-gradient(to top,var(--bg) 70%,transparent)"
        }}>
          {renderAttachmentPreviews()}
          <div style={{
            display: "flex",
            alignItems: "flex-end",
            gap: "8px",
            background: "var(--bg-3)",
            border: "1px solid var(--border)",
            borderRadius: "14px",
            padding: "8px 12px",
            transition: "border-color .2s"
          }}>
            <button
              onClick={() => fileInputRef.current?.click()}
              title="Attach file"
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--muted)",
                padding: "6px",
                fontSize: "1.1rem",
                transition: "color .15s"
              }}
            >
              📎
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleAttachFiles}
              style={{ display: "none" }}
              multiple
            />
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Message AmpAI…"
              style={{
                flex: 1,
                background: "none",
                border: "none",
                color: "var(--text)",
                fontFamily: "inherit",
                fontSize: ".95rem",
                resize: "none",
                outline: "none",
                maxHeight: "140px",
                minHeight: "24px",
                lineHeight: "1.5",
                padding: "6px 0"
              }}
              rows={1}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || (!inputValue.trim() && attachments.length === 0)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "none",
                cursor: "pointer",
                background: "var(--accent)",
                color: "#fff",
                fontFamily: "inherit",
                fontSize: ".875rem",
                fontWeight: "600",
                transition: "all .18s",
                opacity: isLoading || (!inputValue.trim() && attachments.length === 0) ? ".6" : "1"
              }}
            >
              Send
            </button>
          </div>
          <div style={{
            display: "flex",
            marginTop: "6px",
            padding: "0 2px"
          }}>
            <span style={{ fontSize: ".72rem", color: "var(--muted)" }}>
              Shift+Enter for newline · Enter to send
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<ChatPage />);
}
