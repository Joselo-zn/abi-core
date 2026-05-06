# web_interface.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio, json, time

from abi_core.common.utils import abi_logging
from abi_core.common.utils import yield_chunk_data


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
                yield b"event: ping\ndata: {}\n\n"
                try:
                    async for chunk in self.orchestrator_agent.stream(
                        query=query, context_id=context_id, task_id=task_id
                    ):
                    
                        yield yield_chunk_data(chunk)

                    yield b"event: done\ndata: {}\n\n"
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    abi_logging(f"Error en SSE generate_response: {e}", level="error")
                    yield (f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n").encode()
                    await asyncio.sleep(0.05)

            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
