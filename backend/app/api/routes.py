import asyncio
import html
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.models.config import settings
from app.models.schemas import (
    ProviderCatalog,
    ModelInfo,
    AnalyzeRequest,
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    ReportJsonResponse,
    Recommendation,
    ConflictResolution,
    CommunityMetrics,
    GuardrailTelemetry,
    LineRisk
)
from app.api.progress_bus import progress_bus

router = APIRouter()

# In-memory database for mock reports
analyses_db: dict[str, dict] = {}
# In-memory history list
history_db: list[dict] = []


def _find_history(job_id: str | None) -> dict | None:
    if not job_id:
        return None
    return next((item for item in history_db if item.get("job_id") == job_id), None)


def _compact_report_context(job_id: str | None, repo_path: str | None) -> str:
    report = analyses_db.get(job_id or "")
    history = _find_history(job_id)
    path = repo_path or (history or {}).get("path") or "unknown repository"
    codemap_scaffold_context = {
        "frontend_core_files": [
            "frontend/src/app/page.tsx",
            "frontend/src/app/analyze/page.tsx",
            "frontend/src/components/RepoInput.tsx",
            "frontend/src/components/ProgressPanel.tsx",
            "frontend/src/components/ReportViewer.tsx",
            "frontend/src/components/ProjectChatPanel.tsx",
            "frontend/src/components/HistoryList.tsx",
            "frontend/src/hooks/useWebSocket.ts",
            "frontend/src/lib/api.ts",
            "frontend/src/types/contracts.ts",
        ],
        "backend_core_files": [
            "backend/app/main.py",
            "backend/app/api/routes.py",
            "backend/app/api/progress_bus.py",
            "backend/app/models/schemas.py",
            "backend/app/models/config.py",
            "backend/app/services/repo_cloner.py",
            "backend/app/services/analysis_store.py",
            "backend/app/orchestrator/planner.py",
            "backend/app/agents/code_mapper.py",
            "backend/app/agents/doc_generator.py",
            "backend/app/agents/onboarding_guide.py",
        ],
        "current_mvp_limits": [
            "Most backend analysis data is mock data.",
            "Repo clone, persistent store, and real code analysis agents are scaffolded but not fully implemented.",
            "The deployed preview runs a static Next.js frontend and FastAPI backend behind oosu.dev/codemap/example.",
        ],
    }

    if not report:
        return (
            f"Repository: {path}\n"
            "Analysis report is not available yet. Answer from the visible project context and say when the report is still running.\n"
            f"Known CodeMap AI scaffold context: {json.dumps(codemap_scaffold_context, ensure_ascii=False)}"
        )

    context = {
        "repository": path,
        "job_id": job_id,
        "status": report.get("status"),
        "executive_summary": report.get("executive_summary"),
        "health_score": report.get("health_score"),
        "key_strengths": report.get("key_strengths", []),
        "key_risks": report.get("key_risks", []),
        "recommendations": report.get("recommendations", [])[:5],
        "conflicts_resolved": report.get("conflicts_resolved", [])[:3],
        "file_heatmap": report.get("file_heatmap", {}),
        "agent_durations": report.get("agent_durations", {}),
        "known_codemap_ai_scaffold": codemap_scaffold_context,
    }
    return json.dumps(context, ensure_ascii=False, default=str)


def _fallback_chat_answer(message: str, context: str) -> str:
    return (
        "현재 서버에 AI provider 키가 연결되지 않았거나 일시적으로 응답을 받지 못해, "
        "분석 리포트 기반의 기본 답변을 제공합니다.\n\n"
        f"질문: {message}\n\n"
        "이 프로젝트는 CodeMap AI의 분석 결과를 바탕으로 구조 요약, 위험 지점, 추천 작업, "
        "온보딩 순서를 설명하는 대시보드입니다. 우측 리포트의 executive summary, recommendations, "
        "file heatmap을 먼저 확인하면 팀원이 수정해야 할 파일과 위험 포인트를 빠르게 파악할 수 있습니다.\n\n"
        f"사용된 컨텍스트 요약:\n{context[:1200]}"
    )


MODEL_FALLBACKS = {
    "fast": "google/gemini-2.5-flash",
    "balanced": "anthropic/claude-sonnet-4.5",
    "deep": "openai/gpt-5.1",
    "qwen": "qwen/qwen3-coder",
}

SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".turbo", "coverage",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".mp4", ".mov", ".woff", ".woff2", ".ttf", ".pyc",
}
SECRET_PATTERNS = re.compile(r"(api[_-]?key|secret|token|password|private key|-----BEGIN)", re.I)


