import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.routes import router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Code Review API...")
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    logger.info("LLM provider: %s", provider)

    if provider == "ollama":
        model = os.environ.get("OPENAI_MODEL", "qwen2.5-coder:7b")
        base = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        logger.info("Ollama endpoint: %s  model: %s", base, model)
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        logger.info("Gemini model: %s  key configured: %s", os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"), bool(key))
    elif provider == "openai_compat":
        logger.info("OpenAI-compat endpoint: %s  model: %s",
                    os.environ.get("OPENAI_BASE_URL", "(not set)"),
                    os.environ.get("OPENAI_MODEL", "(not set)"))
    else:  # anthropic
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if base_url:
            logger.info("Anthropic corporate gateway: %s", base_url)
        elif api_key:
            logger.info("Anthropic direct API key configured.")
        else:
            logger.warning("No AI connection configured! Set LLM_PROVIDER and related vars in .env")
    yield
    logger.info("Shutting down AI Code Review API.")


app = FastAPI(
    title="AI Code Review API",
    description="AI-powered code review using Claude. Upload code files and receive detailed analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend dev server and production origins
allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    return {
        "status": "ok",
        "llm_provider": provider,
    }
