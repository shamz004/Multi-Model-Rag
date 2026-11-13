"""Records the product demo video with subtitles.

    pip install playwright imageio-ffmpeg
    python -m playwright install ffmpeg
    python scripts/record_demo.py

What it does:
  1. starts a private copy of the app on its own port with an empty data folder
  2. drives the real web UI in Chrome: upload, questions, citations, follow-ups,
     an unanswerable question, document filtering and conversation history
  3. shows a subtitle for every step (burned into the picture) and also writes
     the same subtitles to demo/demo.srt
  4. converts the recording to demo/demo.mp4

Nothing is mocked: every answer in the video comes from the live OpenAI models.
Requires OPENAI_API_KEY in .env and a built frontend (frontend/dist).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
WIDTH, HEIGHT = 1600, 1000
CAPTION_HEIGHT = 96

OVERLAY = f"""
(() => {{
  const style = document.createElement('style');
  style.textContent = `
    html, body {{ height: 100%; }}
    #root {{ height: calc(100% - {CAPTION_HEIGHT}px) !important; }}
    #demo-caption {{
      position: fixed; left: 0; right: 0; bottom: 0; height: {CAPTION_HEIGHT}px;
      background: #111110; color: #fafaf9; display: flex; align-items: center;
      justify-content: center; text-align: center; padding: 0 80px; z-index: 99999;
      font: 500 23px/1.4 "Segoe UI", system-ui, sans-serif; letter-spacing: 0.1px;
    }}
    #demo-caption span {{ transition: opacity .25s ease; }}
    #demo-cursor {{
      position: fixed; width: 22px; height: 22px; margin: -11px 0 0 -11px; border-radius: 50%;
      background: rgba(15,118,110,.28); border: 2px solid #0f766e; z-index: 99998;
      pointer-events: none; left: -50px; top: -50px;
      transition: left .45s cubic-bezier(.22,.8,.3,1), top .45s cubic-bezier(.22,.8,.3,1), transform .12s;
    }}
    #demo-cursor.down {{ transform: scale(.7); background: rgba(15,118,110,.55); }}
  `;
  document.head.appendChild(style);
  const caption = document.createElement('div');
  caption.id = 'demo-caption';
  caption.innerHTML = '<span></span>';
  document.body.appendChild(caption);
  const cursor = document.createElement('div');
  cursor.id = 'demo-cursor';
  document.body.appendChild(cursor);
}})();
"""


class Director:
    """Small helpers that make the automated session watchable."""

    def __init__(self, page: Page, started: float):
        self.page = page
        self.started = started  # when the video recording began
        self.cues: list[tuple[float, str]] = []

    def caption(self, text: str, hold: float = 0.0) -> None:
        self.cues.append((time.time() - self.started, text))
        self.page.evaluate(
            """(text) => {
                const span = document.querySelector('#demo-caption span');
                span.style.opacity = 0;
                setTimeout(() => { span.textContent = text; span.style.opacity = 1; }, 200);
            }""",
            text,
        )
        self.pause(0.4 + hold)

    def pause(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000))

    def point(self, locator) -> None:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.evaluate(
            "([x, y]) => { const c = document.getElementById('demo-cursor');"
            " c.style.left = x + 'px'; c.style.top = y + 'px'; }",
            [x, y],
        )
        self.pause(0.6)

    def click(self, locator) -> None:
        self.point(locator)
        self.page.evaluate("document.getElementById('demo-cursor').classList.add('down')")
        self.pause(0.12)
        locator.click()
        self.page.evaluate("document.getElementById('demo-cursor').classList.remove('down')")
        self.pause(0.3)

    def ask(self, question: str, read: float = 4.0) -> None:
        """Types a question, sends it and waits until the answer has finished streaming."""
        box = self.page.get_by_test_id("question-input")
        answered = self.page.get_by_test_id("answer").count()
        self.click(box)
        box.press_sequentially(question, delay=28)
        self.pause(0.5)
        self.click(self.page.get_by_test_id("send"))
        self.page.wait_for_function(
            "(n) => document.querySelectorAll('[data-testid=answer]').length > n"
            " && !document.querySelector('.caret')"
            " && document.querySelector('[data-testid=send]')",
            arg=answered,
            timeout=90_000,
        )
        self.pause(read)

    def write_srt(self, path: Path, total: float) -> None:
        def stamp(seconds: float) -> str:
            ms = int(round(seconds * 1000))
            return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

        blocks = []
        for index, (start, text) in enumerate(self.cues):
            end = self.cues[index + 1][0] if index + 1 < len(self.cues) else total
            blocks.append(f"{index + 1}\n{stamp(start)} --> {stamp(max(end - 0.05, start + 0.5))}\n{text}\n")
        path.write_text("\n".join(blocks), encoding="utf-8")


def run_demo(page: Page, director: Director) -> None:
    d = director
    pdfs = sorted(str(p) for p in (ROOT / "sample_docs").glob("*.pdf"))

    d.caption("Folio answers questions across multiple PDF documents, using only what the documents say.", 4.5)

    # 1. Upload
    d.caption("Step 1. Upload several PDF reports at once: two annual reports, a sustainability report and a security policy.", 1.5)
    d.point(page.get_by_test_id("upload-button"))
    page.get_by_test_id("file-input").set_input_files(pdfs)
    d.pause(1.5)
    d.caption("Each file is read page by page, split into passages and indexed for search.", 0)
    page.wait_for_function(
        "(n) => document.querySelectorAll('[data-testid=document-row]').length === n"
        " && document.querySelector('[data-testid=scope]').textContent.includes('all ' + n)",
        arg=len(pdfs),
        timeout=120_000,
    )
    d.pause(3.5)

    # 2. First question with citations
    d.caption("Step 2. Ask a question in plain English.", 0.8)
    d.ask("What was Aurora Dynamics' total revenue in 2024, and how did it compare with 2023?", read=1.5)
    d.caption("The answer is written only from the documents. Every statement carries a numbered source reference.", 5)

    # 3. Open a citation
    d.caption("Step 3. Click a reference to see the exact passage and the original PDF page it came from.", 1)
    d.click(page.get_by_test_id("citation").first)
    d.pause(6)
    d.click(page.get_by_label("Close source"))

    # 4. Cross-document question
    d.caption("Questions can span documents. This one needs both the 2023 and the 2024 annual report.", 1)
    d.ask("The 2023 report gave revenue guidance for 2024. What was it, and was it met?", read=2)
    d.caption("The answer combines the two reports and cites each one separately.", 5)

    # 5. Conversation memory
    d.click(page.get_by_test_id("new-chat"))
    d.caption("Conversation memory. Start with a question, then ask follow-ups without repeating the details.", 1)
    d.ask("Which company did Aurora Dynamics acquire in 2024?", read=3)
    d.ask("How much did they pay for it?", read=1)
    d.caption('"They" and "it" are resolved from the conversation. The line above the answer shows how the question was understood.', 5.5)
    d.ask("And where is it based?", read=4)

    # 6. Unanswerable question
    d.caption("What if the answer is not in the documents?", 1)
    d.ask("What is Aurora Dynamics' current share price?", read=1)
    d.caption("The system says it could not find the information instead of guessing, and shows no sources.", 5)

    # 7. Document filter
    d.click(page.get_by_test_id("new-chat"))
    d.caption("You can limit the search to selected documents. Here only the security policy stays ticked.", 0.5)
    for name in ("Annual_Report_2023", "Annual_Report_2024", "Sustainability_Report_2024"):
        d.click(page.get_by_label(f"Include Aurora_Dynamics_{name}.pdf in search"))
    d.pause(1.5)
    d.ask("What are the password rules, and how quickly must security incidents be reported?", read=2)
    d.caption("The answer and its references now come from the security policy alone.", 4.5)
    d.click(page.get_by_test_id("citation").last)
    d.pause(4.5)
    d.click(page.get_by_label("Close source"))

    # 8. History
    d.caption("Every conversation is saved. Reopening one restores its questions, answers and sources.", 0.5)
    d.click(page.get_by_role("button", name="Which company did Aurora Dynamics acquire in 2024?", exact=True))
    d.pause(4.5)

    d.caption("Folio: FastAPI, React, SQLite, hybrid retrieval (vector + keyword search) and OpenAI models.", 5)


def start_server(data_dir: Path) -> subprocess.Popen:
    env = {**os.environ, "DATA_DIR": str(data_dir)}
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--port", str(PORT),
         "--log-level", "warning"],
        cwd=ROOT / "backend",
        env=env,
    )
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/api/health", timeout=2).json()["openai_configured"]:
                return process
            process.terminate()
            raise SystemExit("OPENAI_API_KEY is not configured in .env")
        except httpx.HTTPError:
            time.sleep(0.5)
    process.terminate()
    raise SystemExit("The app server did not start.")


def to_mp4(source: Path, target: Path) -> None:
    import imageio_ffmpeg

    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(source),
         "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-an", str(target)],
        check=True,
    )


def main() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("Build the frontend first: cd frontend && npm install && npm run build")
    DEMO_DIR.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="folio-demo-"))
    server = start_server(work / "data")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                record_video_dir=str(work / "video"),
                record_video_size={"width": WIDTH, "height": HEIGHT},
            )
            recording_started = time.time()
            page = context.new_page()
            page.goto(BASE)
            page.wait_for_selector("[data-testid=upload-button]")
            page.evaluate(OVERLAY)
            director = Director(page, recording_started)
            run_demo(page, director)
            total = time.time() - director.started
            video = page.video
            context.close()
            browser.close()
            raw = Path(video.path())
        director.write_srt(DEMO_DIR / "demo.srt", total)
        to_mp4(raw, DEMO_DIR / "demo.mp4")
        size = (DEMO_DIR / "demo.mp4").stat().st_size / 1024 / 1024
        print(f"Saved demo/demo.mp4 ({size:.1f} MB, {total:.0f}s) and demo/demo.srt")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
