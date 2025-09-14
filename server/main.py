import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from enum import Enum


app = FastAPI(
    title="Whip API",
    version="1.0.0",
    description=(
        "Accepts REST API calls to push a `whip` command to a WebSocket client.\n\n"
        "WebSocket handshake: connect to /ws and include the token via\n"
        "Authorization: Bearer <secret> header.\n"
        "Use Authorization: Bearer <secret> on REST calls to target that connection."
    ),
)


class SideEnum(str, Enum):
    left = "left"
    right = "right"
    both = "both"


class WhipRequest(BaseModel):
    duration: int = Field(..., ge=1, le=60, description="Duration in seconds (1..60)")
    side: SideEnum = Field(
        default=SideEnum.both,
        description="Which side to apply the whip: left, right, or both",
    )


active_connections: Dict[str, WebSocket] = {}
connections_lock = asyncio.Lock()


async def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    return parts[1]


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/whip", status_code=202)
async def whip(payload: WhipRequest, token: str = Depends(get_bearer_token)):
    async with connections_lock:
        ws = active_connections.get(token)

    if ws is None:
        raise HTTPException(status_code=404, detail="No active WebSocket client for this token")

    msg = {
        "command": "whip",
        "duration": payload.duration,
        "side": payload.side.value,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await ws.send_text(json.dumps(msg))
    except Exception:
        # Assume the socket is dead and clean up mapping if needed
        async with connections_lock:
            if active_connections.get(token) is ws:
                active_connections.pop(token, None)
        # Spec defines 404 for no active WS client; treat failed send as 404
        raise HTTPException(status_code=404, detail="No active WebSocket client for this token")

    return JSONResponse({"status": "sent", "payload": msg}, status_code=202)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Extract token only from Authorization header
    token: Optional[str] = None

    auth = websocket.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        # Missing credentials
        await websocket.close(code=1008)
        return

    # Accept connection
    await websocket.accept()

    try:
        # Register connection
        async with connections_lock:
            active_connections[token] = websocket

        # Keep the connection open; we don't require client messages
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        async with connections_lock:
            if active_connections.get(token) is websocket:
                active_connections.pop(token, None)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "60606"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
