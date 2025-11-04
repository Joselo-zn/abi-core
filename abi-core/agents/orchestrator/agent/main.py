# main.py
import os, json, logging, threading
from pathlib import Path
import uvicorn
from a2a.types import AgentCard
from agent.orchestrator import AbiOrchestratorAgent
from agent.web_interface import OrchestratorWebinterface
from common.a2a_server import start_server

logger = logging.getLogger(__name__)

def orchestrator_factory(agent_card_path: str | Path):
    p = Path(agent_card_path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    agent_card = AgentCard(**data)
    if agent_card.name != "Abi Orchestrator Agent":
        msg = f"Unexpected AgentCard name: {agent_card.name!r}"
        logger.error(msg)
        raise ValueError(msg)

    orchestrator_instance = AbiOrchestratorAgent()

    def start_web_server_interface():
        web_interface = OrchestratorWebinterface(orchestrator_instance)
        logger.info("[🚀] Starting Web Server at 0.0.0.0:8083")
        uvicorn.run(web_interface.app, host="0.0.0.0", port=8083)

    web_thread = threading.Thread(target=start_web_server_interface, daemon=True)
    web_thread.start()
    return orchestrator_instance

if __name__ == "__main__":
    agent_card_env = os.getenv("AGENT_CARD")
    if not agent_card_env:
        raise RuntimeError("[X] AGENT_CARD not defined!")

    agent = orchestrator_factory(agent_card_env)
    start_server("0.0.0.0", 8002, agent_card_env, agent)