def _provider_base_url() -> str:
    return (
        settings.AI_BASE_URL
        or os.getenv("OPENROUTER_BASE_URL")
        or ("https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else "https://api.openai.com/v1")
    ).rstrip("/")


def _provider_headers() -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("AI_API_KEY_MISSING")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://oosu.dev"),
        "X-Title": os.getenv("OPENROUTER_SITE_NAME", "CodeMap AI"),
    }


def _call_chat_provider(messages: list[dict], model: str | None = None, max_tokens: int = 900) -> tuple[str, str]:
    base_url = _provider_base_url()
    selected_model = model or settings.AI_MODEL or ("google/gemini-2.5-flash" if os.getenv("OPENROUTER_API_KEY") else settings.DEFAULT_MODEL)

    payload = {
        "model": selected_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_provider_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI_PROVIDER_ERROR:{exc.code}:{detail[:500]}") from exc

    answer = data["choices"][0]["message"]["content"]
    return answer, selected_model


def _openrouter_model_candidates() -> list[ModelInfo]:
    preferred = [
        ("auto", "Auto Select", "Repo size and language aware model selection."),
        ("google/gemini-2.5-flash", "Gemini 2.5 Flash", "Fast analysis for small and medium repositories."),
        ("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", "Strong code reasoning and architecture explanations."),
        ("openai/gpt-5.1", "GPT-5.1", "Deep reasoning for larger or more complex codebases."),
        ("qwen/qwen3-coder", "Qwen3 Coder", "Code-focused model option."),
    ]
    try:
        req = urllib.request.Request(f"{_provider_base_url()}/models", headers=_provider_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        available = {item.get("id"): item for item in data.get("data", []) if item.get("id")}
        models = []
        for model_id, label, hint in preferred:
            if model_id == "auto" or model_id in available:
                models.append(ModelInfo(id=model_id, label=label, hint=hint))
        if len(models) >= 3:
            return models
    except Exception:
        pass
    return [ModelInfo(id=model_id, label=label, hint=hint) for model_id, label, hint in preferred]


def _choose_model(requested: str | None, stats: dict) -> str:
    if requested and requested != "auto":
        return requested
    available = {model.id for model in _openrouter_model_candidates()}
    def pick(*ids: str) -> str:
        for model_id in ids:
            if model_id in available:
                return model_id
        return MODEL_FALLBACKS["fast"]
    file_count = stats.get("file_count", 0)
    total_chars = stats.get("total_chars", 0)
    languages = stats.get("languages", {})
    if file_count > 350 or total_chars > 750_000:
        return pick(MODEL_FALLBACKS["deep"], MODEL_FALLBACKS["balanced"], MODEL_FALLBACKS["fast"])
    if file_count > 120 or any(lang in languages for lang in ("Python", "TypeScript", "JavaScript")):
        return pick(MODEL_FALLBACKS["balanced"], MODEL_FALLBACKS["deep"], MODEL_FALLBACKS["fast"])
    return pick(MODEL_FALLBACKS["fast"], MODEL_FALLBACKS["balanced"])


def _clone_repo(repo_url: str, job_id: str) -> Path:
    if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?$", repo_url):
        raise ValueError("Only public GitHub HTTPS repository URLs are supported for real analysis.")
    workspace = Path(os.getenv("CODEMAP_WORKSPACE_ROOT", "/tmp/codemap-ai-workspace"))
    workspace.mkdir(parents=True, exist_ok=True)
    target = Path(mkdtemp(prefix=f"{job_id}-", dir=workspace))
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target)],
        check=True,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("CLONE_TIMEOUT_SECONDS", "90")),
    )
    return target


def _detect_language(path: Path) -> str:
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".swift": "Swift",
        ".rb": "Ruby", ".php": "PHP", ".md": "Markdown", ".yml": "YAML",
        ".yaml": "YAML", ".json": "JSON", ".toml": "TOML", ".css": "CSS",
    }
    return ext_map.get(path.suffix.lower(), "Other")


def _iter_candidate_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 180_000:
                continue
        except OSError:
            continue
        files.append(path)
    return sorted(files, key=lambda p: (len(p.relative_to(root).parts), str(p.relative_to(root))))[:450]


