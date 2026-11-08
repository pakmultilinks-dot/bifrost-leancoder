"""Build the LeanCoder pitch deck: pitch-deck.pdf and pitch-deck.pptx.

One source of truth for every number on every slide. All numbers come
from MEASURED.md, from the 40 live measured runs (Batch 3: 10 runs,
Batch 4: 30 runs), model ollama/qwen2.5-coder:3b through Bifrost v2.5.0,
local model, no key. Rebuild with: python3 build_pitch_deck.py
"""

import os

REPO = "github.com/pakmultilinks-dot/bifrost-leancoder"
MODEL = "ollama/qwen2.5-coder:3b"

# Every slide: title, list of lines. Lines starting with "- " are bullets,
# lines starting with "  " are indented sub-bullets, other lines are
# plain text. Tables are (header, rows) tuples.
SLIDES = [
    {
        "title": "LeanCoder",
        "lines": [
            "The coding agent that proves every token",
            "",
            "Build a Coding Agent That Gets the Job Done",
            "on the Fewest Tokens",
            "",
            "Global AI Hackathon, Bifrost cash track",
            "Model: " + MODEL + ", local, through Bifrost v2.5.0",
            REPO,
        ],
    },
    {
        "title": "Problem",
        "lines": [
            "AI coding tools send the whole repository on every turn.",
            "Teams pay for context they never needed, and nobody can",
            "prove what a task actually cost.",
            "",
            "- A run can keep going after a provider outage",
            "- A run can blow past a spending limit",
            "- Private code can leak to a remote model",
            "- Files can be written and commands run with no approval",
        ],
    },
    {
        "title": "Solution",
        "lines": [
            "LeanCoder sends only the code a task needs, found by a",
            "small local code search, and proves the saving with a",
            "measured token ledger.",
            "",
            "- Lean mode: only the files the task needs go to the model",
            "- Approval before every file write, shell command, Git action",
            "- Per-task token budget with a hard stop",
            "- Every call through Bifrost, local model fallback",
            "- Private tasks run only on a local model",
        ],
    },
    {
        "title": "How lean mode works",
        "lines": [
            "1. Local code search finds the files the task needs",
            "2. Only those files go to the model, nothing else",
            "3. Files are re-read on every step, so a retry sees",
            "   the current file state after its own patch",
            "4. The model proposes a patch, the approval gate shows",
            "   the diff, then the patch is applied and tests run",
            "5. At most 5 steps, then the run stops and reports",
            "",
            "Direct mode, the baseline, sends the whole repo",
            "context on every model call.",
        ],
    },
    {
        "title": "Architecture",
        "lines": [
            "- Agent loop: plan, read, propose patch, approve,",
            "  apply, run tests, retry, report",
            "- Tools: sandboxed file write, shell, and Git,",
            "  all inside the task repo only",
            "- Retrieval: small local code search, no vector DB",
            "- Budget: per-task token and cost budget, hard stop",
            "- Bifrost client: OpenAI-compatible, timeout,",
            "  retry once on timeout only, clear error on 401",
            "- Ledger and replay: every token counted from the",
            "  model response, every run replayable offline",
            "",
            "Python, requests only. Model: " + MODEL + ".",
        ],
    },
    {
        "title": "Measured results: 40 live runs",
        "lines": [
            "5 tasks, lean mode vs direct mode, same model,",
            MODEL + " through Bifrost v2.5.0.",
            "",
            "- Tokens per passing task, combined: lean 734.3,",
            "  direct 842.5, about 13 percent fewer for lean",
            "- Passes, combined: lean 15 of 20, direct 17 of 20",
            "- Batch 3: lean 560.5 vs direct 579.75 per passing",
            "  task, 4 of 5 each",
            "- Batch 4: lean 797.5 vs direct 923.4, about 14",
            "  percent fewer, lean 11 of 15, direct 13 of 15",
            "- Honest limit: lean had the lower mean on only 2",
            "  of 5 tasks in Batch 4, task4 lean ranged from 462",
            "  to 2652 tokens, no mean is a stable truth",
            "- Cost is 0.0 for every run: the model runs locally",
        ],
    },
    {
        "title": "Outage drill and private-task proof",
        "lines": [
            "Outage drill: the client was pointed at a dead gateway.",
            "- Result: plain error, 0 tokens, no invented success",
            "- Error: Could not reach Bifrost at",
            "  http://127.0.0.1:9999. Start Bifrost first, then retry.",
            "",
            "Private-task proof: a task marked PRIVATE, run twice.",
            "- Remote model: refused before any model call,",
            "  0 model calls, 0 tokens",
            "- Local model: it ran, retry passed in 2 steps,",
            "  854 tokens",
        ],
    },
    {
        "title": "Judge verification",
        "lines": [
            "python3 verify.py",
            "",
            "- Offline: no key, no Docker, no Bifrost",
            "- Runs the full unit test suite: 83 tests passed",
            "- Replays all 40 recorded traces: 40 of 40 matched",
            "- Patches re-applied, hidden tests re-run, ledger",
            "  token totals checked",
            "- Result: PASS, exit 0, 4.8 seconds",
            "- Failed tasks replay as failures too: replay checks",
            "  what happened, it does not turn failures into passes",
            "",
            "Public repo: " + REPO,
        ],
    },
    {
        "title": "What is next",
        "lines": [
            "- A bigger model, when the machine allows it: a 7b",
            "  model did not fit this 8 GB machine",
            "- More tasks and more repeats, to shrink the noise",
            "  in the means",
            "- A remote free tier model as primary through Bifrost,",
            "  with the local model as fallback, once a key exists",
            "- Private code stays local in every case",
            "",
            "The ledger stays honest either way: every run is",
            "measured, every failure is shown as a failure.",
        ],
    },
    {
        "title": "LeanCoder",
        "lines": [
            "Lean used about 13 percent fewer tokens per passing",
            "task across 40 live runs: 734.3 against 842.5,",
            "and passed 15 of 20 against 17 of 20.",
            "",
            "Every token is counted. Every failure is shown.",
            "Verification needs no key.",
            "",
            REPO,
            "",
            "A place in the Bifrost cash track.",
        ],
    },
]

