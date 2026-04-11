"""
ArchDocAI Web Interface — FastAPI backend + simple HTML frontend.
"""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="ArchDocAI", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve static output files
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

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
        project_zip: UploadFile = File(...),
    ):
        """Accept a zipped project, analyze it, return paths to generated files."""
        # Validate provider
        if provider not in ("openai", "anthropic", "custom"):
            raise HTTPException(400, "provider must be openai, anthropic, or custom")

        tmp_dir = tempfile.mkdtemp(prefix="archdoc_")
        try:
            # Extract zip
            zip_path = Path(tmp_dir) / "project.zip"
            zip_path.write_bytes(await project_zip.read())

            extract_dir = Path(tmp_dir) / "project"
            shutil.unpack_archive(str(zip_path), str(extract_dir))

            # Find the actual project root (handle zip with single top-level folder)
            entries = list(extract_dir.iterdir())
            project_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else extract_dir

            output_dir_run = Path("./output") / Path(tmp_dir).name
            output_dir_run.mkdir(parents=True, exist_ok=True)

            # Set env vars for this request
            os.environ["LLM_PROVIDER"] = provider
            os.environ["LLM_API_KEY"] = api_key
            os.environ["LLM_MODEL"] = model

            from src.ingestion import ProjectContext
            from src.analysis import LLMClient, ArchitectureAnalyzer, DiagramGenerator
            from src.output import DocxGenerator, PdfGenerator

            ctx = ProjectContext.from_path(str(project_root))
            client = LLMClient.from_env()
            analyzer = ArchitectureAnalyzer(client=client, language=language)
            result = analyzer.analyze(ctx)

            diagram_gen = DiagramGenerator(output_dir=str(output_dir_run))
            diagram_path = diagram_gen.generate_png(result)
            mermaid = diagram_gen.generate_mermaid(result)

            docx_gen = DocxGenerator(output_dir=str(output_dir_run), language=language)
            docx_path = docx_gen.generate(result, diagram_path=diagram_path)

            pdf_gen = PdfGenerator(output_dir=str(output_dir_run), language=language)
            pdf_path = pdf_gen.generate(result, diagram_path=diagram_path)

            rel = lambda p: "/" + str(Path(p).relative_to("."))

            return JSONResponse({
                "status": "ok",
                "project_name": result.project_name,
                "description": result.description,
                "layers": result.layers,
                "tech_stack": result.tech_stack,
                "good_practices": result.good_practices,
                "improvement_points": result.improvement_points,
                "validation_questions": result.validation_questions,
                "mermaid": mermaid,
                "files": {
                    "diagram": rel(diagram_path),
                    "docx": rel(docx_path),
                    "pdf": rel(pdf_path),
                },
            })

        except Exception as e:
            raise HTTPException(500, str(e))
        finally:
            # Keep output, clean tmp source
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @app.post("/api/validate")
    async def validate_answers(payload: dict):
        """Accept user answers and regenerate docs with corrections."""
        # This would re-run analysis with corrections in a stateful session.
        # For now returns a placeholder — full implementation uses session storage.
        return JSONResponse({"status": "validation endpoint ready"})

    return app
