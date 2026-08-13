"""
TG Web Client routes — full Telegram interface in browser
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter()


def get_user(request):
    from app import get_current_user
    return get_current_user(request)


@router.get("/tg", response_class=HTMLResponse)
async def tg_client(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    from tg_client import get_available_accounts, get_account_info
    
    phones = get_available_accounts()
    accounts = []
    for phone in phones:
        try:
            info = await get_account_info(phone)
        except Exception:
            info = None
        if info:
            info["phone"] = phone
            accounts.append(info)
        else:
            accounts.append({"phone": phone, "first_name": phone, "username": ""})
    
    return templates.TemplateResponse("tg_client.html", {
        "request": request,
        "user": user,
        "accounts": accounts,
        "active": "tg",
    })


@router.get("/api/tg/{phone}/dialogs")
async def api_dialogs(request: Request, phone: str):
    user = get_user(request)
    if not user:
        return JSONResponse({"error": "Auth"}, status_code=401)
    
    from tg_client import get_dialogs
    dialogs = await get_dialogs(f"+{phone}", limit=50)
    return JSONResponse(dialogs)


@router.get("/api/tg/{phone}/messages/{peer_id}")
async def api_messages(request: Request, phone: str, peer_id: int, peer_type: str = "user"):
    user = get_user(request)
    if not user:
        return JSONResponse({"error": "Auth"}, status_code=401)
    
    from tg_client import get_messages
    messages = await get_messages(f"+{phone}", peer_id, peer_type, limit=50)
    return JSONResponse(messages)


@router.post("/api/tg/{phone}/send/{peer_id}")
async def api_send(request: Request, phone: str, peer_id: int, text: str = Form(...)):
    user = get_user(request)
    if not user:
        return JSONResponse({"error": "Auth"}, status_code=401)
    
    from tg_client import send_message
    ok, err = await send_message(f"+{phone}", peer_id, text)
    return JSONResponse({"ok": ok, "error": err})


@router.post("/api/tg/{phone}/read/{peer_id}")
async def api_read(request: Request, phone: str, peer_id: int):
    user = get_user(request)
    if not user:
        return JSONResponse({"error": "Auth"}, status_code=401)
    
    from tg_client import mark_read
    ok = await mark_read(f"+{phone}", peer_id)
    return JSONResponse({"ok": ok})
