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
        "LightRAG",
        "Ollama",
        "Gitleaks",
        "TruffleHog",
        "Trivy",
        "Semgrep",
        "Prowler",
        "pytest",
        "Playwright",
        "OpenTelemetry",
    ):
        assert tool in text, tool


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
    assert 'id="scope-allow"' in app
    assert "No requests at this priority" in app
    assert "aria-busy" in app
    assert "scrollIntoView" in app
    assert "/api/audit" in app
    assert "window.addEventListener('keydown'" in app
    assert "minmax(120px, 156px)" not in css
    assert ".step-line" in css
