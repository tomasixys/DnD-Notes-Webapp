from fastapi import FastAPI
from fastapi import staticfiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.frontend import mount_frontend
from app.routers import campaigns, sessions, people, locations, factions, rolls

from app.app_paths import (
    get_app_data_dir,
    get_uploads_dir,
    get_campaign_images_dir,
)


def initialize_app_storage():
    get_app_data_dir()
    get_uploads_dir()
    get_campaign_images_dir()


app = FastAPI(title="Campaign Notes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/api/uploads",
    staticfiles.StaticFiles(directory=get_uploads_dir()),
    name="uploads",
)


@app.on_event("startup")
def on_startup():
    initialize_app_storage()
    create_db_and_tables()


app.include_router(campaigns.router)
app.include_router(sessions.router)
app.include_router(people.router)
app.include_router(locations.router)
app.include_router(factions.router)
app.include_router(rolls.router)

# Keep this after every API router. It contains the catch-all SPA route.
mount_frontend(app)
