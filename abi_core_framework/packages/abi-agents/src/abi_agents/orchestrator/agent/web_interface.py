# web_interface.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio, json, time, logging

from abi_core.common.utils import abi_logging

logger = logging.getLogger(__name__)

class OrchestratorWebinterface:
    def __init__(self, orchestrator_agent):
        self.orchestrator_agent = orchestrator_agent
        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):
        @self.app.post("/stream")
        async def stream_query(request: dict):
            query = request.get("query")
            context_id = request.get("context_id", "web-session")
            task_id = request.get("task_id", f"task-{int(time.time())}")

            async def generate_response():
                # 1) Abrir el canal
                yield b"event: ping\ndata: {}\n\n"
                try:
                    # 2) Stream real del agente (DEBE ser async generator)
                    async for chunk in self.orchestrator_agent.stream(
                        query=query, context_id=context_id, task_id=task_id
                    ):
                        # Convert chunk to serializable format
                        try:
                            if hasattr(chunk, 'model_dump'):
                                chunk_data = chunk.model_dump()
                            elif hasattr(chunk, 'dict'):
                                chunk_data = chunk.dict()
                            elif hasattr(chunk, '__dict__'):
                                chunk_data = chunk.__dict__
                            else:
                                chunk_data = {"message": str(chunk), "type": type(chunk).__name__}

                            abi_logging(f"[DEBUG] Chunk received: {type(chunk).__name__} - {str(chunk)[:100]}...", level="debug")

                            yield (f"data: {json.dumps(chunk_data)}\n\n").encode()
                        except Exception as serialize_error:
                            error_data = {
                                "error": "Serialization failed",
                                "chunk_type": type(chunk).__name__,
                                "details": str(serialize_error)
                            }
                            yield (f"data: {json.dumps(error_data)}\n\n").encode()
                    # 3) Cierre normal
                    yield b"event: done\ndata: {}\n\n"
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # 4) Log + evento de error para que curl reciba "algo" antes del cierre
                    abi_logging(f"Error en SSE generate_response: {e}", level="error")
                    yield (f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n").encode()
                    await asyncio.sleep(0.05)

            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
