import "./styles.css";
import { api, ApiError } from "./api";
import type { Chat, KnowledgeDocument, Message, Session } from "./types";

const root = document.querySelector<HTMLDivElement>("#app");
if (!root) throw new Error("App root not found");

const SESSION_KEY = "parallax.session";
const iconPaths: Record<string, string> = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  panel: '<rect width="18" height="16" x="3" y="4" rx="2"/><path d="M9 4v16"/>',
  file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>',
  upload:
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  logout:
    '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  spark: '<path d="m12 3-1.5 5.5L5 10l5.5 1.5L12 17l1.5-5.5L19 10l-5.5-1.5Z"/>',
  arrow: '<path d="m9 18 6-6-6-6"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
};

function icon(name: string, size = 18): string {
  return `<svg aria-hidden="true" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${iconPaths[name]}</svg>`;
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>'"]/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      })[char] ?? char,
  );
}

function renderMarkdown(value: string): string {
  const blocks = escapeHtml(value).split(/```/);
  return blocks
    .map((block, index) => {
      if (index % 2) {
        const cleaned = block.replace(/^[\w.+-]+\n/, "");
        return `<pre><code>${cleaned.trim()}</code></pre>`;
      }
      return block
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/^### (.+)$/gm, "<h3>$1</h3>")
        .replace(/^## (.+)$/gm, "<h2>$1</h2>")
        .replace(/^# (.+)$/gm, "<h1>$1</h1>")
        .replace(/^- (.+)$/gm, "<li>$1</li>")
        .replace(/(?:<li>.*<\/li>\n?)+/g, "<ul>$&</ul>")
        .replace(/\n{2,}/g, "</p><p>")
        .replace(/\n/g, "<br>");
    })
    .join("");
}

function formatDate(value?: string): string {
  if (!value) return "Now";
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function initials(value: string): string {
  return (
    value
      .split(/\s|@/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "PX"
  );
}

function sessionFromStorage(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_KEY);
    return value ? (JSON.parse(value) as Session) : null;
  } catch {
    return null;
  }
}

const state: {
  session: Session | null;
  chats: Chat[];
  activeChat: Chat | null;
  messages: Message[];
  documents: KnowledgeDocument[];
  searching: string;
  busy: boolean;
  abortController: AbortController | null;
  pollingId: number | null;
} = {
  session: sessionFromStorage(),
  chats: [],
  activeChat: null,
  messages: [],
  documents: [],
  searching: "",
  busy: false,
  abortController: null,
  pollingId: null,
};

function toast(message: string, tone: "default" | "error" = "default"): void {
  const region = document.querySelector("#toast-region") ?? document.body;
  const node = document.createElement("div");
  node.className = `toast ${tone === "error" ? "toast-error" : ""}`;
  node.innerHTML = `${tone === "error" ? icon("alert", 16) : icon("check", 16)}<span>${escapeHtml(message)}</span>`;
  region.append(node);
  window.setTimeout(() => node.classList.add("toast-visible"), 20);
  window.setTimeout(() => {
    node.classList.remove("toast-visible");
    window.setTimeout(() => node.remove(), 250);
  }, 3600);
}

function authView(): string {
  return `
    <main class="auth-shell">
      <section class="auth-art" aria-label="Parallax introduction">
        <div class="brand brand-light"><span class="brand-mark">P<span>·</span></span><span>PARALLAX</span></div>
        <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
        <div class="auth-statement">
          <span class="eyebrow">ENTERPRISE KNOWLEDGE / 01</span>
          <h1>Your documents,<br><em>in conversation.</em></h1>
          <p>Ask difficult questions. Get precise answers grounded in the context that matters.</p>
        </div>
        <div class="signal-card signal-card-one"><span class="signal-dot"></span><span>Retrieval layer</span><b>ONLINE</b></div>
        <div class="signal-card signal-card-two"><span>${icon("spark", 17)}</span><p>Context assembled<br><b>12 relevant passages</b></p></div>
        <div class="auth-foot">PRIVATE BY DESIGN <span></span> BUILT FOR DEEP WORK</div>
      </section>
      <section class="auth-panel">
        <div class="mobile-brand brand"><span class="brand-mark">P<span>·</span></span><span>PARALLAX</span></div>
        <div class="auth-card">
          <div class="auth-heading">
            <span class="section-index">ACCESS / 01</span>
            <h2>Enter your workspace</h2>
            <p>Continue where your research left off.</p>
          </div>
          <div class="auth-tabs" role="tablist">
            <button class="auth-tab active" type="button" data-auth-tab="login">Sign in</button>
            <button class="auth-tab" type="button" data-auth-tab="signup">Create account</button>
          </div>
          <form id="login-form" class="auth-form">
            <label>Email address<input name="email" type="email" autocomplete="email" placeholder="you@company.com" required></label>
            <label>Password<input name="password" type="password" autocomplete="current-password" placeholder="••••••••" minlength="6" required></label>
            <button class="primary-button" type="submit"><span>Enter workspace</span>${icon("arrow")}</button>
          </form>
          <form id="signup-form" class="auth-form hidden">
            <label>Your name<input name="name" type="text" autocomplete="name" placeholder="Ada Lovelace" required></label>
            <label>Email address<input name="email" type="email" autocomplete="email" placeholder="you@company.com" required></label>
            <label>Password<input name="password" type="password" autocomplete="new-password" placeholder="At least 6 characters" minlength="6" required></label>
            <button class="primary-button" type="submit"><span>Create workspace</span>${icon("arrow")}</button>
          </form>
          <p id="auth-error" class="form-error" role="alert"></p>
          <p class="terms">By continuing, you agree to keep your organization's data use compliant with its policies.</p>
        </div>
      </section>
      <div id="toast-region" class="toast-region"></div>
    </main>`;
}

function chatItems(): string {
  const query = state.searching.toLowerCase();
  const filtered = state.chats.filter((chat) =>
    chat.title.toLowerCase().includes(query),
  );
  if (!filtered.length)
    return `<div class="nav-empty">${state.searching ? "No matching threads" : "No threads yet"}</div>`;
  return filtered
    .map(
      (chat) => `
    <button class="chat-item ${chat.id === state.activeChat?.id ? "active" : ""}" data-chat-id="${chat.id}">
      <span class="chat-glyph">${icon("arrow", 14)}</span>
      <span class="chat-copy"><strong>${escapeHtml(chat.title)}</strong><small>${formatDate(chat.created_at)}</small></span>
    </button>`,
    )
    .join("");
}

function documentRows(): string {
  if (!state.activeChat)
    return `<div class="docs-empty">Select a thread to inspect its sources.</div>`;
  if (!state.documents.length)
    return `<div class="docs-empty">${icon("file", 23)}<strong>No sources attached</strong><span>Add a PDF or text file to ground this thread.</span></div>`;
  return state.documents
    .map((doc) => {
      const status = doc.status?.toLowerCase() ?? "pending";
      const statusIcon =
        status === "completed"
          ? "check"
          : status === "failed"
            ? "alert"
            : "clock";
      return `<article class="document-row">
      <div class="file-badge">${doc.title.toLowerCase().endsWith(".pdf") ? "PDF" : "TXT"}</div>
      <div class="document-copy"><strong title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</strong><small>${formatDate(doc.uploaded_at)}</small></div>
      <span class="status status-${status}">${icon(statusIcon, 13)}${escapeHtml(status)}</span>
    </article>`;
    })
    .join("");
}

function emptyConversation(): string {
  return `<section class="conversation-empty">
    <div class="empty-symbol"><span></span>${icon("spark", 30)}</div>
    <span class="eyebrow">A BLANK FIELD</span>
    <h2>What are we<br><em>trying to understand?</em></h2>
    <p>Ask a question across your source material, or begin by adding documents to this thread.</p>
    <div class="prompt-grid">
      <button data-prompt="Summarize the key findings across my documents."><span>01</span>Summarize the key findings</button>
      <button data-prompt="What assumptions or contradictions should I investigate?"><span>02</span>Find contradictions</button>
      <button data-prompt="Create an executive brief using the available evidence."><span>03</span>Draft an executive brief</button>
    </div>
  </section>`;
}

function messageRows(): string {
  if (!state.messages.length) return emptyConversation();
  return `<div class="message-list">${state.messages
    .map((message, index) => {
      const assistant = message.role !== "user";
      return `<article class="message ${assistant ? "message-assistant" : "message-user"}" data-message-index="${index}">
      <div class="message-meta">
        <span class="message-avatar">${assistant ? "P·" : initials(state.session?.name ?? state.session?.email ?? "You")}</span>
        <strong>${assistant ? "PARALLAX" : "YOU"}</strong>
        <time>${formatDate(message.sent_at)}</time>
      </div>
      <div class="message-content ${message.pending ? "is-streaming" : ""} ${message.failed ? "is-failed" : ""}">${assistant ? renderMarkdown(message.content) : escapeHtml(message.content).replace(/\n/g, "<br>")}</div>
      ${assistant && !message.pending && message.content ? `<button class="copy-button" data-copy-index="${index}" aria-label="Copy response">${icon("copy", 15)} Copy</button>` : ""}
    </article>`;
    })
    .join("")}</div>`;
}

function workspaceView(): string {
  const activeTitle = state.activeChat?.title ?? "Knowledge workspace";
  const userName =
    state.session?.name || state.session?.email.split("@")[0] || "Researcher";
  return `
    <main class="workspace">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar-head">
          <div class="brand"><span class="brand-mark">P<span>·</span></span><span>PARALLAX</span></div>
          <button class="icon-button mobile-close" id="close-sidebar" aria-label="Close sidebar">${icon("close")}</button>
        </div>
        <button class="new-chat-button" id="new-chat">${icon("plus", 17)}<span>New thread</span><kbd>N</kbd></button>
        <div class="search-wrap">${icon("search", 16)}<input id="chat-search" value="${escapeHtml(state.searching)}" placeholder="Search threads" aria-label="Search threads"></div>
        <div class="nav-label"><span>THREADS</span><small>${state.chats.length.toString().padStart(2, "0")}</small></div>
        <nav class="chat-list" aria-label="Conversation threads">${chatItems()}</nav>
        <div class="sidebar-profile">
          <div class="profile-avatar">${initials(userName)}</div>
          <div><strong>${escapeHtml(userName)}</strong><small>${escapeHtml(state.session?.email ?? "")}</small></div>
          <button class="icon-button" id="logout" title="Sign out" aria-label="Sign out">${icon("logout", 17)}</button>
        </div>
      </aside>
      <div class="sidebar-scrim" id="sidebar-scrim"></div>

      <section class="chat-stage">
        <header class="topbar">
          <button class="icon-button mobile-menu" id="open-sidebar" aria-label="Open sidebar">${icon("menu")}</button>
          <div class="thread-heading">
            <span class="section-index">THREAD / ${state.activeChat ? String(state.chats.findIndex((c) => c.id === state.activeChat?.id) + 1).padStart(2, "0") : "—"}</span>
            <h1>${escapeHtml(activeTitle)}</h1>
          </div>
          <div class="topbar-actions">
            <span class="private-indicator"><i></i>PRIVATE</span>
            <button class="source-toggle" id="source-toggle">${icon("panel", 17)}<span>Sources</span><b>${state.documents.length}</b></button>
          </div>
        </header>
        <div class="conversation" id="conversation">${messageRows()}</div>
        <footer class="composer-zone">
          <form class="composer" id="message-form">
            <textarea id="message-input" rows="1" maxlength="8000" placeholder="Ask across your knowledge…" ${!state.activeChat || state.busy ? "disabled" : ""}></textarea>
            <div class="composer-foot">
              <div class="composer-context"><span class="pulse-dot"></span>${state.documents.filter((d) => d.status === "completed").length} sources ready</div>
              <span class="keyboard-hint">↵ send &nbsp;·&nbsp; ⇧↵ newline</span>
              <button class="send-button" type="submit" aria-label="Send message" ${!state.activeChat || state.busy ? "disabled" : ""}>${state.busy ? '<span class="loader"></span>' : icon("send", 17)}</button>
            </div>
          </form>
          <p>Parallax can make mistakes. Verify critical details against your source material.</p>
        </footer>
      </section>

      <aside class="sources-panel" id="sources-panel">
        <div class="sources-head"><div><span class="section-index">CONTEXT / ${String(state.documents.length).padStart(2, "0")}</span><h2>Source material</h2></div><button class="icon-button" id="close-sources" aria-label="Close sources">${icon("close")}</button></div>
        <p class="sources-intro">Files in this thread become the evidence layer for every response.</p>
        <label class="upload-zone ${state.activeChat ? "" : "disabled"}" for="file-input">
          ${icon("upload", 21)}<span><strong>Add source</strong><small>PDF or TXT · click to browse</small></span>
          <input id="file-input" type="file" accept=".pdf,.txt,application/pdf,text/plain" ${state.activeChat ? "" : "disabled"}>
        </label>
        <div class="docs-label"><span>FILES</span><button id="refresh-docs" ${!state.activeChat ? "disabled" : ""}>Refresh</button></div>
        <div class="documents-list">${documentRows()}</div>
        <div class="sources-note"><span>${icon("spark", 15)}</span><p><strong>Grounded answers</strong><br>Only completed sources are available for retrieval.</p></div>
      </aside>

      <dialog id="new-chat-dialog" class="new-chat-dialog">
        <form method="dialog" id="new-chat-form">
          <div class="dialog-index">NEW THREAD / 01</div>
          <button class="icon-button dialog-close" value="cancel" aria-label="Cancel">${icon("close")}</button>
          <h2>Name the inquiry</h2>
          <p>A focused title makes your research easier to return to.</p>
          <label>Thread title<input name="title" maxlength="80" placeholder="e.g. Q3 market intelligence" required autofocus></label>
          <div class="dialog-actions"><button value="cancel" class="text-button">Cancel</button><button value="default" class="primary-button" id="create-chat-submit"><span>Create thread</span>${icon("arrow")}</button></div>
        </form>
      </dialog>
      <div id="toast-region" class="toast-region"></div>
    </main>`;
}

function setButtonBusy(form: HTMLFormElement, busy: boolean): void {
  const button = form.querySelector<HTMLButtonElement>("button[type='submit']");
  if (!button) return;
  button.disabled = busy;
  button.classList.toggle("button-busy", busy);
}

function bindAuth(): void {
  document
    .querySelectorAll<HTMLButtonElement>("[data-auth-tab]")
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        document
          .querySelectorAll(".auth-tab")
          .forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        const login = tab.dataset.authTab === "login";
        document
          .querySelector("#login-form")
          ?.classList.toggle("hidden", !login);
        document
          .querySelector("#signup-form")
          ?.classList.toggle("hidden", login);
        const error = document.querySelector("#auth-error");
        if (error) error.textContent = "";
      });
    });

  document
    .querySelector<HTMLFormElement>("#login-form")
    ?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget as HTMLFormElement;
      const data = new FormData(form);
      const email = String(data.get("email") ?? "").trim();
      const error = document.querySelector("#auth-error");
      setButtonBusy(form, true);
      try {
        const result = await api.login(
          email,
          String(data.get("password") ?? ""),
        );
        state.session = { token: result.access_token, email };
        localStorage.setItem(SESSION_KEY, JSON.stringify(state.session));
        await loadWorkspace();
      } catch (reason) {
        if (error)
          error.textContent =
            reason instanceof Error ? reason.message : "Unable to sign in";
      } finally {
        setButtonBusy(form, false);
      }
    });

  document
    .querySelector<HTMLFormElement>("#signup-form")
    ?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget as HTMLFormElement;
      const data = new FormData(form);
      const name = String(data.get("name") ?? "").trim();
      const email = String(data.get("email") ?? "").trim();
      const password = String(data.get("password") ?? "");
      const error = document.querySelector("#auth-error");
      setButtonBusy(form, true);
      try {
        await api.signup(name, email, password);
        const result = await api.login(email, password);
        state.session = { token: result.access_token, email, name };
        localStorage.setItem(SESSION_KEY, JSON.stringify(state.session));
        await loadWorkspace();
      } catch (reason) {
        if (error)
          error.textContent =
            reason instanceof Error
              ? reason.message
              : "Unable to create account";
      } finally {
        setButtonBusy(form, false);
      }
    });
}

function logout(): void {
  state.abortController?.abort();
  if (state.pollingId) window.clearInterval(state.pollingId);
  localStorage.removeItem(SESSION_KEY);
  Object.assign(state, {
    session: null,
    chats: [],
    activeChat: null,
    messages: [],
    documents: [],
    busy: false,
  });
  render();
}

async function selectChat(chatId: string): Promise<void> {
  const chat = state.chats.find((item) => item.id === chatId);
  if (!chat || !state.session || state.busy) return;
  state.activeChat = chat;
  state.messages = [];
  state.documents = [];
  render();
  closeMobileSidebar();
  try {
    const [messages, documents] = await Promise.all([
      api.messages(state.session.token, chat.id),
      api.documents(state.session.token, chat.id),
    ]);
    if (state.activeChat?.id !== chat.id) return;
    state.messages = messages.sort(
      (a, b) =>
        new Date(a.sent_at ?? 0).getTime() - new Date(b.sent_at ?? 0).getTime(),
    );
    state.documents = documents;
    render();
    scrollConversation();
    startDocumentPolling();
  } catch (error) {
    handleApiError(error, "Could not load this thread");
  }
}

function startDocumentPolling(): void {
  if (state.pollingId) window.clearInterval(state.pollingId);
  if (
    !state.documents.some(
      (doc) => doc.status === "pending" || doc.status === "processing",
    )
  )
    return;
  state.pollingId = window.setInterval(
    () => void refreshDocuments(false),
    4000,
  );
}

async function refreshDocuments(showToast = true): Promise<void> {
  if (!state.session || !state.activeChat) return;
  try {
    state.documents = await api.documents(
      state.session.token,
      state.activeChat.id,
    );
    const list = document.querySelector(".documents-list");
    if (list) list.innerHTML = documentRows();
    const count = document.querySelector(".source-toggle b");
    if (count) count.textContent = String(state.documents.length);
    if (showToast) toast("Sources refreshed");
    startDocumentPolling();
  } catch (error) {
    handleApiError(error, "Could not refresh sources");
  }
}

function closeMobileSidebar(): void {
  document.querySelector("#sidebar")?.classList.remove("is-open");
  document.querySelector("#sidebar-scrim")?.classList.remove("is-visible");
}

function scrollConversation(): void {
  window.requestAnimationFrame(() => {
    const conversation = document.querySelector("#conversation");
    if (conversation) conversation.scrollTop = conversation.scrollHeight;
  });
}

async function sendMessage(content: string): Promise<void> {
  if (!state.session || !state.activeChat || state.busy || !content.trim())
    return;
  const chatId = state.activeChat.id;
  state.busy = true;
  state.messages.push({
    content: content.trim(),
    role: "user",
    sent_at: new Date().toISOString(),
  });
  state.messages.push({
    content: "",
    role: "system",
    sent_at: new Date().toISOString(),
    pending: true,
  });
  render();
  scrollConversation();
  const answerIndex = state.messages.length - 1;
  state.abortController = new AbortController();

  try {
    await api.streamMessage(
      state.session.token,
      chatId,
      content.trim(),
      (chunk) => {
        const message = state.messages[answerIndex];
        if (!message) return;
        message.content += chunk;
        const element = document.querySelector<HTMLElement>(
          `[data-message-index="${answerIndex}"] .message-content`,
        );
        if (element) element.textContent = message.content;
        scrollConversation();
      },
      state.abortController.signal,
    );
    const message = state.messages[answerIndex];
    if (message) message.pending = false;
  } catch (error) {
    const message = state.messages[answerIndex];
    if (message) {
      message.pending = false;
      message.failed = true;
      if (!message.content)
        message.content =
          "The response could not be completed. Please try again.";
    }
    handleApiError(error, "The response was interrupted");
  } finally {
    state.busy = false;
    state.abortController = null;
    render();
    scrollConversation();
  }
}

function handleApiError(error: unknown, fallback: string): void {
  if (error instanceof ApiError && error.status === 401) {
    logout();
    return;
  }
  if (error instanceof DOMException && error.name === "AbortError") return;
  toast(error instanceof Error ? error.message : fallback, "error");
}

function bindWorkspace(): void {
  document.querySelector("#logout")?.addEventListener("click", logout);
  document.querySelector("#open-sidebar")?.addEventListener("click", () => {
    document.querySelector("#sidebar")?.classList.add("is-open");
    document.querySelector("#sidebar-scrim")?.classList.add("is-visible");
  });
  document
    .querySelector("#close-sidebar")
    ?.addEventListener("click", closeMobileSidebar);
  document
    .querySelector("#sidebar-scrim")
    ?.addEventListener("click", closeMobileSidebar);
  document
    .querySelector("#source-toggle")
    ?.addEventListener("click", () =>
      document.querySelector("#sources-panel")?.classList.toggle("is-open"),
    );
  document
    .querySelector("#close-sources")
    ?.addEventListener("click", () =>
      document.querySelector("#sources-panel")?.classList.remove("is-open"),
    );

  const dialog = document.querySelector<HTMLDialogElement>("#new-chat-dialog");
  document
    .querySelector("#new-chat")
    ?.addEventListener("click", () => dialog?.showModal());
  document
    .querySelector<HTMLFormElement>("#new-chat-form")
    ?.addEventListener("submit", async (event) => {
      const submitter = (event as SubmitEvent)
        .submitter as HTMLButtonElement | null;
      if (submitter?.value === "cancel") return;
      event.preventDefault();
      if (!state.session) return;
      const form = event.currentTarget as HTMLFormElement;
      const title = String(new FormData(form).get("title") ?? "").trim();
      if (!title) return;
      setButtonBusy(form, true);
      try {
        const result = await api.createChat(state.session.token, title);
        const id = result.message.match(/[0-9a-f]{8}-[0-9a-f-]{27,}/i)?.[0];
        state.chats = await api.chats(state.session.token);
        dialog?.close();
        form.reset();
        const next =
          (id && state.chats.find((chat) => chat.id === id)) ||
          state.chats.find((chat) => chat.title === title) ||
          state.chats[0];
        if (next) await selectChat(next.id);
        toast("Thread created");
      } catch (error) {
        handleApiError(error, "Could not create thread");
      } finally {
        setButtonBusy(form, false);
      }
    });

  document
    .querySelectorAll<HTMLButtonElement>("[data-chat-id]")
    .forEach((button) => {
      button.addEventListener(
        "click",
        () => void selectChat(button.dataset.chatId ?? ""),
      );
    });
  document
    .querySelector<HTMLInputElement>("#chat-search")
    ?.addEventListener("input", (event) => {
      state.searching = (event.target as HTMLInputElement).value;
      const list = document.querySelector(".chat-list");
      if (list) list.innerHTML = chatItems();
      list
        ?.querySelectorAll<HTMLButtonElement>("[data-chat-id]")
        .forEach((button) => {
          button.addEventListener(
            "click",
            () => void selectChat(button.dataset.chatId ?? ""),
          );
        });
    });

  const textarea =
    document.querySelector<HTMLTextAreaElement>("#message-input");
  textarea?.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  });
  textarea?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      textarea.form?.requestSubmit();
    }
  });
  document
    .querySelector<HTMLFormElement>("#message-form")
    ?.addEventListener("submit", (event) => {
      event.preventDefault();
      const content = textarea?.value ?? "";
      if (textarea) textarea.value = "";
      void sendMessage(content);
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-prompt]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        if (textarea) {
          textarea.value = button.dataset.prompt ?? "";
          textarea.focus();
        }
      });
    });
  document
    .querySelectorAll<HTMLButtonElement>("[data-copy-index]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        const message = state.messages[Number(button.dataset.copyIndex)];
        if (!message) return;
        await navigator.clipboard.writeText(message.content);
        toast("Response copied");
      });
    });

  document
    .querySelector<HTMLInputElement>("#file-input")
    ?.addEventListener("change", async (event) => {
      const input = event.currentTarget as HTMLInputElement;
      const file = input.files?.[0];
      if (!file || !state.session || !state.activeChat) return;
      if (!/\.(pdf|txt)$/i.test(file.name)) {
        toast("Only PDF and TXT files are supported", "error");
        input.value = "";
        return;
      }
      const zone = input.closest(".upload-zone");
      zone?.classList.add("is-uploading");
      try {
        await api.upload(state.session.token, state.activeChat.id, file);
        toast(`${file.name} added to processing queue`);
        await refreshDocuments(false);
      } catch (error) {
        handleApiError(error, "Upload failed");
      } finally {
        zone?.classList.remove("is-uploading");
        input.value = "";
      }
    });
  document
    .querySelector("#refresh-docs")
    ?.addEventListener("click", () => void refreshDocuments());
}

function render(): void {
  root!.innerHTML = state.session ? workspaceView() : authView();
  if (state.session) bindWorkspace();
  else bindAuth();
}

async function loadWorkspace(): Promise<void> {
  if (!state.session) return;
  render();
  try {
    state.chats = (await api.chats(state.session.token)).sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    render();
    if (state.chats[0]) await selectChat(state.chats[0].id);
  } catch (error) {
    handleApiError(error, "Could not load your workspace");
  }
}

document.addEventListener("keydown", (event) => {
  const target = event.target as HTMLElement;
  if (
    event.key.toLowerCase() === "n" &&
    !event.metaKey &&
    !event.ctrlKey &&
    !/input|textarea/i.test(target.tagName) &&
    state.session
  ) {
    document.querySelector<HTMLDialogElement>("#new-chat-dialog")?.showModal();
  }
});

if (state.session) void loadWorkspace();
else render();
