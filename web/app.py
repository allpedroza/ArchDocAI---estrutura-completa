"""
ArchDocAI Web Interface - FastAPI backend + simple HTML frontend.
Analyzes projects directly from a Git URL (shallow clone, no zip needed).

Fixes applied:
- API key never written to os.environ (thread-safe per-request config)
- Analysis runs in a background thread (non-blocking)
- Job store with polling endpoint (/api/status/{job_id})
- Automatic cleanup of output folders older than 24h
"""

import shutil
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# In-memory job store (thread-safe)
# ---------------------------------------------------------------------------

class JobStore:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "status": "queued",
                "step": "Aguardando inicio...",
                "result": None,
                "error": None,
                "created_at": datetime.utcnow(),
            }

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return dict(self._jobs[job_id]) if job_id in self._jobs else None

    def purge_old(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0
        with self._lock:
            stale = [jid for jid, j in self._jobs.items() if j["created_at"] < cutoff]
            for jid in stale:
                del self._jobs[jid]
                removed += 1
        return removed


_jobs = JobStore()


# ---------------------------------------------------------------------------
# Output folder cleanup
# ---------------------------------------------------------------------------

def cleanup_old_output(output_root: Path, max_age_hours: int = 24) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    for folder in output_root.iterdir():
        if not folder.is_dir():
            continue
        try:
            mtime = datetime.utcfromtimestamp(folder.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            continue


# ---------------------------------------------------------------------------
# Background analysis worker
# ---------------------------------------------------------------------------

def _run_analysis(
    job_id: str,
    provider: str,
    api_key: str,
    model: str,
    language: str,
    git_url: str,
    git_branch: str,
    project_name: str,
    output_root: Path,
) -> None:
    tmp_dir = tempfile.mkdtemp(prefix="archdoc_")
    try:
        _jobs.update(job_id, status="running", step="Clonando repositorio...")

        clone_dir = Path(tmp_dir) / "repo"
        cmd = ["git", "clone", "--depth=1", "--single-branch"]
        if git_branch.strip():
            cmd += ["--branch", git_branch.strip()]
        cmd += [git_url.strip(), str(clone_dir)]

        result_clone = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result_clone.returncode != 0:
            raise RuntimeError(f"Git clone falhou: {result_clone.stderr.strip()}")

        _jobs.update(job_id, step="Escaneando arquivos do projeto...")

        project_root = clone_dir
        entries = [e for e in clone_dir.iterdir() if not e.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            project_root = entries[0]

        inferred_name = (
            project_name.strip()
            or Path(git_url.rstrip("/")).stem.replace("-", " ").replace("_", " ").title()
        )

        output_dir_run = output_root / job_id
        output_dir_run.mkdir(parents=True, exist_ok=True)

        # Thread-safe: LLMConfig built locally, never touches os.environ
        from src.ingestion import ProjectContext
        from src.analysis import LLMClient, ArchitectureAnalyzer, DiagramGenerator
        from src.analysis.llm_client import LLMConfig
        from src.output import DocxGenerator, PdfGenerator

        config = LLMConfig(provider=provider, api_key=api_key, model=model)  # type: ignore
        client = LLMClient(config=config)

        ctx = ProjectContext.from_path(str(project_root), project_name=inferred_name)
        summary = ctx.summary()

        _jobs.update(job_id, step=f"Analisando {summary['total_files']} arquivos com LLM...")

        analyzer = ArchitectureAnalyzer(client=client, language=language)
        analysis = analyzer.analyze(ctx)

        _jobs.update(job_id, step="Gerando diagrama...")
        diagram_gen = DiagramGenerator(output_dir=str(output_dir_run))
        diagram_path = diagram_gen.generate_png(analysis)
        mermaid = diagram_gen.generate_mermaid(analysis)

        _jobs.update(job_id, step="Gerando documentos (.docx e PDF)...")
        docx_path = DocxGenerator(output_dir=str(output_dir_run), language=language).generate(
            analysis, diagram_path=diagram_path
        )
        pdf_path = PdfGenerator(output_dir=str(output_dir_run), language=language).generate(
            analysis, diagram_path=diagram_path
        )

        def rel(p: str) -> str:
            return "/" + str(Path(p).relative_to("."))

        _jobs.update(
            job_id,
            status="done",
            step="Concluido.",
            result={
                "project_name": analysis.project_name,
                "description": analysis.description,
                "layers": analysis.layers,
                "tech_stack": analysis.tech_stack,
                "good_practices": analysis.good_practices,
                "improvement_points": analysis.improvement_points,
                "validation_questions": analysis.validation_questions,
                "mermaid": mermaid,
                "files_scanned": summary["total_files"],
                "files": {
                    "diagram": rel(diagram_path),
                    "docx": rel(docx_path),
                    "pdf": rel(pdf_path),
                },
            },
        )

    except Exception as exc:
        _jobs.update(job_id, status="error", step="Erro.", error=str(exc))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(title="ArchDocAI", version="1.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    output_root = Path("./output")
    output_root.mkdir(exist_ok=True)
    app.mount("/output", StaticFiles(directory=str(output_root)), name="output")

    @app.on_event("startup")
    async def startup():
        cleanup_old_output(output_root)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = Path(__file__).parent / "templates" / "index.html"
        return HTMLResponse(content=html_path.read_text())

    @app.post("/api/analyze")
    async def analyze(
        provider: str = Form(...),
        api_key: str = Form(...),
        model: str = Form(...),
        language: str = Form("pt"),
        git_url: str = Form(...),
        git_branch: str = Form(""),
        project_name: str = Form(""),
    ):
        if provider not in ("openai", "anthropic", "custom"):
            raise HTTPException(400, "provider deve ser openai, anthropic ou custom")
        if not git_url.strip():
            raise HTTPException(400, "git_url e obrigatorio")

        # Cleanup old jobs/output on each new request (cheap O(n) scan)
        _jobs.purge_old()
        cleanup_old_output(output_root)

        job_id = uuid.uuid4().hex
        _jobs.create(job_id)

        thread = threading.Thread(
            target=_run_analysis,
            args=(job_id, provider, api_key, model, language, git_url, git_branch, project_name, output_root),
            daemon=True,
        )
        thread.start()

        return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)

    @app.get("/api/status/{job_id}")
    async def status(job_id: str):
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job nao encontrado")

        # Remove non-serializable fields
        job.pop("created_at", None)
        return JSONResponse(job)

    return app
