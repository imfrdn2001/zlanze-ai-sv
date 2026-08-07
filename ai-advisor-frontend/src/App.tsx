import {
  ArrowUp,
  Bell,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  LayoutDashboard,
  Menu,
  ShoppingCart,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { sendMessage } from "./lib/api";
import { generateId } from "./lib/id";
import { createSession, loadSessions, saveSessions, titleFromMessage } from "./lib/sessions";
import type { ChatMessage, ChatSession } from "./types";

function withoutTalentList(content: string, hasDevelopers: boolean): string {
  if (!hasDevelopers) return content;
  const start = content.indexOf("Talent matching for:");
  if (start < 0) return content;
  const remainder = content.slice(start);
  const nextSections = [
    "\n\nEstimated marketplace price:",
    "\n\nEstimated delivery time:",
  ];
  const next = nextSections
    .map((marker) => remainder.indexOf(marker))
    .filter((position) => position >= 0)
    .sort((a, b) => a - b)[0];
  return [content.slice(0, start).trim(), next === undefined ? "" : remainder.slice(next).trim()]
    .filter(Boolean)
    .join("\n\n");
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "FL";
}

const prompts = [
  "Who can work with React, and how many matching freelancers are there?",
  "Find UI/UX and graphic designers for a new ecommerce brand.",
  "Help me plan an MVP and estimate the talent, cost, and timeline.",
];

const navigation = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Talent", icon: UserRound },
  { label: "Zlanze AI", icon: Sparkles },
  { label: "Discovery Calls", icon: Bell },
  { label: "Enquiry Cart", icon: ShoppingCart },
];

