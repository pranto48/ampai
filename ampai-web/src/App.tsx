import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  Brain, 
  LayoutDashboard, 
  MessageSquare, 
  Settings, 
  User, 
  ShieldAlert, 
  ListChecks, 
  Globe, 
  Database, 
  Sparkles, 
  ArrowRight, 
  Copy, 
  Check, 
  Sun, 
  Moon, 
  Menu, 
  X, 
  ChevronDown, 
  Cpu, 
  Lock
} from 'lucide-react';
import { Logo } from './components/Logo';
import './App.css';

type TabType = 'home' | 'overview' | 'features' | 'installation' | 'getting-started' | 'news' | 'integrations' | 'advanced' | 'references' | 'faq';
type FeatureType = 'dashboard' | 'chat' | 'memory' | 'taskboard' | 'automation' | 'terminal' | 'models' | 'profile' | 'config' | 'admin';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [activeFeature, setActiveFeature] = useState<FeatureType>('chat');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  // Initialize and persist theme
  useEffect(() => {
    const savedTheme = localStorage.getItem('ampai-theme') as 'dark' | 'light';
    if (savedTheme) {
      setTheme(savedTheme);
      if (savedTheme === 'light') {
        document.documentElement.classList.add('light');
      } else {
        document.documentElement.classList.remove('light');
      }
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('ampai-theme', newTheme);
    if (newTheme === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(id);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const toggleFaq = (index: number) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  // Helper component for copyable code blocks
  const CodeBlock: React.FC<{ code: string; language: string; id: string }> = ({ code, language, id }) => {
    return (
      <div className="code-block-wrapper">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 1rem', background: 'var(--bg-secondary)', borderTopLeftRadius: '8px', borderTopRightRadius: '8px', borderBottom: '1px solid var(--border-color)', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
          <span>{language}</span>
        </div>
        <button 
          className="code-block-copy-btn" 
          onClick={() => handleCopy(code, id)}
          title="Copy to clipboard"
        >
          {copiedText === id ? <Check size={14} className="terminal-prompt" /> : <Copy size={14} />}
        </button>
        {copiedText === id && <span className="code-badge-success">Copied!</span>}
        <pre><code style={{ color: 'var(--text-primary)' }}>{code}</code></pre>
      </div>
    );
  };

  return (
    <div className="app-container">
      {/* Sticky Header Navigation */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo-container" onClick={() => setActiveTab('home')}>
            <Logo />
            <span className="logo-text">AmpAI</span>
          </div>

          <nav className="nav-links">
            <button className={`nav-item ${activeTab === 'home' ? 'active' : ''}`} onClick={() => setActiveTab('home')}>Home</button>
            <button className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
            <button className={`nav-item ${activeTab === 'features' ? 'active' : ''}`} onClick={() => { setActiveTab('features'); setActiveFeature('chat'); }}>Features</button>
            <button className={`nav-item ${activeTab === 'installation' ? 'active' : ''}`} onClick={() => setActiveTab('installation')}>Installation</button>
            <button className={`nav-item ${activeTab === 'getting-started' ? 'active' : ''}`} onClick={() => setActiveTab('getting-started')}>Getting started</button>
            <button className={`nav-item ${activeTab === 'integrations' ? 'active' : ''}`} onClick={() => setActiveTab('integrations')}>Integrations</button>
            <button className={`nav-item ${activeTab === 'advanced' ? 'active' : ''}`} onClick={() => setActiveTab('advanced')}>Advanced</button>
            <button className={`nav-item ${activeTab === 'references' ? 'active' : ''}`} onClick={() => setActiveTab('references')}>References</button>
            <button className={`nav-item ${activeTab === 'news' ? 'active' : ''}`} onClick={() => setActiveTab('news')}>News</button>
            <button className={`nav-item ${activeTab === 'faq' ? 'active' : ''}`} onClick={() => setActiveTab('faq')}>FAQ</button>
          </nav>

          <div className="header-actions">
            <button className="icon-btn" onClick={toggleTheme} title="Toggle Light/Dark Theme">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <a 
              href="https://github.com/pranto48/ampai" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="btn-github"
            >
              <Cpu size={16} />
              <span>GitHub</span>
            </a>
            <button className="icon-btn hamburger" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <nav className="mobile-nav fade-in">
          <button className={`nav-item ${activeTab === 'home' ? 'active' : ''}`} onClick={() => { setActiveTab('home'); setMobileMenuOpen(false); }}>Home</button>
          <button className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => { setActiveTab('overview'); setMobileMenuOpen(false); }}>Overview</button>
          <button className={`nav-item ${activeTab === 'features' ? 'active' : ''}`} onClick={() => { setActiveTab('features'); setActiveFeature('chat'); setMobileMenuOpen(false); }}>Features</button>
          <button className={`nav-item ${activeTab === 'installation' ? 'active' : ''}`} onClick={() => { setActiveTab('installation'); setMobileMenuOpen(false); }}>Installation</button>
          <button className={`nav-item ${activeTab === 'getting-started' ? 'active' : ''}`} onClick={() => { setActiveTab('getting-started'); setMobileMenuOpen(false); }}>Getting started</button>
          <button className={`nav-item ${activeTab === 'integrations' ? 'active' : ''}`} onClick={() => { setActiveTab('integrations'); setMobileMenuOpen(false); }}>Integrations</button>
          <button className={`nav-item ${activeTab === 'advanced' ? 'active' : ''}`} onClick={() => { setActiveTab('advanced'); setMobileMenuOpen(false); }}>Advanced</button>
          <button className={`nav-item ${activeTab === 'references' ? 'active' : ''}`} onClick={() => { setActiveTab('references'); setMobileMenuOpen(false); }}>References</button>
          <button className={`nav-item ${activeTab === 'news' ? 'active' : ''}`} onClick={() => { setActiveTab('news'); setMobileMenuOpen(false); }}>News</button>
          <button className={`nav-item ${activeTab === 'faq' ? 'active' : ''}`} onClick={() => { setActiveTab('faq'); setMobileMenuOpen(false); }}>FAQ</button>
        </nav>
      )}

      {/* Main Content Render */}
      <main className="main-content">
        
        {/* ==================== HOME TAB ==================== */}
        {activeTab === 'home' && (
          <section className="fade-in">
            <div className="hero-section">
              <div className="author-badge">
                <Sparkles size={14} />
                <span>Open Source Project by IT Support BD & Arif Mahmud</span>
              </div>
              <h1 className="hero-title">Your Secure, Self-Hosted Autonomous Personal AI Agent</h1>
              <p className="hero-subtitle">
                AmpAI bridges the gap between high-performance local AI models, persistent cognitive long-term memories, and advanced actuator tools like browser automation and a secure sandboxed shell terminal.
              </p>
              <div className="hero-cta">
                <button className="btn-primary" onClick={() => setActiveTab('installation')}>
                  Get Started Setup
                  <ArrowRight size={18} />
                </button>
                <button className="btn-secondary" onClick={() => { setActiveTab('features'); setActiveFeature('chat'); }}>
                  Explore Agent Tools
                </button>
              </div>

              {/* Stat badges */}
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-number">100%</div>
                  <div className="stat-label">Self-Hosted / Local</div>
                </div>
                <div className="stat-card">
                  <div className="stat-number">&lt;50ms</div>
                  <div className="stat-label">Hybrid Memory Latency</div>
                </div>
                <div className="stat-card">
                  <div className="stat-number">Layered</div>
                  <div className="stat-label">Security Boundaries</div>
                </div>
                <div className="stat-card">
                  <div className="stat-number">Docker</div>
                  <div className="stat-label">One-Click Install Ready</div>
                </div>
              </div>
            </div>

            <div className="section-header" style={{ textAlign: 'center', marginTop: '4rem' }}>
              <span className="section-tag">Core Value Proposition</span>
              <h2 className="section-title">Why Deploy AmpAI?</h2>
              <p className="section-subtitle" style={{ margin: '0 auto' }}>
                Engineered with high performance, strict local security, and persistent context at its core.
              </p>
            </div>

            <div className="glass-grid">
              <div className="glass-card">
                <div className="card-icon-wrapper"><Brain size={24} /></div>
                <h3>Cognitive Long-Term Memory</h3>
                <p>Combines Redis for instantaneous session recalls, PostgreSQL with pgvector for semantic knowledge retrieval, and ChromaDB for doc embeds.</p>
              </div>
              <div className="glass-card">
                <div className="card-icon-wrapper"><Lock size={24} /></div>
                <h3>Sandboxed Security Policies</h3>
                <p>Never worry about rogue commands. A multi-layered validation structure blocks hazardous commands (e.g. format, registry modifications) at the prompt level.</p>
              </div>
              <div className="glass-card">
                <div className="card-icon-wrapper"><Globe size={24} /></div>
                <h3>Browserless Scraping Actuator</h3>
                <p>Allows the agent to crawl the web, scrape articles, synthesize real-time data, and bypass complex HTML pages using an allowlisted chromium node.</p>
              </div>
            </div>
          </section>
        )}

        {/* ==================== OVERVIEW TAB ==================== */}
        {activeTab === 'overview' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Architecture & Concepts</span>
              <h2 className="section-title">System Overview</h2>
              <p className="section-subtitle">
                AmpAI is built as a microservices architecture orchestrating a local agent cognitive loop. It integrates user interactions, vector databases, and system actuators.
              </p>
            </div>

            <div className="architecture-container">
              <div className="flow-step-list">
                <h3>The Agent Cognitive Loop</h3>
                <div className="flow-step">
                  <div className="flow-step-num">1</div>
                  <div className="flow-step-content">
                    <h4>Perception & Message Intake</h4>
                    <p>The user inputs a message via the Glassmorphic Desktop Web UI or the Telegram bot webhook routing layer.</p>
                  </div>
                </div>
                <div className="flow-step">
                  <div className="flow-step-num">2</div>
                  <div className="flow-step-content">
                    <h4>Context & Memory Retrieval</h4>
                    <p>The backend queries local Redis for active session context and concurrently triggers pgvector/ChromaDB hybrid search to load past relative facts.</p>
                  </div>
                </div>
                <div className="flow-step">
                  <div className="flow-step-num">3</div>
                  <div className="flow-step-content">
                    <h4>LLM Inference & Tool Selection</h4>
                    <p>The core LLM (Ollama model, Gemini, OpenAI) evaluates variables and decides if it needs tools (Web search, Terminal, Browser crawler) to compile its answer.</p>
                  </div>
                </div>
                <div className="flow-step">
                  <div className="flow-step-num">4</div>
                  <div className="flow-step-content">
                    <h4>Actuator Execution & Guardrails</h4>
                    <p>Tools are executed. Shell terminal requests undergo strict regex parsing and approval block checks to prevent unauthorized scripts.</p>
                  </div>
                </div>
                <div className="flow-step">
                  <div className="flow-step-num">5</div>
                  <div className="flow-step-content">
                    <h4>Memory Consolidation</h4>
                    <p>Chat turns with an importance score exceeding 0.15 are sent to the memory curation inbox for approval to become permanent vector facts.</p>
                  </div>
                </div>
              </div>

              <div className="glass-card">
                <h3>Microservices Deployment Stack</h3>
                <p>The entire environment deploys as a multi-container stack, isolating logic and persistent engines:</p>
                <table className="architecture-table">
                  <thead>
                    <tr>
                      <th>Service Name</th>
                      <th>Technology</th>
                      <th>Port Mapping</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><code>ampai-frontend</code></td>
                      <td>Nginx / React</td>
                      <td><code>8080:80</code></td>
                    </tr>
                    <tr>
                      <td><code>ampai-server</code></td>
                      <td>FastAPI / Python</td>
                      <td><code>8000:8000</code></td>
                    </tr>
                    <tr>
                      <td><code>ampai-vector-db</code></td>
                      <td>PostgreSQL + pgvector</td>
                      <td>Internal</td>
                    </tr>
                    <tr>
                      <td><code>ampai-redis</code></td>
                      <td>Redis 7 Cache</td>
                      <td>Internal</td>
                    </tr>
                    <tr>
                      <td><code>ampai-chromadb</code></td>
                      <td>ChromaDB Vector</td>
                      <td><code>8001:8000</code></td>
                    </tr>
                    <tr>
                      <td><code>ampai-browser</code></td>
                      <td>Browserless Chrome</td>
                      <td>Internal</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* ==================== FEATURES TAB ==================== */}
        {activeTab === 'features' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Interactive Preview</span>
              <h2 className="section-title">Explore AmpAI Workspace</h2>
              <p className="section-subtitle">
                Select a console option from the side panel to simulate the interface, logs, and actuators of the agent workspace.
              </p>
            </div>

            <div className="features-simulator">
              <div className="simulator-sidebar">
                <div className="simulator-sidebar-title">Agent Workspace Modules</div>
                <button className={`simulator-menu-item ${activeFeature === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveFeature('dashboard')}>
                  <LayoutDashboard size={16} />
                  Dashboard
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'chat' ? 'active' : ''}`} onClick={() => setActiveFeature('chat')}>
                  <MessageSquare size={16} />
                  Agent Chat
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'memory' ? 'active' : ''}`} onClick={() => setActiveFeature('memory')}>
                  <Brain size={16} />
                  Cognitive Memory
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'taskboard' ? 'active' : ''}`} onClick={() => setActiveFeature('taskboard')}>
                  <ListChecks size={16} />
                  Task Board
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'automation' ? 'active' : ''}`} onClick={() => setActiveFeature('automation')}>
                  <Globe size={16} />
                  Web Automation
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'terminal' ? 'active' : ''}`} onClick={() => setActiveFeature('terminal')}>
                  <Terminal size={16} />
                  Shell Terminal
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'models' ? 'active' : ''}`} onClick={() => setActiveFeature('models')}>
                  <Cpu size={16} />
                  AI Models & Personas
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'profile' ? 'active' : ''}`} onClick={() => setActiveFeature('profile')}>
                  <User size={16} />
                  My Profile
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'config' ? 'active' : ''}`} onClick={() => setActiveFeature('config')}>
                  <Settings size={16} />
                  System Config
                </button>
                <button className={`simulator-menu-item ${activeFeature === 'admin' ? 'active' : ''}`} onClick={() => setActiveFeature('admin')}>
                  <ShieldAlert size={16} />
                  Admin Console
                </button>
              </div>

              <div className="simulator-viewport">
                {/* 1. Dashboard View */}
                {activeFeature === 'dashboard' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>System Dashboard</h3>
                        <p className="viewport-description">Real-time status overview of active memory databases and docker node processes.</p>
                      </div>
                      <span className="integration-badge llm" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>System Healthy</span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                      <div className="glass-card" style={{ padding: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Memory Indexer (pgvector)</span>
                          <span className="mockup-dot green"></span>
                        </div>
                        <p style={{ fontSize: '1.2rem', fontWeight: 700, margin: '0.5rem 0 0.25rem 0', color: 'var(--text-primary)' }}>1,482 vector rows</p>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Latency: 12ms</span>
                      </div>
                      <div className="glass-card" style={{ padding: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Redis Session Cache</span>
                          <span className="mockup-dot green"></span>
                        </div>
                        <p style={{ fontSize: '1.2rem', fontWeight: 700, margin: '0.5rem 0 0.25rem 0', color: 'var(--text-primary)' }}>12 Active Sessions</p>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Memory Usage: 4.8MB</span>
                      </div>
                      <div className="glass-card" style={{ padding: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Browser Nodes</span>
                          <span className="mockup-dot green"></span>
                        </div>
                        <p style={{ fontSize: '1.2rem', fontWeight: 700, margin: '0.5rem 0 0.25rem 0', color: 'var(--text-primary)' }}>1 Container Active</p>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Chrome headless idle</span>
                      </div>
                    </div>

                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">system_monitor_daemon.log</span>
                      </div>
                      <div className="mockup-content">
                        <div className="terminal-line"><span className="terminal-prompt">[INFO]</span> 16:10:02 Redis reporting active connection.</div>
                        <div className="terminal-line"><span className="terminal-prompt">[INFO]</span> 16:10:04 pgvector similarity indices loaded (1536 dims & 768 dims).</div>
                        <div className="terminal-line"><span className="terminal-prompt">[INFO]</span> 16:11:30 Scheduled memory curation check: evaluated 14 turns, promoted 2 candidates.</div>
                        <div className="terminal-line"><span className="terminal-prompt">[INFO]</span> 16:14:15 Browserless docker container health check successful.</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. Agent Chat View */}
                {activeFeature === 'chat' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Agent Chat Simulator</h3>
                        <p className="viewport-description">Simulated conversation thread showing the internal tool invocation log overlay.</p>
                      </div>
                    </div>

                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">Session: chat_session_82f1b</span>
                      </div>
                      <div className="mockup-content" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                        <div className="mockup-chat">
                          <div className="chat-bubble user">
                            What is the latest status of our website development, and did we finish the database backups?
                          </div>
                          
                          <div className="chat-tool-trigger">
                            <Brain size={12} />
                            <span>Memory Retrieval: "website development status" -&gt; Found 2 core facts</span>
                          </div>

                          <div className="chat-tool-trigger">
                            <Terminal size={12} />
                            <span>Shell Exec: "python scripts/backup_check.py" -&gt; "SUCCESS"</span>
                          </div>

                          <div className="chat-bubble agent">
                            Based on your core memories, we initialized the React site structure on June 27th, 2026. 
                            I also executed the backup script diagnostics; it confirmed that the database backups completed successfully with no relational database errors reported.
                          </div>

                          <div className="chat-thinking">
                            <div className="chat-thinking-dot"></div>
                            <div className="chat-thinking-dot"></div>
                            <div className="chat-thinking-dot"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. Cognitive Memory View */}
                {activeFeature === 'memory' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Cognitive Curation Queue</h3>
                        <p className="viewport-description">Evaluated chat facts awaiting user review before embedding insertion.</p>
                      </div>
                    </div>

                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">PostgreSQL memory_candidates table</span>
                      </div>
                      <table className="architecture-table" style={{ background: 'none' }}>
                        <thead>
                          <tr>
                            <th>Fact Segment</th>
                            <th>Importance Score</th>
                            <th>Status</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>User prefers dark mode layouts on documentation hubs.</td>
                            <td><span style={{ color: '#10b981', fontWeight: 600 }}>0.85</span></td>
                            <td><span style={{ color: '#f59e0b', fontWeight: 600 }}>Pending</span></td>
                            <td>
                              <button className="integration-badge tool" style={{ border: 'none', cursor: 'pointer', marginRight: '5px' }}>Approve</button>
                              <button className="integration-badge llm" style={{ border: 'none', cursor: 'pointer', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>Reject</button>
                            </td>
                          </tr>
                          <tr>
                            <td>Website domain for deployment is set to ampai.itsupport.com.bd.</td>
                            <td><span style={{ color: '#10b981', fontWeight: 600 }}>0.92</span></td>
                            <td><span style={{ color: '#10b981', fontWeight: 600 }}>Approved</span></td>
                            <td><span style={{ color: 'var(--text-tertiary)' }}>Indexed</span></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* 4. Task Board View */}
                {activeFeature === 'taskboard' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Agent Task Board</h3>
                        <p className="viewport-description">Kanban board displaying work units scheduled and automated by the AI agent.</p>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                      <div className="glass-card" style={{ padding: '1rem', background: 'rgba(var(--bg-tertiary), 0.2)' }}>
                        <h4 style={{ fontSize: '0.9rem', color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>BACKLOG</h4>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', border: '1px solid var(--border-color)', marginBottom: '0.5rem' }}>
                          Implement CLI test mockups
                        </div>
                      </div>
                      <div className="glass-card" style={{ padding: '1rem', background: 'rgba(var(--bg-tertiary), 0.2)' }}>
                        <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-primary)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>IN PROGRESS</h4>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', border: '1px solid var(--accent-primary)', marginBottom: '0.5rem' }}>
                          Build ampai-web frontend templates
                        </div>
                      </div>
                      <div className="glass-card" style={{ padding: '1rem', background: 'rgba(var(--bg-tertiary), 0.2)' }}>
                        <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-success)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>COMPLETED</h4>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', border: '1px solid var(--border-color)', textDecoration: 'line-through', opacity: 0.6 }}>
                          Initialize git repository configurations
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 5. Web Automation View */}
                {activeFeature === 'automation' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Web Scraping Node</h3>
                        <p className="viewport-description">Simulated execution of the browserless chromium automation container crawling pages.</p>
                      </div>
                    </div>

                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">Scraper Console: browserless_node</span>
                      </div>
                      <div className="mockup-content">
                        <div className="terminal-line"><span className="terminal-prompt">crawler:</span> Initializing chrome browserless launcher context...</div>
                        <div className="terminal-line"><span className="terminal-prompt">crawler:</span> Navigating to URL: <span style={{ color: 'var(--accent-secondary)' }}>https://itsupport.com.bd</span></div>
                        <div className="terminal-line"><span className="terminal-prompt">crawler:</span> Page loaded successfully (HTTP 200). Content-Length: 42104 bytes.</div>
                        <div className="terminal-line"><span className="terminal-prompt">crawler:</span> Extracted text: "IT Support BD — Reliable Software & Security Integrators..."</div>
                        <div className="terminal-line"><span className="terminal-prompt">crawler:</span> Closing browser headless session. Execution time: 1420ms.</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 6. Shell Terminal View */}
                {activeFeature === 'terminal' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Secure Shell Terminal</h3>
                        <p className="viewport-description">Simulated console illustrating permitted commands executing vs blocked destructive patterns.</p>
                      </div>
                    </div>

                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">powershell (sandboxed)</span>
                      </div>
                      <div className="mockup-content">
                        <div className="terminal-line"><span className="terminal-prompt">PS C:\ampai&gt;</span> ping -n 2 127.0.0.1</div>
                        <div className="terminal-line className=terminal-output">Pinging 127.0.0.1 with 32 bytes of data:</div>
                        <div className="terminal-line className=terminal-output">Reply from 127.0.0.1: bytes=32 time&lt;1ms TTL=128</div>
                        <div className="terminal-line className=terminal-output">Ping statistics: Packets: Sent = 2, Received = 2, Lost = 0</div>
                        <div className="terminal-line"><span className="terminal-prompt">PS C:\ampai&gt;</span> rm -rf /</div>
                        <div className="terminal-line terminal-danger">Command blocked: Matches dangerous pattern: "rm -rf /" (Recursive root deletion policy).</div>
                        <div className="terminal-line"><span className="terminal-prompt">PS C:\ampai&gt;</span> <span className="chat-thinking-dot" style={{ display: 'inline-block', width: '8px', height: '8px', animation: 'bounceDot 1s infinite' }}></span></div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 7. AI Models & Personas View */}
                {activeFeature === 'models' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>AI Model Providers</h3>
                        <p className="viewport-description">Configure the primary LLM engines powering the cognitive synthesis layer.</p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--accent-primary)' }}>
                        <div>
                          <h4 style={{ fontSize: '0.95rem' }}>Ollama Local Model (Offline)</h4>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Host: http://host.docker.internal:11434</span>
                        </div>
                        <span className="integration-badge llm">llama3.2:3b (Active)</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <div>
                          <h4 style={{ fontSize: '0.95rem' }}>Google Gemini Pro API</h4>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Connected via secure API keys</span>
                        </div>
                        <span className="integration-badge tool">Ready</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <div>
                          <h4 style={{ fontSize: '0.95rem' }}>OpenAI GPT-4o Engine</h4>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Cloud API integration ready</span>
                        </div>
                        <span className="integration-badge tool">Ready</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 8. My Profile View */}
                {activeFeature === 'profile' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>My Account Profile</h3>
                        <p className="viewport-description">Manage personal API secrets, secure keys, and individual memory isolation scopes.</p>
                      </div>
                    </div>
                    <div className="glass-card" style={{ padding: '1.25rem' }}>
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
                        <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', color: '#070a13' }}>AM</div>
                        <div>
                          <h4 style={{ fontSize: '1.1rem' }}>Arif Mahmud</h4>
                          <span style={{ fontSize: '0.8rem', color: 'var(--accent-primary)' }}>Superadmin Account</span>
                        </div>
                      </div>
                      <p style={{ fontSize: '0.85rem' }}>Email Scope: <code>superadmin@ampai.local</code></p>
                    </div>
                  </div>
                )}

                {/* 9. System Config View */}
                {activeFeature === 'config' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Global System Settings</h3>
                        <p className="viewport-description">Modify memory size parameters, execution timeouts, and general search settings.</p>
                      </div>
                    </div>
                    <div className="mockup-container">
                      <div className="mockup-header-bar">
                        <span className="mockup-dot red"></span>
                        <span className="mockup-dot yellow"></span>
                        <span className="mockup-dot green"></span>
                        <span className="mockup-title">fastapi_config.json</span>
                      </div>
                      <div className="mockup-content">
                        <div className="terminal-line">&#123;</div>
                        <div className="terminal-line">  <span style={{ color: 'var(--accent-secondary)' }}>"memory_mode"</span>: "indexed",</div>
                        <div className="terminal-line">  <span style={{ color: 'var(--accent-secondary)' }}>"memory_top_k"</span>: 5,</div>
                        <div className="terminal-line">  <span style={{ color: 'var(--accent-secondary)' }}>"memory_context_char_budget"</span>: 1200,</div>
                        <div className="terminal-line">  <span style={{ color: 'var(--accent-secondary)' }}>"terminal_require_confirmation"</span>: true,</div>
                        <div className="terminal-line">  <span style={{ color: 'var(--accent-secondary)' }}>"terminal_timeout_seconds"</span>: 30</div>
                        <div className="terminal-line">&#125;</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 10. Admin Console View */}
                {activeFeature === 'admin' && (
                  <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="viewport-header">
                      <div className="viewport-header-title">
                        <h3>Admin Management Console</h3>
                        <p className="viewport-description">Rebuild core indexes, clear caches, and configure path policies.</p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                      <button className="btn-secondary" style={{ padding: '0.65rem 1rem', fontSize: '0.85rem' }}>Rebuild pgvector Indexes</button>
                      <button className="btn-secondary" style={{ padding: '0.65rem 1rem', fontSize: '0.85rem' }}>Flush Redis Conversation Caches</button>
                      <button className="btn-secondary" style={{ padding: '0.65rem 1rem', fontSize: '0.85rem', color: 'var(--accent-danger)', borderColor: 'var(--accent-danger)' }}>Prune ChromaDB Files</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* ==================== INSTALLATION TAB ==================== */}
        {activeTab === 'installation' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Deployment Guide</span>
              <h2 className="section-title">Installing AmpAI</h2>
              <p className="section-subtitle">
                Deploy AmpAI to your local server or cloud hosting node. Select your preferred pipeline environment option below.
              </p>
            </div>

            <div className="glass-card" style={{ maxWidth: '850px', margin: '0 auto' }}>
              <h3>Docker Compose Quickstart (Recommended)</h3>
              <p style={{ marginBottom: '1rem' }}>
                Deploy the complete environment with relational databases, ChromaDB vector nodes, and Redis caches in a single script run.
              </p>
              
              <CodeBlock 
                id="cmd-docker-clone"
                language="bash"
                code={`# Clone the repository and navigate into it
