import { useRef, useState, type DragEvent } from "react";
import type { Conversation, Doc } from "./api";
import { AlertIcon, Logo, PlusIcon, Spinner, TrashIcon, UploadIcon } from "./icons";

type Props = {
  docs: Doc[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onUpload: (files: File[]) => void;
  onDeleteDoc: (doc: Doc) => void;
  uploading: boolean;
  conversations: Conversation[];
  activeConversation: string | null;
  onOpenConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (conversation: Conversation) => void;
  disabled: boolean;
};

const formatSize = (bytes: number) =>
  bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/** "Annual_Report_2024.pdf" -> "Annual Report 2024": readable and able to wrap. */
const displayName = (filename: string) => filename.replace(/\.pdf$/i, "").replace(/_/g, " ");

function SectionTitle({ children, aside }: { children: string; aside?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 pb-2 pt-5">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-500">{children}</h2>
      {aside}
    </div>
  );
}

export default function Sidebar(props: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
    );
    if (files.length) props.onUpload(files);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    if (!props.disabled) pick(event.dataTransfer.files);
  };

  const ready = props.docs.filter((d) => d.status === "ready").length;

  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col border-r border-stone-200 bg-white">
      <div className="flex items-center gap-2.5 border-b border-stone-200 px-4 py-3.5">
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-stone-900">Folio</div>
          <div className="text-[11px] text-stone-500">Document question answering</div>
        </div>
      </div>

      <div className="thin-scroll flex-1 overflow-y-auto">
        <SectionTitle
          aside={
            props.docs.length > 0 ? (
              <span className="text-[11px] tabular-nums text-stone-400">
                {ready} of {props.docs.length} ready
              </span>
            ) : undefined
          }
        >
          Documents
        </SectionTitle>

        <div className="px-3">
          <button
            type="button"
            data-testid="upload-button"
            disabled={props.disabled || props.uploading}
            onClick={() => input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`flex w-full items-center justify-center gap-2 rounded-md border border-dashed px-3 py-3 text-[13px] transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              dragging
                ? "border-teal-700 bg-teal-50 text-teal-800"
                : "border-stone-300 text-stone-600 hover:border-stone-400 hover:bg-stone-50"
            }`}
          >
            {props.uploading ? <Spinner /> : <UploadIcon />}
            {props.uploading ? "Uploading…" : "Upload PDFs or drop them here"}
          </button>
          <input
            ref={input}
            data-testid="file-input"
            type="file"
            accept="application/pdf,.pdf"
            multiple
            hidden
            onChange={(e) => {
              pick(e.target.files);
              e.target.value = "";
            }}
          />
        </div>

        <ul className="mt-2 px-2">
          {props.docs.map((doc) => (
            <li
              key={doc.id}
              data-testid="document-row"
              className="group flex items-start gap-2.5 rounded-md px-2 py-2 hover:bg-stone-50"
            >
              <input
                type="checkbox"
                className="mt-[3px] h-3.5 w-3.5 shrink-0 accent-teal-700 disabled:opacity-40"
                checked={doc.status === "ready" && props.selected.has(doc.id)}
                disabled={doc.status !== "ready"}
                onChange={() => props.onToggle(doc.id)}
                aria-label={`Include ${doc.filename} in search`}
              />
              <div className="min-w-0 flex-1">
                <div
                  className="line-clamp-2 break-words text-[13px] font-medium leading-snug text-stone-800"
                  title={doc.filename}
                >
                  {displayName(doc.filename)}
                </div>
                {doc.status === "ready" && (
                  <div className="mt-0.5 text-[11.5px] tabular-nums text-stone-500">
                    {doc.pages} {doc.pages === 1 ? "page" : "pages"} · {doc.chunks} passages ·{" "}
                    {formatSize(doc.size_bytes)}
                  </div>
                )}
                {doc.status === "processing" && (
                  <div className="flex items-center gap-1.5 text-[11.5px] text-stone-500">
                    <Spinner className="h-3 w-3" /> Reading and indexing…
                  </div>
                )}
                {doc.status === "failed" && (
                  <div className="flex items-start gap-1 text-[11.5px] leading-snug text-red-700">
                    <AlertIcon className="mt-px h-3 w-3 shrink-0" />
                    <span>{doc.error ?? "Processing failed."}</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => props.onDeleteDoc(doc)}
                className="rounded p-1 text-stone-400 opacity-0 hover:bg-stone-200 hover:text-stone-700 focus:opacity-100 group-hover:opacity-100"
                aria-label={`Remove ${doc.filename}`}
                title="Remove document"
              >
                <TrashIcon className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
          {props.docs.length === 0 && (
            <li className="px-2 py-3 text-[12.5px] leading-relaxed text-stone-500">
              No documents yet. Upload annual reports, policies, manuals or any other PDFs to start
              asking questions.
            </li>
          )}
        </ul>

        <SectionTitle
          aside={
            <button
              type="button"
              data-testid="new-chat"
              onClick={props.onNewConversation}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11.5px] font-medium text-stone-600 hover:bg-stone-100 hover:text-stone-900"
            >
              <PlusIcon className="h-3 w-3" /> New
            </button>
          }
        >
          Conversations
        </SectionTitle>

        <ul className="px-2 pb-4">
          {props.conversations.map((conversation) => {
            const active = conversation.id === props.activeConversation;
            return (
              <li key={conversation.id} className="group relative">
                <button
                  type="button"
                  onClick={() => props.onOpenConversation(conversation.id)}
                  className={`w-full truncate rounded-md py-1.5 pl-2.5 pr-8 text-left text-[13px] ${
                    active ? "bg-stone-100 font-medium text-stone-900" : "text-stone-600 hover:bg-stone-50"
                  }`}
                  title={conversation.title}
                >
                  {conversation.title}
                </button>
                <button
                  type="button"
                  onClick={() => props.onDeleteConversation(conversation)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-stone-400 opacity-0 hover:bg-stone-200 hover:text-stone-700 focus:opacity-100 group-hover:opacity-100"
                  aria-label={`Delete conversation ${conversation.title}`}
                  title="Delete conversation"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
          {props.conversations.length === 0 && (
            <li className="px-2 py-2 text-[12.5px] text-stone-500">Your conversations appear here.</li>
          )}
        </ul>
      </div>
    </aside>
  );
}
