"""Landing, login, and the assignment brief stay in the app shell."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def test_landing_follows_the_scroll_guide():
    text = (SRC / "LandingPage.tsx").read_text()
    assert "AOS.init" in text
    assert "once: true" in text
    assert "offset: 48" in text
    assert 'data-aos="fade-up"' in text
    assert 'data-aos="fade-left"' in text
    assert 'data-aos="zoom-in"' in text
    assert "index * 100" in text
    assert "index * 120" in text
    assert "prefers-reduced-motion" in text


def test_brief_explains_the_lending_path():
    text = (SRC / "BriefPage.tsx").read_text()
    for name in ("Intake", "Scoring", "Evidence", "Casework", "Decision", "Promotion", "Lending ops", "Tenant wall"):
        assert name in text
    assert "applicant" in text.lower()
    assert "Credit risk" in text
    assert 'id="path-heading"' in text


def test_brief_reports_runs_to_datarobot_now():
    text = (SRC / "BriefPage.tsx").read_text()
    assert "later build" not in text
    assert "casework.run" in text
    assert "DataRobot external agent monitoring" in text


def test_brief_says_who_it_serves():
    text = (SRC / "BriefPage.tsx").read_text()
    assert 'id="served-heading"' in text
    assert "Who this serves" in text
    for name in ("Credit risk", "Lending ops", "Casework analyst", "Pod lead", "Applicant", "Another bank"):
        assert name in text
    assert "Who." in text and "How." in text
    assert "not a user of Casework" in text
    assert "Nothing is emailed" in text
    assert "serve-grid" in text


def test_brief_explains_code_first():
    text = (SRC / "BriefPage.tsx").read_text()
    assert 'id="code-first-heading"' in text
    assert "Code first" in text
    assert "agent/runner.py" in text
    assert "TriageState" in text
    for step in ("Start", "Planner", "Operator", "Checker", "End"):
        assert step in text
    assert "diagrams/code-first.svg" in text
    assert "diagrams/who-this-serves.svg" in text
    assert "diagrams/the-path.svg" in text
    readme = (ROOT / "README.md").read_text()
    for name in ("code-first", "who-this-serves", "the-path"):
        assert f"frontend/src/diagrams/{name}.svg" in readme
        assert f"frontend/src/diagrams/{name}.excalidraw" in readme
        assert (ROOT / "frontend" / "src" / "diagrams" / f"{name}.excalidraw").is_file()
        assert (ROOT / "frontend" / "src" / "diagrams" / f"{name}.svg").is_file()


def test_brief_covers_the_assignment():
    text = (SRC / "BriefPage.tsx").read_text()
    for beat in (
        "The problem",
        "The solution",
        "The live demo",
        "Challenges and learnings",
        "The vision",
    ):
        assert beat in text
    assert "LangGraph" in text
    assert "DataRobot" in text
    assert "btn-open-desk" in text
    assert "The tools" in text
    for tool in (
        "React",
        "Vite",
        "serve",
        "AOS",
        "Source Sans 3",
        "JetBrains Mono",
        "FastAPI",
        "Uvicorn",
        "Pydantic",
        "LangChain Core",
        "sse-starlette",
        "SQLite",
        "Docker Compose",
        "OmniRoute",
        "pytest",
        "Playwright",
        "OpenTelemetry",
    ):
        assert tool in text, tool
    for unused in ("LightRAG", "Ollama", "Gitleaks", "TruffleHog", "Trivy", "Semgrep", "Prowler"):
        assert unused not in text, unused


def test_login_is_the_demo_analyst():
    text = (SRC / "LoginPage.tsx").read_text()
    assert "analyst" in text
    assert "demo" in text
    assert "/brief" in text
    assert "btn-reveal" in text
    assert "Show password" in text


def test_desk_shows_the_run_and_the_decision():
    app = (SRC / "App.tsx").read_text()
    css = (SRC / "styles.css").read_text()
    assert 'id="decision-status"' in app
    assert 'id="btn-explanation"' in app
    assert "go('/brief')" in app
    assert 'id="scope-allow"' in app
    assert "No requests at this priority" in app
    assert "aria-busy" in app
    assert "scrollIntoView" in app
    assert "/api/audit" in app
    assert "window.addEventListener('keydown'" in app
    assert "minmax(120px, 156px)" not in css
    assert ".step-line" in css
    hdr = css.split(".hdr {", 1)[1].split("}", 1)[0]
    assert "flex-direction: row" in hdr
    assert 'id="graph-guide"' in app
    assert "What is this?" in app
    assert 'id="graph-expanded"' in app
    assert "Expand map" in app
    assert 'id="ai-console"' in app
    assert 'mapId="graphrag-map"' in app
    assert "/api/graph" in app
    assert 'id="console-resize"' in app
    assert 'id="btn-console-expand"' in app
    assert 'id="btn-console-shrink"' in app
    assert "--console-h" in css
    assert "LangChain Core" in app
    assert "SQLite GraphRAG" in app
    assert "grid-area: console" in css
    assert 'id="approval-why"' in app
    assert "Why this can be approved" in app
    assert "can be approved" in app
    assert "status-hold" in app
    assert "Neither one has been rejected" in app
    assert 'id="reply-review"' in app
    assert "Reply to review" in app
    assert "tool-langgraph" in app and "tool-langchain" in app and "tool-rag" in app
    assert "tool-omni" in app and "tool-otel" in app
    assert "HAS_FINDING" in app and "SAME_SEGMENT" in app and "OWNED_BY" in app
    assert "This picture is for the analyst" in app
