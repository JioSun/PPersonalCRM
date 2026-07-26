from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def greetings():
    return {"greetings": "Hello World"}

@app.get("/health")
async def health():
    return True