git clone https://github.com/pranto48/ampai.git
cd ampai

# Run the unified installation script
chmod +x install.sh
./install.sh`}
              />
              
              <p style={{ marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                * The installer generates random secure credentials, configures network bridges, databases, and seeds the superuser account.
              </p>
            </div>

            <div className="glass-card" style={{ maxWidth: '850px', margin: '2rem auto 0 auto' }}>
              <h3>Manual Python Setup (Requires Python 3.11+)</h3>
              <p style={{ marginBottom: '1rem' }}>If you run database engines outside Docker clusters, setup the FastAPIs directly:</p>
              
              <CodeBlock 
                id="cmd-python-install"
                language="bash"
                code={`# 1. Duplicate environment vars template
cp .env.example .env

# 2. Configure critical parameters inside .env file
# (e.g. databases passwords, Ollama or OpenAI credentials)

# 3. Install core python module requirements
pip install -r requirements.txt

# 4. Trigger test suites
pytest tests/ -v

# 5. Boot backend server
uvicorn main:app --host 0.0.0.0 --port 8000`}
              />
            </div>
          </section>
        )}

        {/* ==================== GETTING STARTED TAB ==================== */}
        {activeTab === 'getting-started' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Initial Setup</span>
              <h2 className="section-title">Getting Started</h2>
              <p className="section-subtitle">
                After installation, configure the parameters inside the <code>.env</code> file, set up local Ollama models, and seed credentials.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', maxWidth: '850px', margin: '0 auto' }}>
              <div className="glass-card">
                <h3>1. Edit Environment Variables</h3>
                <p style={{ marginBottom: '1rem' }}>Open the generated <code>.env</code> file and update these core variables:</p>
                <CodeBlock 
                  id="env-vars-sample"
                  language="ini"
                  code={`# Database Connection Passwords
