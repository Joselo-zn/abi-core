#!/usr/bin/env python3
"""
Example: Planner + Orchestrator Integration

This example demonstrates the complete workflow:
1. User sends query to Planner
2. Planner asks clarification questions (if needed)
3. User provides answers
4. Planner creates execution plan
5. Orchestrator receives plan and checks agent health
6. Orchestrator executes workflow
7. Orchestrator synthesizes results

Requirements:
- Planner Agent running on port 11437
- Orchestrator Agent running on port 8002
- Semantic Layer (MCP server) running on port 10100
- At least one worker agent available
"""

import asyncio
import json
import httpx
from typing import AsyncIterator


class PlannerOrchestratorDemo:
    def __init__(
        self,
        planner_url: str = "http://localhost:11437",
        orchestrator_url: str = "http://localhost:8002"
    ):
        self.planner_url = planner_url
        self.orchestrator_url = orchestrator_url
        self.session_id = "demo-session-001"
        self.task_id = "demo-task-001"
    
    async def send_to_planner(self, query: str) -> AsyncIterator[dict]:
        """Send query to Planner and stream responses"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": query}],
                    "messageId": self.task_id,
                    "contextId": self.session_id
                }
            }
            
            print(f"\n📤 Sending to Planner: {query}")
            
            async with client.stream(
                "POST",
                f"{self.planner_url}/stream",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        yield data
    
    async def send_to_orchestrator(self, plan: dict) -> AsyncIterator[dict]:
        """Send plan to Orchestrator and stream execution"""
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Wrap plan in expected format
            plan_json = json.dumps({"plan": plan})
            
            payload = {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": plan_json}],
                    "messageId": self.task_id,
                    "contextId": self.session_id
                }
            }
            
            print(f"\n📤 Sending plan to Orchestrator")
            
            async with client.stream(
                "POST",
                f"{self.orchestrator_url}/stream",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        yield data
    
    async def run_workflow(self, user_query: str):
        """Run complete workflow from query to results"""
        
        print("=" * 80)
        print("🚀 PLANNER + ORCHESTRATOR INTEGRATION DEMO")
        print("=" * 80)
        
        # Step 1: Send query to Planner
        print("\n📋 STEP 1: Planning Phase")
        print("-" * 80)
        
        plan = None
        needs_clarification = False
        questions = []
        
        async for response in self.send_to_planner(user_query):
            if "root" in response and "result" in response["root"]:
                result = response["root"]["result"]
                
                # Check for text content
                if "artifact" in result:
                    artifact = result["artifact"]
                    if "parts" in artifact:
                        for part in artifact["parts"]:
                            if part.get("kind") == "text":
                                print(f"\n💬 Planner: {part['text']}")
                
                # Check metadata for status
                if "metadata" in result:
                    metadata = result["metadata"]
                    
                    if metadata.get("status") == "needs_clarification":
                        needs_clarification = True
                        questions = metadata.get("questions", [])
                        print("\n❓ Planner needs clarification")
                    
                    elif metadata.get("status") == "ready":
                        # Extract plan from content
                        if "artifact" in result and "parts" in result["artifact"]:
                            for part in result["artifact"]["parts"]:
                                if part.get("kind") == "data":
                                    plan = part.get("data")
                                    break
        
        # Step 2: Handle clarification if needed
        if needs_clarification:
            print("\n📝 STEP 2: Clarification Phase")
            print("-" * 80)
            
            # In a real scenario, you'd prompt the user
            # For demo, we'll provide mock answers
            print("\n❓ Questions from Planner:")
            for q in questions:
                print(f"  - {q['question']}")
                if q.get('options'):
                    print(f"    Options: {', '.join(q['options'])}")
            
            # Mock answer (in real scenario, get from user input)
            mock_answer = f"{questions[0]['id']}: {questions[0]['options'][0]}"
            print(f"\n✅ Mock answer: {mock_answer}")
            
            # Send answer back to Planner
            async for response in self.send_to_planner(mock_answer):
                if "root" in response and "result" in response["root"]:
                    result = response["root"]["result"]
                    
                    if "metadata" in result and result["metadata"].get("status") == "ready":
                        if "artifact" in result and "parts" in result["artifact"]:
                            for part in result["artifact"]["parts"]:
                                if part.get("kind") == "data":
                                    plan = part.get("data")
                                    break
        
        # Step 3: Send plan to Orchestrator
        if plan:
            print("\n🎯 STEP 3: Orchestration Phase")
            print("-" * 80)
            print(f"\n📋 Plan Summary:")
            print(f"  Objective: {plan.get('objective', 'N/A')}")
            print(f"  Tasks: {len(plan.get('tasks', []))}")
            print(f"  Strategy: {plan.get('execution_strategy', 'N/A')}")
            
            # Execute via Orchestrator
            async for response in self.send_to_orchestrator(plan):
                if "root" in response and "result" in response["root"]:
                    result = response["root"]["result"]
                    
                    # Print updates
                    if "artifact" in result and "parts" in result["artifact"]:
                        for part in result["artifact"]["parts"]:
                            if part.get("kind") == "text":
                                print(f"\n🤖 Orchestrator: {part['text']}")
                    
                    # Check for completion
                    if "metadata" in result:
                        metadata = result["metadata"]
                        
                        if metadata.get("status") == "on_hold":
                            print("\n⏸️ Workflow on hold - agents unavailable")
                            unavailable = metadata.get("unavailable_agents", [])
                            for ua in unavailable:
                                print(f"  ❌ {ua['agent']}: {ua['last_status']}")
                        
                        elif metadata.get("status") == "completed":
                            print("\n✅ Workflow completed successfully!")
                            print(f"  Total results: {metadata.get('total_results', 0)}")
        else:
            print("\n❌ No plan generated")
        
        print("\n" + "=" * 80)
        print("✅ DEMO COMPLETED")
        print("=" * 80)


async def main():
    """Run the demo"""
    demo = PlannerOrchestratorDemo()
    
    # Example queries to try:
    queries = [
        "Analyze the latest market trends and create a summary report",
        "Research competitor pricing and recommend our pricing strategy",
        "Monitor system health and alert if any issues are detected"
    ]
    
    # Run first query
    await demo.run_workflow(queries[0])


if __name__ == "__main__":
    asyncio.run(main())
