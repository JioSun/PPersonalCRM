from fastapi import FastAPI, status, HTTPException

from backend.app.models.client import Client, ClientRead
from backend.app.api.routes import users

app = FastAPI(title="Secure API")
app.include_router(
    users.router,
)

@app.get("/")
async def greetings():
    return {"greetings": "Hello World"}

@app.get("/health")
async def health():
    return True

@app.post("auth/register")

@app.post("/client", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def client(new_client: Client):
    pass

