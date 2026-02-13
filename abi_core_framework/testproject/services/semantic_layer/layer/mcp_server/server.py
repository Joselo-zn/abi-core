import json
import uuid
import numpy as np

from typing import Optional

from starlette.responses import JSONResponse
from starlette.requests import Request
from fastmcp import FastMCP

from abi_core.common.utils import abi_logging
from abi_core.semantic.semantic_access_validator import validate_semantic_access
from layer.embedding_mesh.api import attach_embedding_mesh_routes
from layer.embedding_mesh.embeddings_abi import embed_one, build_agent_card_embeddings
from layer.embedding_mesh.weaviate_store import search_agent_cards

# Import configuration
from config import config

MODEL = config.EMBEDDING_MODEL


def serve(host, port, transport):
    """Start the MCP Agent Card Server
    Args:
        host: Hostname or IP address to bind the Server to.
        port: Port number to bind the server to.
    """
    abi_logging('[🔄] Starting Agents Cards MCP Server')
    mcp = FastMCP('agent-cards', host=host, port=port)

    # Initialize Weaviate collections
    from layer.embedding_mesh.weaviate_store import ensure_collections, upsert_agent_cards, get_existing_agent_card_uris
    
    abi_logging('[🗄️] Ensuring Weaviate collections exist...')
    ensure_collections()
    abi_logging('[✅] Weaviate collections ready')
    
    # Build embeddings for agent cards
    df = build_agent_card_embeddings()
    
    # Persist embeddings to Weaviate (only new/updated cards)
    if df is not None and not df.empty:
        # Get existing cards from Weaviate
        existing_uris = get_existing_agent_card_uris()
        abi_logging(f'[📊] Found {len(existing_uris)} existing agent cards in Weaviate')
        
        # Filter to only new or updated cards
        items = []
        skipped = 0
        for idx, row in df.iterrows():
            card_uri = row['card_uri']
            
            # Check if card already exists
            if card_uri in existing_uris:
                skipped += 1
                continue
            
            agent_card = row['agent_card']
            # Generate deterministic UUID from card URI
            card_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, card_uri))
            
            items.append({
                "id": card_uuid,
                "text": json.dumps(agent_card),  # Store full card as text
                "uri": card_uri,
                "metadata": {
                    "name": agent_card.get('name', ''),
                    "description": agent_card.get('description', ''),
                    "supportedTasks": agent_card.get('supportedTasks', [])
                },
                "vector": row['card_embeddings'],
                "origin": "agent_card"
            })
        
        if items:
            abi_logging(f'[📤] Upserting {len(items)} new agent cards to Weaviate...')
            upsert_agent_cards(items)
            abi_logging(f'[✅] Successfully upserted {len(items)} agent cards')
        
        if skipped > 0:
            abi_logging(f'[⏭️] Skipped {skipped} existing agent cards')
        
        if not items and not skipped:
            abi_logging('[⚠️] No agent cards to upsert')
    else:
        abi_logging('[⚠️] No agent cards found')

    @mcp.tool(
        name='find_agent',
        description='Finds the most adecuate agent cards base in natural laguage query string.'
    )
    @validate_semantic_access
    async def find_agent(query: str, _request_context: dict = None) -> Optional[dict]:
        """Finds the most relevant Agent Card based on semantic similarity with a natural language query.
        
        Args:
            query (str): Natural language string describing the desired Agent.
        
        Returns:
            dict | None:
                - JSON dictionary of the most relevant Agent Card.
                - None if no matching Agent Card is found.
        
        Search Logic:
            1. Compute embedding for the query using `embed_one()` (local embedding model).
            2. Compute dot product similarity between query embedding and all cached Agent Card embeddings.
            3. Return the Agent Card with the highest similarity score.
        
        Note:
            - Relies on `build_agent_card_embeddings()` having been called at least once.
            - In the robust version, this will query Weaviate instead of in-memory cache.
        """

        if df is None or df.empty:
            abi_logging("[⚠️] No Agent Cards available for search.")
            return None

        query_embedding = embed_one(query)
        resultados_completos = search_agent_cards(query_vector=query_embedding, top_k=1) 

        if resultados_completos:
            # Parse the agent card from JSON text
            try:
                best_match = json.loads(resultados_completos[0]["text"])
                abi_logging(f"[🎯] Best match: {best_match.get('name', 'Unknown')} (score: {resultados_completos[0].get('score', 0):.2f})")
                abi_logging(f"✅ Access validated - returning agent: {best_match.get('name', 'Unknown')}")
                return best_match
            except json.JSONDecodeError as e:
                abi_logging(f"[❌] Error parsing agent card JSON: {e}")
                return None
        else:
            abi_logging("[⚠️] No matching agent found")
            return None
    
    @mcp.tool(
        name='recommend_agents',
        description='Recommends multiple agents for a complex task based on semantic similarity'
    )
    @validate_semantic_access
    async def recommend_agents(
        task_description: str,
        max_agents: int = 3,
        _request_context: dict = None
    ) -> list[dict]:
        """Recommend multiple agents for a complex task.
        
        Args:
            task_description (str): Description of the task requiring multiple agents
            max_agents (int): Maximum number of agents to recommend (default: 3)
        
        Returns:
            list[dict]: List of recommended agents with relevance scores
        """
        abi_logging(f"[🔍] Recommending up to {max_agents} agents for: {task_description}")
        
        if df is None or df.empty:
            abi_logging("[⚠️] No Agent Cards available for recommendations")
            return []
        
        query_embedding = embed_one(task_description)
        results = search_agent_cards(query_vector=query_embedding, top_k=max_agents)
        
        recommendations = []
        for result in results:
            agent_card = result["text"]
            score = result.get("score", 0.0)
            
            recommendations.append({
                "agent": agent_card,
                "relevance_score": float(score),
                "confidence": "high" if score > 0.8 else "medium" if score > 0.5 else "low"
            })
        
        abi_logging(f"[✅] Recommended {len(recommendations)} agents")
        return recommendations
    
    @mcp.tool(
        name='check_agent_capability',
        description='Check if an agent has specific capabilities/tasks'
    )
    @validate_semantic_access
    async def check_agent_capability(
        agent_name: str,
        required_tasks: list[str],
        _request_context: dict = None
    ) -> dict:
        """Check if an agent supports required tasks.
        
        Args:
            agent_name (str): Name of the agent to check
            required_tasks (list[str]): List of required task names
        
        Returns:
            dict: Capability check result with supported/missing tasks
        """
        abi_logging(f"[🔍] Checking capabilities for agent: {agent_name}")
        
        if df is None or df.empty:
            return {
                "agent": agent_name,
                "found": False,
                "error": "No agents available"
            }
        
        # Find agent card
        agent_cards = df[df['agent_card'].apply(
            lambda x: x.get('name', '').lower() == agent_name.lower()
        )]
        
        if agent_cards.empty:
            abi_logging(f"[⚠️] Agent '{agent_name}' not found")
            return {
                "agent": agent_name,
                "found": False,
                "error": "Agent not found"
            }
        
        agent_card = agent_cards.iloc[0]['agent_card']
        supported_tasks = agent_card.get('supportedTasks', [])
        
        # Check capabilities
        supported = [task for task in required_tasks if task in supported_tasks]
        missing = [task for task in required_tasks if task not in supported_tasks]
        
        result = {
            "agent": agent_name,
            "found": True,
            "supported_tasks": supported,
            "missing_tasks": missing,
            "has_all_capabilities": len(missing) == 0,
            "capability_coverage": len(supported) / len(required_tasks) if required_tasks else 1.0
        }
        
        abi_logging(f"[✅] Capability check complete: {result['capability_coverage']:.0%} coverage")
        return result
    
    @mcp.tool(
        name='check_agent_health',
        description='Check if an agent is online and responding'
    )
    @validate_semantic_access
    async def check_agent_health(
        agent_name: str,
        _request_context: dict = None
    ) -> dict:
        """Check agent health status.
        
        Args:
            agent_name (str): Name of the agent to check
        
        Returns:
            dict: Health status with response time
        """
        import httpx
        import time
        from functools import lru_cache
        
        abi_logging(f"[🏥] Checking health for agent: {agent_name}")
        
        if df is None or df.empty:
            return {
                "agent": agent_name,
                "status": "unknown",
                "error": "No agents available"
            }
        
        # Find agent card
        agent_cards = df[df['agent_card'].apply(
            lambda x: x.get('name', '').lower() == agent_name.lower()
        )]
        
        if agent_cards.empty:
            abi_logging(f"[⚠️] Agent '{agent_name}' not found")
            return {
                "agent": agent_name,
                "status": "not_found",
                "error": "Agent not found"
            }
        
        agent_card = agent_cards.iloc[0]['agent_card']
        agent_url = agent_card.get('url', '')
        
        # Check health endpoint with timeout
        try:
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{agent_url}/health")
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            result = {
                "agent": agent_name,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": agent_url,
                "response_time_ms": round(response_time, 2),
                "status_code": response.status_code
            }
            
            abi_logging(f"[✅] Health check complete: {result['status']} ({result['response_time_ms']}ms)")
            return result
            
        except httpx.TimeoutException:
            abi_logging(f"[⏰] Health check timeout for {agent_name}")
            return {
                "agent": agent_name,
                "status": "timeout",
                "url": agent_url,
                "error": "Health check timeout (5s)"
            }
        except Exception as e:
            abi_logging(f"[❌] Health check error for {agent_name}: {e}")
            return {
                "agent": agent_name,
                "status": "error",
                "url": agent_url,
                "error": str(e)
            }
    
    
    @mcp.resource('resource://agent_cards/list/{agent_id}', mime_type='application/json')
    @validate_semantic_access
    async def get_agent_cards(agent_id: str = None,_request_context: dict = None) -> dict:
        """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/list'.

        Returns:
            A json / dictionary structured as {'agent_cards': [...]}, where the value is a
            list containing all the loaded agent card dictionaries. Returns
            {'agent_cards': []} if the data cannot be retrieved.
        """
        resources = {"agent_cards": []}
        abi_logging(f'[📄] Starting read resources')

        try:
            # df is built once at startup; check availability
            if df is None or getattr(df, "empty", True):
                abi_logging("[⚠️] No Agent Cards available for listing.")
                return resources

            # Extract agent_card column as list
            raw_cards = df.get('agent_card', []).tolist() if 'agent_card' in df.columns else []

            cleaned_cards = []
            for card in raw_cards:
                if card is None:
                    continue
                # If card is a pandas Series or object with to_dict, try to convert to plain dict
                try:
                    # many agent cards will already be dicts
                    if isinstance(card, dict):
                        cleaned_cards.append(card)
                    else:
                        # try to coerce objects (e.g., pandas Series) to dict
                        converted = getattr(card, "to_dict", None)
                        if callable(converted):
                            cleaned_cards.append(converted())
                        else:
                            cleaned_cards.append(card)
                except Exception:
                    # fallback: include raw object (best-effort)
                    cleaned_cards.append(card)

            resources["agent_cards"] = cleaned_cards
            abi_logging(f"[✅] Retrieved {len(cleaned_cards)} agent cards.")
        except Exception as exc:
            abi_logging(f"[❌] Error retrieving agent cards: {exc}")

        return resources
    
    @mcp.resource(
        'resource://agent_cards/{card_name}', mime_type='applicacion/json'
    )
    @validate_semantic_access
    async def get_agent_card(card_name: str, _request_context: dict = None) ->dict:
        """Retrieves an specific Agent Card as a JSON dictionary for the MCP resource endpoint

        Returns: JSON Dictionary.
        When resource were found: {agent_card: [.]}
        When data can't be found: {agent_card: []}
        """
        resource = {}
        abi_logging(f'[📄] Starting to read resource {card_name}')
        abi_logging(f'[📋] Available card_uris: {df["card_uri"].tolist()}')
        
        # The card_uri in DataFrame contains file paths, not resource URIs
        # So we need to match by filename instead
        matching_cards = df.loc[
            df['card_uri'].str.contains(f'{card_name}.json', na=False),
            'agent_card'
        ].to_list()
        
        resource['agent_card'] = matching_cards
        abi_logging(f'[✅] Found {len(matching_cards)} matching cards for {card_name}')
        
        if len(matching_cards) == 0:
            abi_logging(f'[⚠️] No cards found for {card_name}. Trying exact filename match...')
            # Try exact filename match
            exact_matches = df.loc[
                df['card_uri'].str.endswith(f'{card_name}.json'),
                'agent_card'
            ].to_list()
            resource['agent_card'] = exact_matches
            abi_logging(f'[🎯] Exact match found {len(exact_matches)} cards for {card_name}')
        
        return resource
    
    @mcp.tool(
        name='register_agent',
        description='Register a new agent in the semantic layer'
    )
    @validate_semantic_access
    async def register_agent(
        agent_card: dict,
        _request_context: dict = None
    ) -> dict:
        """Register a new agent card in the semantic layer.
        
        Args:
            agent_card (dict): Complete agent card with auth credentials
            _request_context (dict): Request context for validation
        
        Returns:
            dict: Registration result with status and agent info
        
        Security:
            - Authenticates via HMAC signature in agent_card.auth
            - Authorizes via OPA policy (checks if agent can register)
        """
        try:
            # Validate agent card structure
            required_fields = ['id', 'name', 'auth']
            missing = [f for f in required_fields if f not in agent_card]
            if missing:
                return {
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing)}"
                }
            
            # Validate auth section
            auth = agent_card.get('auth', {})
            if auth.get('method') != 'hmac_sha256':
                return {
                    "success": False,
                    "error": "Only hmac_sha256 authentication method is supported"
                }
            
            if not auth.get('shared_secret'):
                return {
                    "success": False,
                    "error": "Missing shared_secret in auth section"
                }
            
            # Generate embedding for the new agent card
            from layer.embedding_mesh.embeddings_abi import embed_one
            
            # Create combined text for embedding
            combined_text = ' '.join([
                agent_card.get('name', ''),
                agent_card.get('description', ''),
                ' '.join(agent_card.get('supportedTasks', [])),
                ' '.join([
                    skill.get('description', '') 
                    for skill in agent_card.get('skills', [])
                ])
            ])
            
            embedding = embed_one(combined_text)
            
            if not embedding:
                return {
                    "success": False,
                    "error": "Failed to generate embedding for agent card"
                }
            
            # Generate deterministic UUID from agent ID
            agent_id = agent_card['id']
            card_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, agent_id))
            
            # Prepare item for Weaviate
            item = {
                "id": card_uuid,
                "text": json.dumps(agent_card),
                "uri": f"dynamic://{agent_id}",  # Mark as dynamically registered
                "metadata": {
                    "name": agent_card.get('name', ''),
                    "description": agent_card.get('description', ''),
                    "supportedTasks": agent_card.get('supportedTasks', [])
                },
                "vector": embedding,
                "origin": "agent_card"
            }
            
            # Upsert to Weaviate
            from layer.embedding_mesh.weaviate_store import upsert_agent_cards
            count = upsert_agent_cards([item])
            
            abi_logging(f"[✅] Registered new agent: {agent_card.get('name')} ({agent_id})")
            
            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": agent_card.get('name'),
                "message": f"Agent '{agent_card.get('name')}' registered successfully",
                "uuid": card_uuid
            }
            
        except Exception as e:
            abi_logging(f"[❌] Error registering agent: {e}")
            return {
                "success": False,
                "error": f"Registration failed: {str(e)}"
            }
    
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request):
        return JSONResponse({"status": "ok"})
    
    mcp.run(transport=transport)