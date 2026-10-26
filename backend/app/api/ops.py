from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.security import require_api_key
from app.agent.alert_agent import analyze_alert
router = APIRouter(prefix="/ops", tags=["ops"], dependencies=[Depends(require_api_key)])
class AlertIn(BaseModel):
    alert: str
    logs: str = ""
    top_k: int = 3
@router.post("/analyze-alert")
async def analyze(body: AlertIn):
    result = await analyze_alert(body.alert, body.logs, body.top_k)
    return result
