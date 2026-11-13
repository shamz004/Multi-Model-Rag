import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, streamChat, type Conversation, type Doc, type Health, type Message, type Source } from "./api";
import Chat from "./Chat";
import { AlertIcon } from "./icons";
import Sidebar from "./Sidebar";
import SourcePanel from "./SourcePanel";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [uploading, setUploading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const refreshDocs = useCallback(() => api.documents().then(setDocs).catch(() => {}), []);
  const refreshConversations = useCallback(
    () => api.conversations().then(setConversations).catch(() => {}),
    [],
  );

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setNotice("Cannot reach the server. Make sure the backend is running."));
    refreshDocs();
    refreshConversations();
  }, [refreshDocs, refreshConversations]);

  // Poll while any document is still being processed.
  const processing = docs.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(refreshDocs, 1200);
    return () => clearInterval(timer);
  }, [processing, refreshDocs]);

  const readyDocs = useMemo(() => docs.filter((d) => d.status === "ready"), [docs]);
  const selected = useMemo(
    () => new Set(readyDocs.filter((d) => !excluded.has(d.id)).map((d) => d.id)),
    [readyDocs, excluded],
  );

  const toggleDoc = (id: string) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const upload = async (files: File[]) => {
    setUploading(true);
    setNotice(null);
    try {
      const results = await api.upload(files);
      const problems = results
        .filter((r) => r.status === "rejected")
        .map((r) => `${r.filename}: ${r.error}`);
      const duplicates = results.filter((r) => r.duplicate).map((r) => r.filename);
      if (duplicates.length) problems.push(`Already uploaded: ${duplicates.join(", ")}`);
      if (problems.length) setNotice(problems.join("  ·  "));
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setUploading(false);
      refreshDocs();
    }
  };

  const deleteDoc = async (doc: Doc) => {
    if (!window.confirm(`Remove "${doc.filename}"? It will no longer be used to answer questions.`)) return;
    await api.deleteDocument(doc.id).catch((error: Error) => setNotice(error.message));
    if (activeSource?.document_id === doc.id) setActiveSource(null);
    refreshDocs();
  };

  const openConversation = async (id: string) => {
    if (streaming) return;
    try {
      const conversation = await api.conversation(id);
      setConversationId(id);
      setMessages(conversation.messages);
      setActiveSource(null);
    } catch (error) {
      setNotice((error as Error).message);
      refreshConversations();
    }
  };

  const newConversation = () => {
    if (streaming) return;
    setConversationId(null);
    setMessages([]);
    setActiveSource(null);
  };

  const deleteConversation = async (conversation: Conversation) => {
    if (!window.confirm(`Delete the conversation "${conversation.title}"?`)) return;
    await api.deleteConversation(conversation.id).catch((error: Error) => setNotice(error.message));
    if (conversation.id === conversationId) newConversation();
    refreshConversations();
  };

  const ask = async (question: string) => {
    const pendingId = `pending-${Date.now()}`;
    const patch = (change: Partial<Message> | ((m: Message) => Partial<Message>)) =>
      setMessages((current) =>
        current.map((m) =>
          m.id === pendingId ? { ...m, ...(typeof change === "function" ? change(m) : change) } : m,
        ),
      );

    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: question, sources: [], answerable: null },
      { id: pendingId, role: "assistant", content: "", sources: [], answerable: null },
    ]);
    setStreaming(true);
    setStatus(messages.length ? "Reading the conversation…" : "Searching the documents…");
    setNotice(null);
    abort.current = new AbortController();

    const everything = selected.size === readyDocs.length;
    try {
      await streamChat(
        {
          question,
          conversation_id: conversationId,
          document_ids: everything ? null : [...selected],
        },
        (event) => {
          if (event.type === "conversation") {
            setConversationId(event.conversation.id);
            setConversations((current) => [
              event.conversation,
              ...current.filter((c) => c.id !== event.conversation.id),
            ]);
          } else if (event.type === "rewrite") {
            patch({ rewritten: event.question });
            setStatus("Searching the documents…");
          } else if (event.type === "sources") {
            patch({ sources: event.sources });
            setStatus("Writing the answer…");
          } else if (event.type === "token") {
            patch((m) => ({ content: m.content + event.text }));
          } else if (event.type === "done") {
            patch((m) => ({ ...event.message, id: pendingId, rewritten: m.rewritten }));
          } else if (event.type === "error") {
            patch({ content: event.message, error: true });
          }
        },
        abort.current.signal,
      );
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        patch((m) => ({ content: m.content || "Stopped.", answerable: null }));
      } else {
        patch({ content: (error as Error).message, error: true });
      }
    } finally {
      setStreaming(false);
      setStatus(null);
      refreshConversations();
    }
  };

  const configured = health?.openai_configured ?? true;
  const blockedReason = !configured
    ? "Add your OpenAI API key to the .env file to start"
    : readyDocs.length === 0
      ? processing
        ? "Your documents are being processed…"
        : "Upload a PDF to start asking questions"
      : selected.size === 0
        ? "Select at least one document to search"
        : null;

  const scope =
    readyDocs.length === 0
      ? "No documents"
      : selected.size === readyDocs.length
        ? `Searching all ${readyDocs.length} ${readyDocs.length === 1 ? "document" : "documents"}`
        : `Searching ${selected.size} of ${readyDocs.length} documents`;

  const title = conversations.find((c) => c.id === conversationId)?.title ?? "New conversation";

  return (
    <div className="flex h-full flex-col">
      {(notice || !configured) && (
        <div className="flex shrink-0 items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-900">
          <AlertIcon className="h-4 w-4 shrink-0" />
          <span className="flex-1">
            {!configured
              ? "OpenAI API key is not configured. Add OPENAI_API_KEY to the .env file in the project folder, then reload this page."
              : notice}
          </span>
          {configured && (
            <button type="button" onClick={() => setNotice(null)} className="font-medium hover:underline">
              Dismiss
            </button>
          )}
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Sidebar
          docs={docs}
          selected={selected}
          onToggle={toggleDoc}
          onUpload={upload}
          onDeleteDoc={deleteDoc}
          uploading={uploading}
          conversations={conversations}
          activeConversation={conversationId}
          onOpenConversation={openConversation}
          onNewConversation={newConversation}
          onDeleteConversation={deleteConversation}
          disabled={!configured}
        />
        <Chat
          title={title}
          messages={messages}
          streaming={streaming}
          status={status}
          scope={scope}
          canAsk={blockedReason === null}
          blockedReason={blockedReason}
          activeSource={activeSource}
          onAsk={ask}
          onStop={() => abort.current?.abort()}
          onSelectSource={setActiveSource}
        />
        {activeSource && <SourcePanel source={activeSource} onClose={() => setActiveSource(null)} />}
      </div>
    </div>
  );
}
