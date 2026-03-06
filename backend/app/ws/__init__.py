from fastapi import APIRouter

from app.ws.audio_handler import router as audio_router
from app.ws.handler import router as ws_handler_router
from app.ws.roleplay_handler import router as roleplay_ws_router

router = APIRouter()
router.include_router(ws_handler_router)
router.include_router(audio_router)
router.include_router(roleplay_ws_router)
