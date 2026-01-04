from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .api.routes import auth as auth_router
from .api.routes import users as users_router
from .api.routes import announcements as announcements_router
from .api.routes import tickets as tickets_router
from .api.routes import room_assessments as room_assessments_router

settings = get_settings()
app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(users_router.router, prefix="/api")
app.include_router(announcements_router.router, prefix="/api")
app.include_router(tickets_router.router, prefix="/api")
app.include_router(room_assessments_router.router, prefix="/api")

@app.get("/api/health")
def health():
    return {"status": "ok"}