POSTGRES_PASSWORD=your_secure_db_password

# JWT Signing Secret (Generate using: openssl rand -hex 32)
JWT_SECRET=8f45a0b73c4d9e210a5b6c8f9d0e1b2c3a4d5e6f7a8b9c0d1e2f3a4b5c6d7e8

# Default Admin User Credentials
DEFAULT_ADMIN_EMAIL=admin@ampai.local
DEFAULT_ADMIN_PASSWORD=super_secure_password_101

# Actuator Terminal Switch
TERMINAL_TOOLS_ENABLED=true
TERMINAL_REQUIRE_CONFIRMATION=true`}
                />
              </div>

              <div className="glass-card">
                <h3>2. Setup Local Models (Ollama)</h3>
                <p style={{ marginBottom: '1rem' }}>For a fully offline environment, run Ollama and fetch the default inference models:</p>
                <CodeBlock 
                  id="ollama-cmds"
                  language="bash"
                  code={`# Fetch Llama text generation model
ollama pull llama3.2

# Fetch text embedding model (768-dims vector)
ollama pull nomic-embed-text`}
                />
                <p style={{ marginTop: '0.75rem', fontSize: '0.85rem' }}>
                  AmpAI automatically resolves local Ollama links pointing to host gateways on port <code>11434</code>.
                </p>
              </div>

              <div className="glass-card">
                <h3>3. Seeding Admin & Accessing UI</h3>
                <p>
                  When <code>ampai-server</code> boots up, it automatically seeds the initial account parameters matching <code>DEFAULT_ADMIN_EMAIL</code>. 
                  Open your browser and navigate to <strong>http://localhost:8080</strong> to login to the workspace dashboard using these values.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* ==================== INTEGRATIONS TAB ==================== */}
        {activeTab === 'integrations' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Connectivity Matrix</span>
              <h2 className="section-title">Supported Integrations</h2>
              <p className="section-subtitle">
                AmpAI is designed to hook into multiple AI model providers, databases, web scraping nodes, and external messengers.
              </p>
            </div>

            <div className="integrations-matrix">
              <div className="integration-card">
                <div className="integration-icon"><Cpu size={24} /></div>
                <h4>Ollama Models</h4>
                <span className="integration-badge llm">Local LLMs</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Cpu size={24} /></div>
                <h4>Google Gemini</h4>
                <span className="integration-badge llm">Cloud API</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Cpu size={24} /></div>
                <h4>OpenAI GPT-4o</h4>
                <span className="integration-badge llm">Cloud API</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Cpu size={24} /></div>
                <h4>Anthropic Claude</h4>
                <span className="integration-badge llm">Cloud API</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Database size={24} /></div>
                <h4>pgvector</h4>
                <span className="integration-badge db">Semantic DB</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Database size={24} /></div>
                <h4>Redis 7</h4>
                <span className="integration-badge db">Session Cache</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Database size={24} /></div>
                <h4>ChromaDB</h4>
                <span className="integration-badge db">Doc Embeddings</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><Globe size={24} /></div>
                <h4>Browserless</h4>
                <span className="integration-badge tool">Headless Chrome</span>
              </div>
              <div className="integration-card">
                <div className="integration-icon"><MessageSquare size={24} /></div>
                <h4>Telegram Bot</h4>
                <span className="integration-badge tool">Webhook Interface</span>
              </div>
            </div>
          </section>
        )}

        {/* ==================== ADVANCED TAB ==================== */}
        {activeTab === 'advanced' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">For Developers</span>
              <h2 className="section-title">Advanced Configurations</h2>
              <p className="section-subtitle">
                Extend tool layers, declare custom allowlist filters, and audit terminal scripts.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', maxWidth: '850px', margin: '0 auto' }}>
              <div className="glass-card">
                <h3>Terminal Command Policies</h3>
                <p style={{ marginBottom: '1rem' }}>
                  Administrators can declare path limits and command filters by editing the policy configurations:
                </p>
                <CodeBlock 
                  id="policy-json-update"
                  language="json"
                  code={`// PATCH /api/terminal/policy
{
  "command_allowlist": ["git", "npm", "python", "pip", "node"],
  "command_denylist": ["curl", "wget", "ssh"],
  "allowed_folders": ["/home/user/projects", "/opt/app"]
}`}
                />
                <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                  * Permitted folders restrict absolute script references. Attempts to execute commands outside these folders are blocked immediately.
                </p>
              </div>

              <div className="glass-card">
                <h3>Creating Custom Tools</h3>
                <p style={{ marginBottom: '1rem' }}>You can extend the actuator system by writing new Python tools. Example structure:</p>
                <CodeBlock 
                  id="python-custom-tool"
                  language="python"
                  code={`# core/tools/custom_tool.py
