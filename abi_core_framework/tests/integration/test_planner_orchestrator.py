"""
Integration tests for Planner + Orchestrator workflow

These tests verify the complete integration between Planner and Orchestrator agents.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Import the agents
import sys
sys.path.insert(0, 'src/abi_core')

from abi_agents.planner.agent.planner import AbiPlannerAgent
from abi_agents.orchestrator.agent.orchestrator import AbiOrchestratorAgent


class TestPlannerOrchestratorIntegration:
    """Test suite for Planner + Orchestrator integration"""
    
    @pytest.fixture
    async def planner_agent(self):
        """Create Planner agent instance"""
        with patch('abi_agents.planner.agent.planner.ChatOllama'):
            agent = AbiPlannerAgent()
            return agent
    
    @pytest.fixture
    async def orchestrator_agent(self):
        """Create Orchestrator agent instance"""
        with patch('abi_agents.orchestrator.agent.orchestrator.ChatOllama'):
            agent = AbiOrchestratorAgent()
            return agent
    
    @pytest.mark.asyncio
    async def test_planner_generates_valid_plan(self, planner_agent):
        """Test that Planner generates a valid plan structure"""
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "status": "ready",
            "plan": {
                "objective": "Test objective",
                "tasks": [
                    {
                        "task_id": "task_1",
                        "description": "Test task",
                        "agent_count": 1,
                        "dependencies": [],
                        "requires_clarification": False
                    }
                ],
                "execution_strategy": "sequential"
            }
        })
        
        planner_agent.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # Mock semantic tools
        with patch('common.semantic_tools.tool_find_agent', new_callable=AsyncMock) as mock_find:
            mock_agent = MagicMock()
            mock_agent.dict.return_value = {
                "name": "test_agent",
                "id": "agent://test_agent",
                "url": "http://test:8000"
            }
            mock_find.return_value = mock_agent
            
            # Generate plan
            result = await planner_agent.decompose_and_assign(
                "Test query",
                "session-001"
            )
            
            # Verify plan structure
            assert result["status"] == "ready"
            assert "plan" in result
            assert "tasks" in result["plan"]
            assert len(result["plan"]["tasks"]) > 0
            
            # Verify task structure
            task = result["plan"]["tasks"][0]
            assert "task_id" in task
            assert "description" in task
            assert "agents" in task
    
    @pytest.mark.asyncio
    async def test_planner_asks_clarification(self, planner_agent):
        """Test that Planner asks clarification when needed"""
        
        # Mock LLM response with clarification needed
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "status": "needs_clarification",
            "questions": [
                {
                    "id": "q1",
                    "question": "What time range?",
                    "type": "required",
                    "options": ["7 days", "30 days"]
                }
            ],
            "partial_understanding": "User wants analysis"
        })
        
        planner_agent.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # Generate plan
        result = await planner_agent.decompose_and_assign(
            "Analyze data",
            "session-001"
        )
        
        # Verify clarification request
        assert result["status"] == "needs_clarification"
        assert "questions" in result
        assert len(result["questions"]) > 0
        
        # Verify question structure
        question = result["questions"][0]
        assert "id" in question
        assert "question" in question
        assert "type" in question
    
    @pytest.mark.asyncio
    async def test_orchestrator_checks_agent_health(self, orchestrator_agent):
        """Test that Orchestrator checks agent health before execution"""
        
        plan = {
            "objective": "Test",
            "tasks": [
                {
                    "task_id": "task_1",
                    "description": "Test task",
                    "agents": [
                        {
                            "name": "test_agent",
                            "id": "agent://test_agent"
                        }
                    ]
                }
            ]
        }
        
        # Mock health check - healthy agent
        with patch('common.semantic_tools.tool_check_agent_health', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "healthy"}
            
            result = await orchestrator_agent.check_agents_availability(plan, max_retries=1)
            
            assert result["all_available"] is True
            assert len(result["unavailable"]) == 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_unavailable_agents(self, orchestrator_agent):
        """Test that Orchestrator handles unavailable agents correctly"""
        
        plan = {
            "objective": "Test",
            "tasks": [
                {
                    "task_id": "task_1",
                    "description": "Test task",
                    "agents": [
                        {
                            "name": "unavailable_agent",
                            "id": "agent://unavailable_agent"
                        }
                    ]
                }
            ]
        }
        
        # Mock health check - unhealthy agent
        with patch('common.semantic_tools.tool_check_agent_health', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "unhealthy"}
            
            result = await orchestrator_agent.check_agents_availability(plan, max_retries=2)
            
            assert result["all_available"] is False
            assert len(result["unavailable"]) == 1
            assert result["unavailable"][0]["agent"] == "unavailable_agent"
    
    @pytest.mark.asyncio
    async def test_orchestrator_creates_workflow_from_plan(self, orchestrator_agent):
        """Test that Orchestrator creates valid workflow from plan"""
        
        plan = {
            "objective": "Test workflow",
            "tasks": [
                {
                    "task_id": "task_1",
                    "description": "First task",
                    "agents": [{"name": "agent1"}],
                    "dependencies": [],
                    "requires_clarification": False
                },
                {
                    "task_id": "task_2",
                    "description": "Second task",
                    "agents": [{"name": "agent2"}],
                    "dependencies": ["task_1"],
                    "requires_clarification": False
                }
            ],
            "execution_strategy": "sequential"
        }
        
        workflow = orchestrator_agent.create_workflow_from_plan(
            plan,
            "context-001",
            "task-001"
        )
        
        # Verify workflow structure
        assert workflow is not None
        assert len(workflow.nodes) == 2
        
        # Verify nodes have correct attributes
        for node in workflow.nodes.values():
            assert node.task is not None
            assert node.agents is not None
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, planner_agent, orchestrator_agent):
        """Test complete end-to-end workflow"""
        
        # Step 1: Planner generates plan
        mock_plan_response = MagicMock()
        mock_plan_response.content = json.dumps({
            "status": "ready",
            "plan": {
                "objective": "Complete test workflow",
                "tasks": [
                    {
                        "task_id": "task_1",
                        "description": "Execute test",
                        "agent_count": 1,
                        "dependencies": [],
                        "requires_clarification": False
                    }
                ],
                "execution_strategy": "sequential"
            }
        })
        
        planner_agent.llm.ainvoke = AsyncMock(return_value=mock_plan_response)
        
        with patch('common.semantic_tools.tool_find_agent', new_callable=AsyncMock) as mock_find:
            mock_agent = MagicMock()
            mock_agent.dict.return_value = {
                "name": "test_agent",
                "id": "agent://test_agent",
                "url": "http://test:8000"
            }
            mock_find.return_value = mock_agent
            
            # Generate plan
            plan_result = await planner_agent.decompose_and_assign(
                "Execute test workflow",
                "session-001"
            )
            
            assert plan_result["status"] == "ready"
            plan = plan_result["plan"]
            
            # Step 2: Orchestrator checks health
            with patch('common.semantic_tools.tool_check_agent_health', new_callable=AsyncMock) as mock_health:
                mock_health.return_value = {"status": "healthy"}
                
                health_result = await orchestrator_agent.check_agents_availability(plan)
                
                assert health_result["all_available"] is True
                
                # Step 3: Orchestrator creates workflow
                workflow = orchestrator_agent.create_workflow_from_plan(
                    plan,
                    "context-001",
                    "task-001"
                )
                
                assert workflow is not None
                assert len(workflow.nodes) == len(plan["tasks"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