def _read_safe_text(path: Path, limit: int = 8000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if SECRET_PATTERNS.search(path.name) or SECRET_PATTERNS.search(text[:1200]):
        text = SECRET_PATTERNS.sub("[REDACTED]", text)
    return text[:limit]


def _analyze_repository_files(root: Path) -> dict:
    files = _iter_candidate_files(root)
    languages: dict[str, int] = {}
    candidates = []
    risk_files = []
    entrypoint_names = {
        "package.json", "pyproject.toml", "requirements.txt", "Dockerfile",
        "docker-compose.yml", "next.config.ts", "vite.config.ts", "main.py",
        "app.py", "README.md", "tsconfig.json",
    }
    risk_re = re.compile(r"(auth|login|token|secret|password|payment|database|db|cors|eval|exec|subprocess|TODO|FIXME)", re.I)
    for file in files:
        rel = str(file.relative_to(root))
        lang = _detect_language(file)
        languages[lang] = languages.get(lang, 0) + 1
        text = _read_safe_text(file, 3000)
        risk_score = 0
        reasons = []
        if risk_re.search(rel) or risk_re.search(text[:1500]):
            risk_score += 2
            reasons.append("security/config/runtime keyword")
        if len(text) > 2500:
            risk_score += 1
            reasons.append("large or dense file")
        if file.name in entrypoint_names or rel.startswith(("frontend/src/app", "backend/app/api")):
            risk_score += 1
            reasons.append("entrypoint or routing surface")
        if risk_score:
            risk_files.append({"path": rel, "risk_score": risk_score, "reasons": reasons[:3]})
        if file.name in entrypoint_names or len(candidates) < 35:
            candidates.append({
                "path": rel,
                "language": lang,
                "chars": len(text),
                "preview": text[:1400],
            })
    stats = {
        "file_count": len(files),
        "languages": languages,
        "total_chars": sum(item["chars"] for item in candidates),
        "entrypoints": [item["path"] for item in candidates if Path(item["path"]).name in entrypoint_names][:20],
        "risk_files": sorted(risk_files, key=lambda item: item["risk_score"], reverse=True)[:20],
        "sample_files": candidates[:40],
    }
    return stats


def _json_from_model_text(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{.*\}", stripped, re.S)
    if match:
        stripped = match.group(0)
    return json.loads(stripped)


def _report_from_ai_text(text: str, stats: dict) -> dict:
    clean = text.strip() or "AI 모델이 빈 응답을 반환했습니다."
    clean = re.sub(r"^```(?:json)?", "", clean).strip()
    clean = re.sub(r"```$", "", clean).strip()
    paragraphs = "\n".join(
        f"<p>{html.escape(line.strip())}</p>"
        for line in clean.splitlines()
        if line.strip()
    )
    return {
        "executive_summary": clean[:1400],
        "health_score": 78,
        "key_strengths": [
            f"실제 Git clone 후 {stats.get('file_count', 0)}개 파일을 스캔했습니다.",
            f"언어 구성: {', '.join(stats.get('languages', {}).keys()) or 'unknown'}",
        ],
        "key_risks": [
            "AI 응답이 구조화 JSON이 아니어서 추천 항목 일부는 정적 분석 결과와 함께 표시됩니다.",
        ],
        "recommendations": [],
        "conflicts_resolved": [],
        "html_report": f"""
        <div class="space-y-4">
          <h2>AI Repository Analysis</h2>
          {paragraphs}
        </div>
        """,
    }


def _fallback_report(job_id: str, repo_url: str, stats: dict, model: str, started_at: float) -> dict:
    risk_files = stats.get("risk_files", [])[:3]
    recommendations = [
        Recommendation(
            title="우선 진입점과 라우팅 파일부터 온보딩 문서화",
            detail="자동 분석에서 entrypoint/config/routing surface가 먼저 발견되었습니다. 팀원이 실행 흐름을 빠르게 잡을 수 있도록 README와 라우팅 파일을 기준으로 문서화하세요.",
            affected_files=stats.get("entrypoints", [])[:4] or ["README.md"],
            priority="high",
        )
    ]
    file_heatmap = {
        item["path"]: [LineRisk(line=1, risk_level="medium", reason=", ".join(item["reasons"]), metric="maintainability")]
        for item in risk_files
    }
    return ReportJsonResponse(
        job_id=job_id,
        status="completed",
        completed_at=datetime.utcnow().isoformat() + "Z",
        total_pipeline_ms=int((time.time() - started_at) * 1000),
        recommendations=recommendations,
        conflicts_resolved=[],
        community=CommunityMetrics(
            commits_per_week=0,
            avg_issue_response_hours=None,
            unique_contributors=0,
            top_contributors=[],
            is_degraded=True,
            degraded_reason="GitHub community metrics are not connected yet.",
        ),
        html_report=f"""
        <div class="space-y-4">
          <h2>Real Repository Scan: {repo_url}</h2>
          <p>Scanned {stats.get('file_count', 0)} source/config/docs files. Language mix: {stats.get('languages', {})}.</p>
          <h3>Suggested entrypoints</h3>
          <ul>{''.join(f'<li>{item}</li>' for item in stats.get('entrypoints', [])[:8])}</ul>
          <h3>Risk candidates</h3>
          <ul>{''.join(f'<li>{item["path"]}: {", ".join(item["reasons"])}</li>' for item in risk_files)}</ul>
        </div>
        """,
        file_heatmap=file_heatmap,
        guardrail_telemetry=GuardrailTelemetry(regex_blocked=[], semantic_filtered=[], regenerate_count=0, fallback_triggered=True, input_secrets_redacted=0, self_check_warnings=[]),
        agent_durations={"static_analyzer": int((time.time() - started_at) * 1000), "behavior_inferer": 0, "community_assessor": 0, "reporter": 0},
        executive_summary=f"실제 Git clone 후 {stats.get('file_count', 0)}개 파일을 스캔했습니다. AI 리포트 생성이 실패해 정적 분석 기반 요약을 표시합니다.",
        health_score=70,
        key_strengths=[f"Detected languages: {', '.join(stats.get('languages', {}).keys()) or 'unknown'}"],
        key_risks=["AI provider report generation failed or returned invalid JSON."],
        summary_confidence=0.55,
    ).dict()

# Populate initial history and mock reports for demonstrations
MOCK_JOBS = {
    "numpy-analysis-job": {
        "path": "https://github.com/numpy/numpy",
        "source": "github",
        "model": "gpt-4o",
        "created_at": int(time.time() - 3600),
        "completed_at": int(time.time() - 3550),
        "status": "completed",
        "health_score": 88,
        "executive_summary": "NumPy relies heavily on highly-optimized C loops and SIMD vectorization. The core memory layout utilizes contiguous strided Ndarrays. Most matrix arithmetic routes directly to BLAS/LAPACK implementations. Low-level performance bottlenecks exist in the ufunc outer loop dispatching logic, which is currently undergoing refactoring to modern C++ templates.",
        "key_strengths": [
            "Highly efficient vectorization via SIMD configuration pipelines",
            "Zero-copy memory slicing and advanced layout striding",
            "Direct bindings to industry-standard C BLAS/LAPACK packages"
        ],
        "key_risks": [
            "Extremely high code complexity in legacy C macros (ufunc loops)",
            "Fragmented memory management between Python allocator and C allocations"
        ],
        "recommendations": [
            Recommendation(
                title="Migrate macro-based ufuncs to C++ templates",
                detail="Legacy C preprocessor macros in 'numpy/core/src/multiarray/ufunc_object.c' hinder readability and maintainability. Replacing them with C++ metaprogramming will improve compile-time safety.",
                affected_files=["numpy/core/src/multiarray/ufunc_object.c", "numpy/core/src/umath/ufunc_dispatch.cpp"],
                priority="high"
            ),
            Recommendation(
                title="Sanitize inter-thread GIL releases",
                detail="Ensure GIL releases are properly scoped and don't lead to race conditions during multi-threaded slicing in array expressions.",
                affected_files=["numpy/core/src/multiarray/array_assign.c"],
                priority="medium"
            )
        ],
        "conflicts": [
            ConflictResolution(
                module="ufunc_object.c",
                static_view="Dead code detected in legacy dispatching paths. Recommend aggressive deprecation.",
                behavior_view="Active critical runtime path under SIMD execution. Deprecation would break SIMD optimizations.",
                final_recommendation="Preserve code but wrap in modern C++ templates to unify execution pathways.",
                judge_model="gpt-4o",
                escalated=False,
                confidence=0.92
            )
        ],
        "community": CommunityMetrics(
            commits_per_week=45.2,
            avg_issue_response_hours=3.5,
            unique_contributors=142,
            top_contributors=["charlesrharris", "seberg", "rgommers"],
            is_degraded=False
        ),
        "file_heatmap": {
            "numpy/core/src/multiarray/ufunc_object.c": [
                LineRisk(line=145, risk_level="critical", reason="Unbounded buffer write in macro dispatching loop", metric="complexity"),
                LineRisk(line=312, risk_level="high", reason="GIL released without proper thread context cleanup", metric="maintainability")
            ],
            "numpy/core/src/multiarray/array_assign.c": [
                LineRisk(line=78, risk_level="medium", reason="Redundant copying of strided layout configurations", metric="coverage")
            ]
        },
        "guardrail": GuardrailTelemetry(
            regex_blocked=[],
            semantic_filtered=[],
            regenerate_count=0,
            fallback_triggered=False,
            input_secrets_redacted=0,
            self_check_warnings=[]
        ),
        "durations": {
            "static_analyzer": 12450,
            "behavior_inferer": 18200,
            "community_assessor": 5400,
            "reporter": 8100
        },
        "html_report": """
        <div class="space-y-4">
            <h2>Detailed NumPy Architecture Report</h2>
            <p>This report covers the deep structural analysis of the NumPy ndarray and ufunc dispatch pipeline.</p>
            <h3>1. Ndarray Memory Topology</h3>
            <p>The core ndarray class is backed by a continuous block of memory mapped through a strided coordinate system. Slicing operations are zero-copy, shifting only the offsets and strides.</p>
            <h3>2. Ufunc Dispatches</h3>
            <p>The universal function (ufunc) execution layer resolves loops dynamically depending on alignment and memory continuity:</p>
            <ul>
                <li>Contiguous 1D loops trigger aligned compiler vectorization.</li>
                <li>Strided multi-dimensional loops fall back to nested pointer increments.</li>
            </ul>
        </div>
        """
    },
    "fastapi-analysis-job": {
        "path": "https://github.com/tiangolo/fastapi",
        "source": "github",
        "model": "gpt-4o",
        "created_at": int(time.time() - 7200),
        "completed_at": int(time.time() - 7160),
        "status": "completed",
        "health_score": 95,
        "executive_summary": "FastAPI leverages Pydantic for request/response serialization and Starlette for ASGI routing. Execution flow is driven by asyncio event loops. Route mapping reveals clean dependency-injection flows. Code risks are exceptionally low, with main hotspots centered around custom dynamic parameter parsing and signature matching.",
        "key_strengths": [
            "Extremely high code readability with strict type hints",
            "Highly performant async ASGI routing through Starlette",
            "Automated OpenAPI schema generation at runtime"
        ],
        "key_risks": [
            "High runtime overhead in dynamic inspect-module signatures",
            "Deep dependency coupling with specific Pydantic versions"
        ],
        "recommendations": [
            Recommendation(
                title="Optimize parameter extraction caching",
                detail="Caching signature parsing in 'fastapi/dependencies/utils.py' will reduce request serialization latency under high load.",
                affected_files=["fastapi/dependencies/utils.py"],
                priority="medium"
            )
        ],
        "conflicts": [],
        "community": CommunityMetrics(
            commits_per_week=12.8,
            avg_issue_response_hours=24.5,
            unique_contributors=318,
            top_contributors=["tiangolo", "dmontagu", "Kludex"],
            is_degraded=False
        ),
        "file_heatmap": {
            "fastapi/dependencies/utils.py": [
                LineRisk(line=254, risk_level="medium", reason="Dynamic introspection runtime penalty on every route invocation", metric="complexity")
            ]
        },
        "guardrail": GuardrailTelemetry(
            regex_blocked=[],
            semantic_filtered=[],
            regenerate_count=0,
            fallback_triggered=False,
            input_secrets_redacted=1,
            self_check_warnings=[]
        ),
        "durations": {
            "static_analyzer": 8500,
            "behavior_inferer": 11200,
            "community_assessor": 3800,
            "reporter": 4500
        },
        "html_report": """
        <div class="space-y-4">
            <h2>FastAPI Architecture Review</h2>
            <p>Comprehensive review of async routes and validation layers.</p>
            <h3>Dependency Injection</h3>
            <p>FastAPI uses Pydantic models to inspect function signatures at start time, mapping dependencies recursively to solve DI graphs on requests.</p>
        </div>
        """
    }
}

# Seed database
for jid, data in MOCK_JOBS.items():
    history_db.append({
        "job_id": jid,
        "source": data["source"],
        "path": data["path"],
        "status": data["status"],
        "created_at": data["created_at"],
        "completed_at": data["completed_at"],
        "total_pipeline_ms": sum(data["durations"].values()),
        "error_message": None,
        "model_used": data["model"],
        "force_refresh": False
    })
    
    analyses_db[jid] = ReportJsonResponse(
        job_id=jid,
        status="completed",
        completed_at=datetime.fromtimestamp(data["completed_at"]).isoformat(),
        total_pipeline_ms=sum(data["durations"].values()),
        recommendations=data["recommendations"],
        conflicts_resolved=data["conflicts"],
        community=data["community"],
        html_report=data["html_report"],
        file_heatmap=data["file_heatmap"],
        guardrail_telemetry=data["guardrail"],
        agent_durations=data["durations"],
        executive_summary=data["executive_summary"],
        health_score=data["health_score"],
        key_strengths=data["key_strengths"],
        key_risks=data["key_risks"],
        summary_confidence=0.95
    ).dict()


@router.get("/models", response_model=ProviderCatalog)
async def get_models():
    """Return available model choices for analysis."""
    return ProviderCatalog(
        provider="custom",
        base_url=_provider_base_url(),
        default_model="auto",
        models=_openrouter_model_candidates(),
    )


async def run_real_analysis_pipeline(job_id: str, path: str, source: str, model: str):
    """Clone, scan, and summarize a public GitHub repository."""
    agents = ["static_analyzer", "behavior_inferer", "community_assessor", "reporter"]
    started_at = time.time()
    agent_started: dict[str, float] = {}
    agent_durations: dict[str, int] = {}
    repo_dir: Path | None = None
    
    try:
        agent_started["static_analyzer"] = time.time()
        await progress_bus.publish(job_id, {
            "type": "agent_status",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "static_analyzer",
            "status": "running",
            "progress": 10,
            "stage_label": "Cloning GitHub repository..."
        })
        repo_dir = await asyncio.to_thread(_clone_repo, path, job_id)
        await progress_bus.publish(job_id, {
            "type": "agent_status",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "static_analyzer",
            "status": "running",
            "progress": 45,
            "stage_label": "Scanning files, languages, entrypoints, and risk signals..."
        })
        stats = await asyncio.to_thread(_analyze_repository_files, repo_dir)
        selected_model = _choose_model(model, stats)
        agent_durations["static_analyzer"] = int((time.time() - agent_started["static_analyzer"]) * 1000)
        await progress_bus.publish(job_id, {
            "type": "agent_completed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "static_analyzer",
            "duration_ms": agent_durations["static_analyzer"],
            "summary": f"Scanned {stats['file_count']} files. Selected model: {selected_model}."
        })

        agent_started["behavior_inferer"] = time.time()
        await progress_bus.publish(job_id, {
            "type": "agent_status",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "behavior_inferer",
            "status": "running",
            "progress": 20,
            "stage_label": "Asking AI model to infer architecture and runtime behavior..."
        })
        prompt_context = json.dumps(stats, ensure_ascii=False)[:60_000]
        system_prompt = (
            "You are CodeMap AI. Analyze the supplied real repository scan and return ONLY valid JSON. "
            "Write Korean prose. Do not invent files that are not in the context. "
            "Keep the response concise enough to finish completely. No markdown fences. "
            "JSON schema: {executive_summary:string, health_score:number, key_strengths:string[], key_risks:string[], "
            "recommendations:max 4 items of {title:string, detail:string, affected_files:max 4 strings, priority:'critical'|'high'|'medium'|'low'}, "
            "conflicts_resolved:max 3 items of {module:string, static_view:string, behavior_view:string, final_recommendation:string, confidence:number}, "
            "onboarding_steps:max 5 strings, html_report:string under 900 chars}"
        )
        try:
            ai_text, used_model = await asyncio.to_thread(
                _call_chat_provider,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Repository URL: {path}\nReal scan context:\n{prompt_context}"},
                ],
                selected_model,
                5000,
            )
            try:
                ai_report = _json_from_model_text(ai_text)
            except Exception:
                ai_report = _report_from_ai_text(ai_text, stats)
        except Exception:
            if selected_model != MODEL_FALLBACKS["fast"]:
                try:
                    ai_text, used_model = await asyncio.to_thread(
                        _call_chat_provider,
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Repository URL: {path}\nReal scan context:\n{prompt_context}"},
                        ],
                        MODEL_FALLBACKS["fast"],
                        5000,
                    )
                    try:
                        ai_report = _json_from_model_text(ai_text)
                    except Exception:
                        ai_report = _report_from_ai_text(ai_text, stats)
                except Exception:
                    ai_text, used_model = "", selected_model
                    ai_report = {}
            else:
                ai_text, used_model = "", selected_model
                ai_report = {}
            if not ai_report:
                ai_report = {
                    "executive_summary": f"실제 Git clone 후 {stats['file_count']}개 파일을 스캔했습니다. AI JSON 리포트 생성은 실패해 정적 분석 기반 요약을 사용합니다.",
                    "health_score": 70,
                    "key_strengths": [f"감지된 언어: {', '.join(stats.get('languages', {}).keys()) or 'unknown'}"],
                    "key_risks": ["AI provider 응답을 구조화하지 못해 세부 판단은 제한적입니다."],
                    "recommendations": [],
                    "conflicts_resolved": [],
                    "html_report": "",
                }
        agent_durations["behavior_inferer"] = int((time.time() - agent_started["behavior_inferer"]) * 1000)
        await progress_bus.publish(job_id, {
            "type": "agent_completed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "behavior_inferer",
            "duration_ms": agent_durations["behavior_inferer"],
            "summary": f"AI architecture inference completed with {used_model}."
        })

        agent_started["community_assessor"] = time.time()
        await progress_bus.publish(job_id, {
            "type": "agent_status",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "community_assessor",
            "status": "running",
            "progress": 50,
            "stage_label": "Estimating repository maintainability signals from local scan..."
        })
        await asyncio.sleep(0)
        agent_durations["community_assessor"] = int((time.time() - agent_started["community_assessor"]) * 1000)
        await progress_bus.publish(job_id, {
            "type": "agent_completed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "community_assessor",
            "duration_ms": agent_durations["community_assessor"],
            "summary": "Local maintainability signal assessment completed."
        })

        agent_started["reporter"] = time.time()
        await progress_bus.publish(job_id, {
            "type": "agent_status",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "reporter",
            "status": "running",
            "progress": 75,
            "stage_label": "Composing CodeMap onboarding report..."
        })
        risk_files = stats.get("risk_files", [])[:8]
        file_heatmap = {
            item["path"]: [LineRisk(line=1, risk_level="medium", reason=", ".join(item["reasons"]), metric="maintainability")]
            for item in risk_files
        }
        recommendations = [
            Recommendation(
                title=item.get("title", "추천 작업"),
                detail=item.get("detail", ""),
                affected_files=item.get("affected_files", [])[:8],
                priority=item.get("priority", "medium"),
            )
            for item in ai_report.get("recommendations", [])[:5]
        ] or [
            Recommendation(
                title="핵심 진입점 문서화",
                detail="실제 스캔에서 발견된 entrypoint와 라우팅 파일을 기준으로 신규 팀원용 읽기 순서를 정리하세요.",
                affected_files=stats.get("entrypoints", [])[:5],
                priority="high",
            )
        ]
        conflicts = [
            ConflictResolution(
                module=item.get("module", "repository"),
                static_view=item.get("static_view", "Static scan identified this area as important."),
                behavior_view=item.get("behavior_view", "Runtime behavior should be verified manually."),
                final_recommendation=item.get("final_recommendation", ""),
                judge_model=used_model,
                escalated=False,
                confidence=item.get("confidence", 0.7),
            )
            for item in ai_report.get("conflicts_resolved", [])[:3]
        ]
        agent_durations["reporter"] = int((time.time() - agent_started["reporter"]) * 1000)
        completed_timestamp = int(time.time())
        total_time_ms = int((time.time() - started_at) * 1000)
        html_report = ai_report.get("html_report") or f"""
        <div class="space-y-4">
          <h2>CodeMap 분석 결과: {path}</h2>
          <p>{ai_report.get('executive_summary', '')}</p>
          <h3>언어 구성</h3>
          <pre>{json.dumps(stats.get('languages', {}), ensure_ascii=False)}</pre>
        </div>
        """
        report = ReportJsonResponse(
            job_id=job_id,
            status="completed",
            completed_at=datetime.utcfromtimestamp(completed_timestamp).isoformat() + "Z",
            total_pipeline_ms=total_time_ms,
            recommendations=recommendations,
            conflicts_resolved=conflicts,
            community=CommunityMetrics(
                commits_per_week=0,
                avg_issue_response_hours=None,
                unique_contributors=0,
                top_contributors=[],
                is_degraded=True,
                degraded_reason="GitHub API community metrics are not connected yet; local source scan was used."
            ),
            html_report=html_report,
            file_heatmap=file_heatmap,
            guardrail_telemetry=GuardrailTelemetry(
                regex_blocked=[],
                semantic_filtered=[],
                regenerate_count=0,
                fallback_triggered=False,
                input_secrets_redacted=0,
                self_check_warnings=[]
            ),
            agent_durations=agent_durations,
            executive_summary=ai_report.get("executive_summary", f"실제 Git clone 후 {stats['file_count']}개 파일을 분석했습니다."),
            health_score=int(ai_report.get("health_score", 75)),
            key_strengths=ai_report.get("key_strengths", [])[:6],
            key_risks=ai_report.get("key_risks", [])[:6],
            summary_confidence=0.82
        ).dict()
        
        analyses_db[job_id] = report
        
        history_db.append({
            "job_id": job_id,
            "source": source,
            "path": path,
            "status": "completed",
            "created_at": completed_timestamp - int(total_time_ms / 1000),
            "completed_at": completed_timestamp,
            "total_pipeline_ms": total_time_ms,
            "error_message": None,
            "model_used": used_model,
            "force_refresh": False
        })
        
        await progress_bus.publish(job_id, {
            "type": "agent_completed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "reporter",
            "duration_ms": agent_durations["reporter"],
            "summary": "Real repository report generated."
        })
        await progress_bus.publish(job_id, {
            "type": "completed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "report_url": f"/api/report/{job_id}",
            "total_duration_ms": total_time_ms
        })
        
    except Exception as e:
        completed_timestamp = int(time.time())
        fallback_stats = locals().get("stats", {"file_count": 0, "languages": {}, "entrypoints": [], "risk_files": []})
        fallback_report = _fallback_report(job_id, path, fallback_stats, model, started_at)
        analyses_db[job_id] = fallback_report
        history_db.append({
            "job_id": job_id,
            "source": source,
            "path": path,
            "status": "failed",
            "created_at": int(started_at),
            "completed_at": completed_timestamp,
            "total_pipeline_ms": int((time.time() - started_at) * 1000),
            "error_message": str(e),
            "model_used": model,
            "force_refresh": False
        })
        await progress_bus.publish(job_id, {
            "type": "failed",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": "PIPELINE_ERROR",
            "message": str(e)
        })
    finally:
        if repo_dir:
            shutil.rmtree(repo_dir, ignore_errors=True)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repo(payload: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Start real async repository analysis for public GitHub URLs."""
    job_id = str(uuid.uuid4())
    created_time = datetime.utcnow().isoformat() + "Z"
    
    background_tasks.add_task(
        run_real_analysis_pipeline,
        job_id,
        payload.path,
        payload.source,
        payload.model or "auto"
    )
    
    return AnalyzeResponse(
        job_id=job_id,
        status="queued",
        created_at=created_time,
        ws_url=f"/ws/progress/{job_id}" # Resolved at frontend via buildWsUrl
    )


@router.get("/analyses")
async def get_analyses(limit: int = 30):
    """Return historical jobs (sorted by newest)."""
    sorted_history = sorted(history_db, key=lambda x: x["created_at"], reverse=True)
    return {"items": sorted_history[:limit]}


@router.get("/report/{job_id}")
async def get_report(job_id: str, format: str = Query("json", regex="^(json|html)$")):
    """Get report output as JSON structure or raw HTML text."""
    if job_id not in analyses_db:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    report = analyses_db[job_id]
    if format == "html":
        return report.get("html_report") or "<div>No HTML report content available</div>"
    
    return report


@router.post("/chat", response_model=ChatResponse)
async def chat_with_project(payload: ChatRequest):
    """Answer project questions using the latest analysis report as context."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    context = _compact_report_context(payload.job_id, payload.repo_path)
    system_prompt = (
        "You are CodeMap AI's project copilot inside an analysis dashboard. "
        "Answer in Korean by default. Be concise, practical, and grounded in the supplied repository analysis context. "
        "If the context is mock or incomplete, say so clearly and separate confirmed facts from inferences."
    )
    provider_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Repository analysis context:\n{context}"},
    ]
    for item in payload.messages[-8:]:
        if item.role in {"user", "assistant"} and item.content.strip():
            provider_messages.append({"role": item.role, "content": item.content.strip()[:2000]})
    provider_messages.append({"role": "user", "content": user_message})

    try:
        answer, model = await asyncio.to_thread(_call_chat_provider, provider_messages)
        return ChatResponse(answer=answer, model=model, used_context=bool(context))
    except Exception:
        return ChatResponse(
            answer=_fallback_chat_answer(user_message, context),
            model="fallback",
            used_context=bool(context),
        )
