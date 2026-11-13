import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, Source } from "./api";
import { SearchOffIcon, SendIcon, Spinner, StopIcon } from "./icons";

type Props = {
  title: string;
  messages: Message[];
  streaming: boolean;
  status: string | null;
  scope: string;
  canAsk: boolean;
  blockedReason: string | null;
  activeSource: Source | null;
  onAsk: (question: string) => void;
  onStop: () => void;
  onSelectSource: (source: Source) => void;
};

const EXAMPLES = [
  "Summarise the key points of each document.",
  "What were the main financial results, and how did they change year over year?",
  "What risks or challenges do the documents mention?",
];

/** Turns "[2]" markers into links the markdown renderer hands back to us as citation buttons. */
const linkCitations = (text: string) => text.replace(/\[(\d+)\]/g, "[$1](#cite-$1)");

function Answer({
  message,
  streaming,
  activeSource,
  onSelectSource,
}: {
  message: Message;
  streaming: boolean;
  activeSource: Source | null;
  onSelectSource: (source: Source) => void;
}) {
  const byNumber = new Map(message.sources.map((s) => [s.n, s]));
  const cited = message.sources.filter((s) => s.cited);
  const notFound = message.answerable === false && !message.error;

  if (message.error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3.5 py-2.5 text-[14px] leading-relaxed text-red-800">
        {message.content}
      </div>
    );
  }

  return (
    <div data-testid="answer">
      {notFound && (
        <div className="mb-2 inline-flex items-center gap-1.5 rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11.5px] font-medium text-amber-800">
          <SearchOffIcon className="h-3 w-3" /> Not found in the documents
        </div>
      )}
      <div className={`answer text-[15px] text-stone-800 ${streaming ? "caret" : ""}`}>
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            a({ href, children }) {
              if (href?.startsWith("#cite-")) {
                const source = byNumber.get(Number(href.slice(6)));
                if (!source) return <span className="text-stone-400">[{children}]</span>;
                const active = activeSource?.chunk_id === source.chunk_id;
                return (
                  <button
                    type="button"
                    data-testid="citation"
                    onClick={() => onSelectSource(source)}
                    title={`${source.filename}, page ${source.page}`}
                    className={`ml-1 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-[4px] border px-1 align-middle text-[11px] font-semibold tabular-nums leading-none transition-colors ${
                      active
                        ? "border-teal-700 bg-teal-700 text-white"
                        : "border-teal-700/30 bg-teal-50 text-teal-800 hover:border-teal-700 hover:bg-teal-100"
                    }`}
                  >
                    {children}
                  </button>
                );
              }
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-teal-800 underline">
                  {children}
                </a>
              );
            },
          }}
        >
          {linkCitations(message.content)}
        </Markdown>
      </div>

      {cited.length > 0 && !streaming && (
        <div className="mt-4 border-t border-stone-200 pt-3" data-testid="sources">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-500">
            Sources
          </div>
          <ol className="space-y-0.5">
            {cited.map((source) => {
              const active = activeSource?.chunk_id === source.chunk_id;
              return (
                <li key={source.chunk_id}>
                  <button
                    type="button"
                    onClick={() => onSelectSource(source)}
                    className={`flex w-full items-baseline gap-2.5 rounded px-1.5 py-1 text-left text-[13px] ${
                      active ? "bg-teal-50" : "hover:bg-stone-100"
                    }`}
                  >
                    <span className="w-4 shrink-0 text-right text-[11.5px] font-semibold tabular-nums text-teal-800">
                      {source.n}
                    </span>
                    <span className="min-w-0 truncate text-stone-700">{source.filename}</span>
                    <span className="shrink-0 tabular-nums text-stone-500">p. {source.page}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function Chat(props: Props) {
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const last = props.messages[props.messages.length - 1];

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [props.messages.length, last?.content, props.status]);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [draft]);

  const submit = (text = draft) => {
    const question = text.trim();
    if (!question || props.streaming || !props.canAsk) return;
    props.onAsk(question);
    setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col">
      <header className="flex h-[57px] shrink-0 items-center justify-between gap-4 border-b border-stone-200 bg-white px-6">
        <h1 className="truncate text-[14px] font-semibold text-stone-900">{props.title}</h1>
        <span className="shrink-0 text-[12px] text-stone-500" data-testid="scope">
          {props.scope}
        </span>
      </header>

      <div ref={scroller} className="thin-scroll flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[760px] px-6 py-8">
          {props.messages.length === 0 ? (
            <div className="pt-[12vh]">
              <h2 className="text-[22px] font-semibold tracking-tight text-stone-900">
                Ask a question about your documents
              </h2>
              <p className="mt-2 max-w-[560px] text-[14.5px] leading-relaxed text-stone-600">
                Answers are written only from the PDFs you upload, and every statement links to the
                page it came from. If the documents do not contain the answer, you will be told so.
              </p>
              {props.canAsk && (
                <div className="mt-7">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-500">
                    Try asking
                  </div>
                  <ul className="divide-y divide-stone-200 border-y border-stone-200">
                    {EXAMPLES.map((example) => (
                      <li key={example}>
                        <button
                          type="button"
                          onClick={() => submit(example)}
                          className="flex w-full items-center justify-between gap-3 px-1 py-2.5 text-left text-[14px] text-stone-700 hover:text-teal-800"
                        >
                          {example}
                          <SendIcon className="h-3.5 w-3.5 shrink-0 text-stone-400" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-8">
              {props.messages.map((message, index) => {
                const isLast = index === props.messages.length - 1;
                if (message.role === "user") {
                  return (
                    <div key={message.id} data-testid="question">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-400">
                        Question
                      </div>
                      <div className="whitespace-pre-wrap text-[17px] font-semibold leading-snug tracking-tight text-stone-900">
                        {message.content}
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={message.id}>
                    {message.rewritten && (
                      <div className="mb-2 text-[12px] text-stone-500" data-testid="rewrite">
                        Understood as: <span className="italic text-stone-600">{message.rewritten}</span>
                      </div>
                    )}
                    {isLast && props.streaming && !message.content ? (
                      <div className="flex items-center gap-2 text-[13.5px] text-stone-500">
                        <Spinner /> {props.status ?? "Working…"}
                      </div>
                    ) : (
                      <Answer
                        message={message}
                        streaming={isLast && props.streaming}
                        activeSource={props.activeSource}
                        onSelectSource={props.onSelectSource}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 border-t border-stone-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-[760px]">
          <div className="flex items-end gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 focus-within:border-stone-500">
            <textarea
              ref={textarea}
              data-testid="question-input"
              rows={1}
              value={draft}
              disabled={!props.canAsk}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={props.blockedReason ?? "Ask a question about the uploaded documents"}
              className="max-h-[180px] flex-1 resize-none bg-transparent py-1 text-[14.5px] leading-relaxed text-stone-900 outline-none placeholder:text-stone-400 disabled:cursor-not-allowed"
            />
            {props.streaming ? (
              <button
                type="button"
                onClick={props.onStop}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-stone-200 text-stone-700 hover:bg-stone-300"
                aria-label="Stop generating"
                title="Stop"
              >
                <StopIcon />
              </button>
            ) : (
              <button
                type="button"
                data-testid="send"
                onClick={() => submit()}
                disabled={!draft.trim() || !props.canAsk}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-stone-900 text-white hover:bg-stone-700 disabled:bg-stone-200 disabled:text-stone-400"
                aria-label="Send question"
                title="Send"
              >
                <SendIcon />
              </button>
            )}
          </div>
          <p className="mt-1.5 text-[11.5px] text-stone-400">
            Enter to send · Shift + Enter for a new line · Follow-up questions keep the context of
            this conversation
          </p>
        </div>
      </div>
    </section>
  );
}
