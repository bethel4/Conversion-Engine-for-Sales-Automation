from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def health():
    return {"status": "running"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("Incoming webhook:", data)

    return {"status": "received"}