function App() {
  const initialSessions = loadSessions();
  const archivedSessions = useRef<ChatSession[]>(initialSessions.slice(1));
  const [session, setSession] = useState<ChatSession>(
    initialSessions[0] || createSession(),
  );
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(
    () => saveSessions([
      session,
      ...archivedSessions.current.filter((item) => item.id !== session.id),
    ]),
    [session],
  );
  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [session.messages, sending]);

  async function submit(rawMessage = message) {
    const query = rawMessage.trim();
    if (!query || sending) return;
    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: query,
      createdAt: new Date().toISOString(),
    };
    setSession((current) => ({
      ...current,
      title: current.messages.length ? current.title : titleFromMessage(query),
      updatedAt: userMessage.createdAt,
      messages: [...current.messages, userMessage],
    }));
    setMessage("");
    setSending(true);
    try {
      const result = await sendMessage(session.id, query);
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: result.response,
        createdAt: new Date().toISOString(),
        advisorData: result.data,
      };
      setSession((current) => ({
        ...current,
        updatedAt: assistantMessage.createdAt,
        messages: [...current.messages, assistantMessage],
      }));
    } catch (error) {
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: error instanceof Error
          ? `I couldn't complete that request. ${error.message}`
          : "I couldn't complete that request. Please try again.",
        createdAt: new Date().toISOString(),
      };
      setSession((current) => ({ ...current, messages: [...current.messages, assistantMessage] }));
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function startNewStrategy() {
    if (session.messages.length) {
      archivedSessions.current = [
        session,
        ...archivedSessions.current.filter((item) => item.id !== session.id),
      ];
    }
    setSession(createSession());
    setMessage("");
  }

  return (
    <div className="enterprise-app">
      <aside className={`enterprise-sidebar ${sidebarOpen ? "is-open" : ""} ${collapsed ? "is-collapsed" : ""}`}>
        <div className="enterprise-brand">
          <span><strong>zLanze</strong><small>ENTERPRISE</small></span>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={20} /></button>
        </div>
        <nav className="enterprise-nav" aria-label="Enterprise navigation">
          {navigation.map(({ label, icon: Icon }) => (
            <button key={label} type="button" className={label === "Zlanze AI" ? "active" : ""}>
              <Icon size={19} /><span>{label}</span>{label === "Zlanze AI" && <i />}
            </button>
          ))}
        </nav>
        <button className="collapse-button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <ChevronRight size={17} /> : <><ChevronLeft size={17} /><span>Collapse</span></>}
        </button>
      </aside>

      {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <section className="enterprise-content">
        <header className="enterprise-topbar">
          <button className="menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu size={22} /></button>
          <div className="topbar-actions">
            <button aria-label="Notifications"><Bell size={20} /></button>
            <button aria-label="Help"><CircleHelp size={20} /></button>
            <span className="topbar-divider" />
            <button aria-label="Open enquiry cart"><ShoppingCart size={19} /></button>
            <span className="account-avatar">CT</span>
          </div>
        </header>

        <main className="enterprise-main enterprise-ai-content">
          <section className="enterprise-ai" aria-labelledby="zlanze-ai-heading">
            <div className="enterprise-ai-intro">
              <div>
                <p className="eyebrow">zLanze AI</p>
                <h1 id="zlanze-ai-heading">Your engineering team consultant</h1>
                <p>Describe what you’re building and get a focused hiring strategy for your next team.</p>
              </div>
            </div>

            {session.messages.length === 0 ? (
              <div className="enterprise-ai-empty">
                <div>
                  <h2>What are you building today?</h2>
                  <p>Share your project goals and I’ll recommend the right hiring approach.</p>
                </div>
                <div className="ai-prompt-list" aria-label="Suggested prompts">
                  {prompts.map((prompt) => (
                    <button key={prompt} type="button" onClick={() => setMessage(prompt)}>{prompt}</button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="enterprise-ai-result">
                {session.messages.map((item) => (
                  <article className={`ai-message ai-${item.role}-message`} key={item.id}>
                    {item.role === "assistant" && (
                      <div className="ai-message-heading"><span><Sparkles size={17} /></span><strong>zLanze AI recommendation</strong></div>
                    )}
                    {withoutTalentList(
                      item.content,
                      Boolean(item.advisorData?.developers?.length),
                    ) && (
                      <p>{withoutTalentList(
                        item.content,
                        Boolean(item.advisorData?.developers?.length),
                      )}</p>
                    )}
                    {item.role === "assistant" && Boolean(item.advisorData?.developers?.length) && (
                      <div className="talent-results">
                        <div className="talent-results-heading">
                          <h3>Recommended talent</h3>
                          <span>{item.advisorData?.developers.length} top matches</span>
                        </div>
                        <div className="talent-card-rail" aria-label="Recommended freelancers">
                          {item.advisorData?.developers.map((developer) => (
                            <article className="talent-card" key={developer.user_id}>
                              <div className="talent-identity">
                                <span className="member-avatar">
                                  {developer.profile_picture ? (
                                    <img
                                      src={developer.profile_picture}
                                      alt=""
                                      loading="lazy"
                                      referrerPolicy="no-referrer"
                                      onError={(event) => {
                                        event.currentTarget.style.display = "none";
                                        event.currentTarget.parentElement?.classList.add("image-failed");
                                      }}
                                    />
                                  ) : null}
                                  <b>{initials(developer.display_name)}</b>
                                </span>
                                <div>
                                  <h4>{developer.display_name}</h4>
                                  <p>{developer.current_company || "Marketplace candidate"}</p>
                                </div>
                              </div>
                              <dl>
                                <div><dt>Experience</dt><dd>{developer.experience || "Not provided"}</dd></div>
                                <div><dt>Coverage</dt><dd>{developer.coverage_percent}%</dd></div>
                                <div><dt>Location</dt><dd title={developer.location || ""}>{developer.location || "—"}</dd></div>
                              </dl>
                              {developer.hourly_rate_inr != null && (
                                <div className="talent-price">
                                  <span>Calculated working rate</span>
                                  <strong>₹{developer.hourly_rate_inr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}/hour</strong>
                                  <small>₹{developer.daily_rate_inr?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}/day</small>
                                </div>
                              )}
                              <div className="skill-tags">
                                {developer.matched_tech.map((skill) => <span key={skill}>{skill}</span>)}
                              </div>
                            </article>
                          ))}
                        </div>
                      </div>
                    )}
                  </article>
                ))}
                {sending && <article className="ai-message ai-assistant-message ai-thinking"><span /><span /><span /><em>Reviewing marketplace data</em></article>}
                {!sending && <button type="button" className="text-action ai-reset" onClick={startNewStrategy}>Start a new strategy</button>}
                <div ref={bottomRef} />
              </div>
            )}

            <form className="enterprise-ai-composer" onSubmit={onSubmit}>
              <label htmlFor="ai-project-description">Describe what you’re building</label>
              <div>
                <textarea
                  id="ai-project-description"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="Describe your project, team goals, and timeline..."
                  rows={1}
                  disabled={sending}
                  aria-label="Message the advisor"
                />
                <button type="submit" aria-label="Send message" disabled={sending || !message.trim()}><ArrowUp size={21} /></button>
              </div>
              <p>zLanze AI creates a hiring strategy. Final talent selection happens in Talent Explorer.</p>
            </form>
          </section>
        </main>
      </section>
    </div>
  );
}

export default App;
