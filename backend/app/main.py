from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.routers import campaigns, sessions, people, locations, factions, rolls

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

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(campaigns.router)
app.include_router(sessions.router)
app.include_router(people.router)
app.include_router(locations.router)
app.include_router(factions.router)
app.include_router(rolls.router)