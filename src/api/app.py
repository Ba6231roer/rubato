from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .routes import configs
from .routes import testcases
from .websocket import websocket_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rubato Console API",
        description="HTTP API for Rubato configuration management and task execution",
        version="1.0.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(configs.router, prefix="/api")
    app.include_router(testcases.router, prefix="/api")
    app.include_router(websocket_router)
    
    web_dir = Path(__file__).parent.parent / "web"
    static_dir = web_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/")
    async def root():
        index_path = web_dir / "templates" / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Rubato Console API", "docs": "/docs"}
    
    return app
