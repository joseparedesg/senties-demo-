"""
Orkesta Fianzas — Demo para Senties Chauvet
============================================

FastAPI backend con:
  - Login básico (roles: admin, operativo, ejecutivo)
  - 4 dashboards con chat persistente lateral
  - Chat conversacional contextual con Claude Sonnet

Run: uvicorn app.main:app --reload --port 8000
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request, Form, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.services.db import get_db
from app.services import queries, chat

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Orkesta-Senties Chauvet")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "orkesta-demo-secret-key-2026"))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ============================================================
# USUARIOS DE DEMO
# ============================================================

DEMO_USERS = {
    "diego": {"password": "senties2026", "role": "admin", "nombre": "Diego Senties", "cartera": None},
    "marlene": {"password": "senties2026", "role": "operativo", "nombre": "Marlene Barrera", "cartera": None},
    "alfonso": {"password": "senties2026", "role": "ejecutivo", "nombre": "Alfonso Vázquez", "cartera": "AVAZQUEZ5274"},
}


def get_current_user(request: Request):
    user_key = request.session.get("user")
    if not user_key or user_key not in DEMO_USERS:
        return None
    user = DEMO_USERS[user_key].copy()
    user["key"] = user_key
    return user


def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        return None
    return user


# ============================================================
# LOGIN / LOGOUT
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard/salud", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in DEMO_USERS and DEMO_USERS[username]["password"] == password:
        request.session["user"] = username
        return RedirectResponse(url="/dashboard/salud", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Usuario o contraseña incorrectos"})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ============================================================
# DASHBOARDS — Salud es el default
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_default(request: Request):
    return RedirectResponse(url="/dashboard/salud", status_code=302)


@app.get("/dashboard/salud", response_class=HTMLResponse)
async def dashboard_salud(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    data = queries.dashboard_salud(db)
    db.close()
    return templates.TemplateResponse("dashboard_salud.html", {"request": request, "user": user, "data": data})


@app.get("/dashboard/pipeline", response_class=HTMLResponse)
async def dashboard_pipeline(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    data = queries.dashboard_pipeline(db)
    db.close()
    return templates.TemplateResponse("dashboard_pipeline.html", {"request": request, "user": user, "data": data})


@app.get("/dashboard/cartera", response_class=HTMLResponse)
async def dashboard_cartera(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    ejecutivo_filter = user.get("cartera") if user["role"] == "ejecutivo" else None
    data = queries.dashboard_cartera(db, ejecutivo_filter)
    db.close()
    return templates.TemplateResponse("dashboard_cartera.html", {"request": request, "user": user, "data": data})


@app.get("/dashboard/cobranza", response_class=HTMLResponse)
async def dashboard_cobranza(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    data = queries.dashboard_cobranza(db)
    db.close()
    return templates.TemplateResponse("dashboard_cobranza.html", {"request": request, "user": user, "data": data})


# ============================================================
# CHAT API
# ============================================================

@app.post("/api/chat")
async def chat_endpoint(request: Request, message: str = Form(...), module_context: str = Form("global")):
    user = require_login(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    try:
        response = chat.ask(message, module_context=module_context)
        return JSONResponse({"response": response})
    except Exception as e:
        import traceback
        print(f"[/api/chat] Error inesperado: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return JSONResponse({
            "response": f"Ocurrió un error procesando tu pregunta ({type(e).__name__}). Prueba otra o revisa los logs del servidor."
        })


# ============================================================
# HEALTH CHECK (Railway)
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok", "service": "orkesta-senties-chauvet"}
