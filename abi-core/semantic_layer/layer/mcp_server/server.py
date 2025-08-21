import os

import numpy as np

from typing import Optional

from starlette.responses import JSONResponse
from starlette.requests import Request
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

from layer.embedding_mesh.api import attach_embedding_mesh_routes
from layer.embedding_mesh.embeddings_abi import embed_one, build_agent_card_embeddings


logger = get_logger(__name__)

MODEL = os.getenv("MODEL")


def serve(host, port, transport):
    """Start the MCP Agent Card Server
    Args:
        host: Hostname or IP address to bind the Server to.
        port: Port number to bind the server to.
    """
    logger.info('[*] Starting Agents Cards MCP Server')
    mcp = FastMCP('agent-cards', host=host, port=port)

    df = build_agent_card_embeddings()

    @mcp.tool(
        name='find_agent',
        description='Finds the most adecuate agent cards base in natural laguage query string.'
    )
    def find_agent(query: str) -> Optional[dict]:
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
        df = build_agent_card_embeddings()

        if df is None or df.empty:
            logger.warning("[!] No Agent Cards available for search.")
            return None

        query_embedding = embed_one(query)

        dot_products = np.dot(
            np.stack(df['card_embeddings']),
            query_embedding
        )

        best_match_index = np.argmax(dot_products)
        best_match = df.iloc[best_match_index]['agent_card']

        logger.debug(f"[*] Best match index: {best_match_index}, similarity: {dot_products[best_match_index]}")
        return best_match
    
    #@TODO Implement more tools to enhance the system
    
    @mcp.resource('resource://agent_card/list', mime_type='application/json')
    def get_agent_cards() -> dict:
        """Retrives all loaded Agents Cards as a JSON dictionary for the MCP resource endpoint

        Returns: JSON Dictionary. 
        When resources were found: {agent_cards: [...]},
        When data can't be retrieve: {agent_cards: []}
        """
        resources = {}
        logger.info('[*] Starting to read resources')
        resources['agent_cards'] = df['card_uri'].to_list()
        return resources
    
    @mcp.resource(
        'resource://agent_cards/{card_name}', mime_type='applicacion/json'
    )
    def get_agent_card(card_name: str) ->dict:
        """Retrieves an specific Agent Card as a JSON dictionary for the MCP resource endpoint

        Returns: JSON Dictionary.
        When resource were found: {agent_card: [.]}
        When data can't be found: {agent_card: []}
        """
        resource = {}
        logger.info(f'[*] Starting to read resource {card_name}')
        resource['agent_card'] = (df.loc[
            df['card_uri'] == f'resource://agent_cards/{card_name}',
            'agent_card'
        ]).to_list()

        return resource
    
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request):
        return JSONResponse({"status": "ok"})
    
    mcp.run(transport=transport)