from typing import Dict

def run_custom_tool(param: str) -> Dict[str, any]:
    """
    Executes developer defined tasks. Registered automatically by main.py
    """
    try:
        # Perform custom queries or script runs
        return {"status": "success", "result": f"Processed {param}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}`}
                />
              </div>
            </div>
          </section>
        )}

        {/* ==================== REFERENCES TAB ==================== */}
        {activeTab === 'references' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Syntax & Dictionary</span>
              <h2 className="section-title">References</h2>
              <p className="section-subtitle">
                Quick dictionary mapping env configs and relational table models.
              </p>
            </div>

            <div className="glass-card" style={{ maxWidth: '850px', margin: '0 auto' }}>
              <h3>Environment Variable Keys</h3>
              <table className="architecture-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>Default</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code>JWT_SECRET</code></td>
                    <td>—</td>
                    <td>Secret key used to encrypt and sign JWT credentials.</td>
                  </tr>
                  <tr>
                    <td><code>POSTGRES_PASSWORD</code></td>
                    <td>—</td>
                    <td>Master password for user databases.</td>
                  </tr>
                  <tr>
                    <td><code>TERMINAL_TOOLS_ENABLED</code></td>
                    <td><code>false</code></td>
                    <td>Master switch for enabling CMD/Powershell actions.</td>
                  </tr>
                  <tr>
                    <td><code>TERMINAL_REQUIRE_CONFIRMATION</code></td>
                    <td><code>true</code></td>
                    <td>Forces per-session validation before script executions.</td>
                  </tr>
                  <tr>
                    <td><code>MEMORY_TOP_K</code></td>
                    <td><code>5</code></td>
                    <td>Max vectors returned per semantic recall query.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* ==================== NEWS TAB ==================== */}
        {activeTab === 'news' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Updates Log</span>
              <h2 className="section-title">News & Roadmap</h2>
              <p className="section-subtitle">
                Stay updated with the development progress and releases compiled by IT Support BD and Arif Mahmud.
              </p>
            </div>

            <div className="timeline">
              <div className="timeline-item">
                <div className="timeline-dot"></div>
                <div className="timeline-date">June 2026</div>
                <div className="timeline-card">
                  <h4>v1.0.0 Initial Release</h4>
                  <p>
                    Launched AmpAI cognitive core services including FastAPI backend, Redis session caching, and PostgreSQL pgvector data nodes.
                  </p>
                </div>
              </div>

              <div className="timeline-item">
                <div className="timeline-dot"></div>
                <div className="timeline-date">July 2026</div>
                <div className="timeline-card">
                  <h4>Security Policies Patch</h4>
                  <p>
                    Upgraded terminal shell safety mechanics. Introduced block rules preventing regedit, disk formatting, and absolute path escapes.
                  </p>
                </div>
              </div>

              <div className="timeline-item">
                <div className="timeline-dot"></div>
                <div className="timeline-date">Q3 2026 (Roadmap)</div>
                <div className="timeline-card">
                  <h4>Multi-Agent Collaboration</h4>
                  <p>
                    Engineering cross-agent subtask dispatchers enabling separate local instances to partition tasks automatically.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ==================== FAQ TAB ==================== */}
        {activeTab === 'faq' && (
          <section className="fade-in">
            <div className="section-header">
              <span className="section-tag">Troubleshooting</span>
              <h2 className="section-title">Frequently Asked Questions</h2>
              <p className="section-subtitle">
                Find answers to common questions about deployment, databases, and LLM providers.
              </p>
            </div>

            <div className="faq-list" style={{ maxWidth: '800px', margin: '2rem auto 0 auto' }}>
              <div className={`faq-item ${openFaq === 0 ? 'open' : ''}`}>
                <button className="faq-question-btn" onClick={() => toggleFaq(0)}>
                  How does local memory differ from standard context windows?
                  <ChevronDown size={18} className="faq-chevron" />
                </button>
                <div className="faq-answer">
                  <p>
                    Standard LLM conversations forget past facts once the context limit is exceeded. AmpAI extracts facts, calculates importance scores, and saves them permanently in pgvector database tables. It retrieves them dynamically during search triggers.
                  </p>
                </div>
              </div>

              <div className={`faq-item ${openFaq === 1 ? 'open' : ''}`}>
                <button className="faq-question-btn" onClick={() => toggleFaq(1)}>
                  Can I run AmpAI completely offline?
                  <ChevronDown size={18} className="faq-chevron" />
                </button>
                <div className="faq-answer">
                  <p>
                    Yes. By running a local instance of Ollama (with models like llama3.2 and nomic-embed-text) and deployment via Docker Compose, no data ever leaves your server.
                  </p>
                </div>
              </div>

              <div className={`faq-item ${openFaq === 2 ? 'open' : ''}`}>
                <button className="faq-question-btn" onClick={() => toggleFaq(2)}>
                  What security guardrails protect my system?
                  <ChevronDown size={18} className="faq-chevron" />
                </button>
                <div className="faq-answer">
                  <p>
                    We implement regex checking against destructive commands (such as formatting or recursive deletes), allowlist filters restricting execution to designated projects directories, and optional per-session confirmation keys.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

      </main>

      {/* Footer Section */}
      <footer className="app-footer">
        <div className="footer-inner">
          <div className="footer-credits">
            &copy; {new Date().getFullYear()} <span className="footer-brand">AmpAI</span>. Created by <a href="https://itsupport.com.bd" target="_blank" rel="noopener noreferrer">IT Support BD</a> &amp; Arif Mahmud.
          </div>
          <div className="footer-links">
            <button className="footer-link" style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('overview')}>Overview</button>
            <button className="footer-link" style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('features')}>Features</button>
            <button className="footer-link" style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setActiveTab('installation')}>Installation</button>
            <a href="https://github.com/pranto48/ampai" target="_blank" rel="noopener noreferrer" className="footer-link">Source Repository</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
