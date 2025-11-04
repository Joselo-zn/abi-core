from agent.base_agent import BaseAgent
from agent.policy import evaluate_policy
from agent.semantics import enrich_input

class AbiAgent(BaseAgent):
    def handle_input(self, input_data):
        enriched = enrich_input(input_data)
        if not evaluate_policy(enriched):
            raise Exception(f"[{self.agent_name}] Policy rejected the input.")
        return self.process(enriched)

    def process(self, enriched_input):
        raise NotImplementedError("process() must be implemented by the subclass")