BG = (0x0F, 0x1B, 0x2D)
TITLE_COLOR = (0xFF, 0xFF, 0xFF)
ACCENT = (0x2D, 0xD4, 0xBF)
BODY_COLOR = (0xD6, 0xDE, 0xE8)
MUTED = (0x8A, 0x9B, 0xB0)


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def build_pdf(path):
    from reportlab.lib.pagesizes import landscape
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    page_w, page_h = 13.33 * inch, 7.5 * inch
    c = canvas.Canvas(path, pagesize=(page_w, page_h))
    for idx, slide in enumerate(SLIDES):
        c.setFillColor(HexColor(_hex(BG)))
        c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
        c.setFillColor(HexColor(_hex(ACCENT)))
        c.rect(0.6 * inch, page_h - 1.05 * inch, 0.55 * inch, 0.07 * inch,
               stroke=0, fill=1)
        c.setFillColor(HexColor(_hex(TITLE_COLOR)))
        c.setFont("Helvetica-Bold", 34)
        c.drawString(0.6 * inch, page_h - 0.85 * inch, slide["title"])
        y = page_h - 1.55 * inch
        for line in slide["lines"]:
            if line == "":
                y -= 0.18 * inch
                continue
            if line.startswith("  "):
                c.setFont("Helvetica", 17)
                c.setFillColor(HexColor(_hex(BODY_COLOR)))
                c.drawString(1.15 * inch, y, line.strip())
            elif line.startswith("- "):
                c.setFont("Helvetica", 18)
                c.setFillColor(HexColor(_hex(ACCENT)))
                c.drawString(0.85 * inch, y, "-")
                c.setFillColor(HexColor(_hex(BODY_COLOR)))
                c.drawString(1.15 * inch, y, line[2:])
            else:
                c.setFont("Helvetica", 19)
                c.setFillColor(HexColor(_hex(BODY_COLOR)))
                c.drawString(0.6 * inch, y, line)
            y -= 0.34 * inch
        c.setFont("Helvetica", 11)
        c.setFillColor(HexColor(_hex(MUTED)))
        c.drawString(0.6 * inch, 0.45 * inch, "LeanCoder")
        c.drawRightString(page_w - 0.6 * inch, 0.45 * inch,
                          "%d / %d" % (idx + 1, len(SLIDES)))
        c.showPage()
    c.save()


def build_pptx(path):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    for idx, slide in enumerate(SLIDES):
        s = prs.slides.add_slide(blank)
        bg = s.background
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(*BG)
        bar = s.shapes.add_shape(1, Inches(0.6), Inches(0.55),
                                 Inches(0.55), Inches(0.07))
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*ACCENT)
        bar.line.fill.background()
        tb = s.shapes.add_textbox(Inches(0.6), Inches(0.7),
                                  Inches(12.1), Inches(0.8))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = slide["title"]
        p.font.size = Pt(34)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*TITLE_COLOR)
        body = s.shapes.add_textbox(Inches(0.6), Inches(1.7),
                                    Inches(12.1), Inches(5.1))
        btf = body.text_frame
        btf.word_wrap = True
        first = True
        for line in slide["lines"]:
            if line == "":
                if not first:
                    p = btf.add_paragraph()
                    p.font.size = Pt(10)
                continue
            p = btf.paragraphs[0] if first else btf.add_paragraph()
            first = False
            if line.startswith("  "):
                p.text = line.strip()
                p.font.size = Pt(17)
                p.space_before = Pt(2)
            elif line.startswith("- "):
                p.text = "- " + line[2:]
                p.font.size = Pt(18)
                p.space_before = Pt(4)
            else:
                p.text = line
                p.font.size = Pt(19)
                p.space_before = Pt(2)
            p.font.color.rgb = RGBColor(*BODY_COLOR)
            if line.startswith("- "):
                p.font.color.rgb = RGBColor(*BODY_COLOR)
        foot = s.shapes.add_textbox(Inches(0.6), Inches(7.0),
                                    Inches(12.1), Inches(0.35))
        ftf = foot.text_frame
        ftf.word_wrap = True
        p = ftf.paragraphs[0]
        p.text = "LeanCoder    %d / %d" % (idx + 1, len(SLIDES))
        p.font.size = Pt(11)
        p.font.color.rgb = RGBColor(*MUTED)
    prs.save(path)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    build_pdf(os.path.join(here, "pitch-deck.pdf"))
    build_pptx(os.path.join(here, "pitch-deck.pptx"))
    print("Built pitch-deck.pdf and pitch-deck.pptx, %d slides"
          % len(SLIDES))


if __name__ == "__main__":
    main()
