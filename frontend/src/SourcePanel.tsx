import { pdfUrl, type Source } from "./api";
import { CloseIcon, ExternalIcon } from "./icons";

export default function SourcePanel({ source, onClose }: { source: Source; onClose: () => void }) {
  const url = pdfUrl(source);
  return (
    <aside
      data-testid="source-panel"
      className="flex h-full w-[440px] shrink-0 flex-col border-l border-stone-200 bg-white"
    >
      <div className="flex h-[57px] shrink-0 items-center gap-3 border-b border-stone-200 px-4">
        <span className="flex h-5 min-w-5 items-center justify-center rounded-[4px] bg-teal-700 px-1 text-[11.5px] font-semibold tabular-nums text-white">
          {source.n}
        </span>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-[13px] font-semibold text-stone-900" title={source.filename}>
            {source.filename}
          </div>
          <div className="text-[11.5px] tabular-nums text-stone-500">Page {source.page}</div>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 rounded px-2 py-1 text-[12px] font-medium text-stone-600 hover:bg-stone-100 hover:text-stone-900"
        >
          Open PDF <ExternalIcon className="h-3.5 w-3.5" />
        </a>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-stone-500 hover:bg-stone-100 hover:text-stone-900"
          aria-label="Close source"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="thin-scroll max-h-[38%] shrink-0 overflow-y-auto border-b border-stone-200 px-4 py-3.5">
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-500">
          Passage used
        </div>
        <blockquote className="whitespace-pre-line border-l-2 border-teal-700 pl-3 text-[13px] leading-relaxed text-stone-700">
          {source.text}
        </blockquote>
      </div>

      {/* key forces the viewer to reload when the page changes within the same file */}
      <iframe
        key={`${source.document_id}-${source.page}`}
        src={`${url}&toolbar=0&navpanes=0&view=FitH`}
        title={`${source.filename}, page ${source.page}`}
        className="min-h-0 w-full flex-1 bg-stone-100"
      />
    </aside>
  );
}
