from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str

@app.post("/ask")
async def ask(request: PromptRequest):
    # Placeholder response
    return {"message": f"Received: {request.prompt}"}
