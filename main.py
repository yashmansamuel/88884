import os
import logging
import secrets
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# -----------------------------
# Logger Setup
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# -----------------------------
# CORS Middleware
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Config from environment
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

# -----------------------------
# Clients Init
# -----------------------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Signaturesi Backend: Neo L1.0 Engine Connected Successfully.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

# -----------------------------
# SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = "You are Neo L1.0, an advanced reasoning AI..."

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {"status": "Online", "brand": "Signaturesi", "model": "Neo L1.0", "message": "Neo L1.0 API is Live and Healthy"}

# -----------------------------
# Get User Balance
# -----------------------------
@app.get("/v1/user/balance")
def get_balance(api_key: str):
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="API Key not found")
        balance = response.data[0].get("token_balance", 0)
        return {"api_key": api_key, "balance": balance}
    except Exception as e:
        logger.error(f"Supabase Error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

# -----------------------------
# Generate New API Key
# -----------------------------
@app.post("/v1/user/new-key")
def generate_key():
    new_key = "sig-live-" + secrets.token_urlsafe(16)
    try:
        supabase.table("users").insert({"api_key": new_key, "token_balance": 1000}).execute()
        return {"api_key": new_key, "balance": 1000}
    except Exception as e:
        logger.error(f"Supabase Insert Error: {e}")
        raise HTTPException(status_code=500, detail="Cannot create new API key")

# -----------------------------
# Chat Endpoint
# -----------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")

    user_api_key = authorization.replace("Bearer ", "")

    # Fetch user balance
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="API Key not found")
        current_balance = response.data[0].get("token_balance", 0)
    except Exception as e:
        logger.error(f"Supabase Error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    body = await request.json()

    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
            model="llama3.1-8b",
            temperature=0.4,
            top_p=0.9,
            stream=False
        )

        tokens_used = ai_response.usage.total_tokens
        new_balance = current_balance - tokens_used

        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()

        ai_response.model = "Neo-L1.0"
        return ai_response

    except Exception as e:
        logger.error(f"Cerebras API Error: {e}")
        raise HTTPException(status_code=500, detail="AI Engine Failed")
