import os
import logging
import secrets
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo_backend")

app = FastAPI()

# -----------------------------
# CORS Middleware (Safe)
# -----------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Environment Config
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")  # ONLY anon/public key
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

# -----------------------------
# Clients
# -----------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
logger.info("Neo L1.0 Engine Connected Successfully")

# -----------------------------
# System Prompt
# -----------------------------
SYSTEM_PROMPT = "You are Neo L1.0, an advanced reasoning AI..."

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {"status": "Online", "model": "Neo L1.0", "message": "API Live"}

# -----------------------------
# Get User Balance (Safe)
# -----------------------------
@app.get("/v1/user/balance")
def get_balance(api_key: str):
    response = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="API Key not found")
    return {"balance": response.data[0].get("token_balance", 0)}

# -----------------------------
# Generate New API Key (Server-side only)
# -----------------------------
@app.post("/v1/user/new-key")
def generate_key():
    new_key = "sig-live-" + secrets.token_urlsafe(16)
    supabase.table("users").insert({"api_key": new_key, "token_balance": 1000}).execute()
    return {"api_key": new_key, "balance": 1000}

# -----------------------------
# Chat Endpoint (Safe)
# -----------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")

    user_api_key = authorization.replace("Bearer ", "")

    # 1️⃣ Verify user balance
    response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="API Key not found")

    balance = response.data[0].get("token_balance", 0)
    if balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    # 2️⃣ Parse body
    body = await request.json()
    messages = body.get("messages", [])

    # 3️⃣ Call Cerebras safely
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            model="llama3.1-8b",
            temperature=0.4,
            top_p=0.9,
            stream=False
        )

        tokens_used = ai_response.usage.total_tokens
        new_balance = balance - tokens_used
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
        ai_response.model = "Neo-L1.0"

        return ai_response

    except Exception as e:
        logger.error(f"AI Engine Error: {e}")
        raise HTTPException(status_code=500, detail="AI Engine Failed")
