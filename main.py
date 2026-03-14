import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras
import secrets

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# App Init
# -----------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend can run anywhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Config
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")

# -----------------------------
# Clients Init
# -----------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
logger.info("Backend: Neo L1.0 Engine Connected Successfully.")

# -----------------------------
# SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = "You are Neo L1.0, an advanced reasoning AI..."

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {"status": "Online", "brand": "Signaturesi", "model": "Neo L1.0", "message": "API Live"}

# -----------------------------
# Get User Balance
# -----------------------------
@app.get("/v1/user/balance")
def get_balance(api_key: str):
    response = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=404, detail="API Key not found")
    return {"api_key": api_key, "balance": response.data[0].get("token_balance", 0)}

# -----------------------------
# Generate New API Key
# -----------------------------
@app.post("/v1/user/new-key")
def generate_key():
    new_key = "sig-live-" + secrets.token_urlsafe(16)
    supabase.table("users").insert({"api_key": new_key, "token_balance": 1000}).execute()
    return {"api_key": new_key, "balance": 1000}

# -----------------------------
# Chat Endpoint
# -----------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    user_api_key = authorization.replace("Bearer ", "")

    response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=401, detail="API Key not found")
    current_balance = response.data[0].get("token_balance", 0)
    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    body = await request.json()
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
