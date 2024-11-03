import asyncio
import os
from fastapi import FastAPI, WebSocket
import logging
from app.api.models import WebSocketManager
from app.cache.models import CacheManager, PubSubManager
from app.db.models import DbManager
from contextlib import asynccontextmanager

cache_manager = CacheManager()
db_manager = DbManager()
pubsub_manager = PubSubManager()

WEBSOCKET_TIMEOUT = os.getenv("WEBSOCKET_TIMEOUT", 360)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager to handle the lifespan of the FastAPI application.
    """
    try:
        await pubsub_manager.start()
        yield
    finally:
        await cache_manager.close()
        await db_manager.close()
        await pubsub_manager.close()


app = FastAPI(lifespan=lifespan)  # Added lifespan parameter here


@app.websocket("/{session_id}")
async def main_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for quiz moderators.
    Handles connection validation, message processing, and resource cleanup.
    """
    manager = WebSocketManager(
        websocket=websocket,
        session_id=session_id,
        cache_manager=cache_manager,
        db_manager=db_manager,
        pubsub_manager=pubsub_manager,
    )

    await websocket.accept()

    logger.info(f"Moderator connected to session {session_id}")

    if not await manager.validate_connection():
        return

    try:

        await manager.send_initial_payload()

        (pubsub_task, ws_task, heartbeat_task) = manager.manage_tasks()

        done, pending = await asyncio.wait(
            [pubsub_task, ws_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=WEBSOCKET_TIMEOUT,
        )

        for task in pending:
            # Cancel tasks if the connection is closed
            if websocket.client_state.value != 1:
                logger.info(
                    f"Closing task: {task} for session {session_id} for user {manager.user.user_id}"
                )
                task.cancel()
        for task in done:
            if task.exception():
                logger.error(
                    f"Task {task} for session {session_id} for user {manager.user.user_id} raised an exception: {task.exception()}"
                )

    except Exception as e:
        logger.error(f"Error in WS Manager: {e}")
    finally:
        logger.info(f"Moderator disconnected from session {session_id}")
        # Close the connection if it's not already closed
        if websocket.client_state.value != 2:
            await manager.close_connection()
