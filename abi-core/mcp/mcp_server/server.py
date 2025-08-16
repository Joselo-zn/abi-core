import json
import os

import numpy as np
import pandas as pd
import google.generativeai as genai

from pathlib import Path
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger
from .embeddings_abi_ollama import embed_one
from typing import Optional, Tuple, List


logger = get_logger(__name__)

MODEL = os.getenv("MODEL")

_agent_cards_df_cache: Optional[pd.DataFrame] = None

def load_agent_cards() -> Tuple[List[str], List[dict]]:
    """Retrieves all Agent Cards stored as JSON files in the configured directory.
    
    Returns:
        tuple:
            - card_uris (List[str]): List of file paths for each Agent Card JSON.
            - agent_cards (List[dict]): List of parsed JSON dictionaries representing Agent Cards.
    
    Behavior:
        - Skips unreadable or malformed JSON files with a warning.
        - Returns empty lists if no Agent Cards are found.
    """
    AGENT_CARDS_DIR = os.getenv("AGENT_CARDS_BASE", "agent_cards")
    dir_path = Path(AGENT_CARDS_DIR)

    if not dir_path.is_dir():
        logger.error(f"[!] Agent Cards directory not found or is not a directory: {AGENT_CARDS_DIR}")
        return [], []

    card_uris = []
    agent_cards = []

    for file_path in dir_path.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)
                card_uris.append(str(file_path))
                agent_cards.append(card_data)
        except json.JSONDecodeError:
            logger.warning(f"[!] Invalid JSON format in file: {file_path}")
        except Exception as e:
            logger.error(f"[!] Error reading {file_path}: {e}", exc_info=True)

    return card_uris, agent_cards


def build_agent_card_embeddings(force_reload: bool = False) -> Optional[pd.DataFrame]:
    """Generates embeddings for all available Agent Cards and caches them in memory.
    
    Args:
        force_reload (bool, optional): If True, forces regeneration of embeddings 
                                       even if cached data exists. Defaults to False.
    
    Returns:
        pd.DataFrame | None:
            - DataFrame with columns:
                - card_uri: Path to the JSON file for the Agent Card.
                - agent_card: Original JSON dictionary of the Agent Card.
                - card_embeddings: Vector embedding of the Agent Card JSON content.
            - None if no Agent Cards are found.
    
    Note:
        This is the MVP version — embeddings are computed locally via `embed_one()`.
        In the robust version, these embeddings will be persisted in Weaviate for semantic search.
    """
    global _agent_cards_df_cache

    if _agent_cards_df_cache is not None and not force_reload:
        logger.debug("[*] Returning cached Agent Card embeddings")
        return _agent_cards_df_cache

    card_uris, agent_cards = load_agent_cards()

    if not agent_cards:
        logger.warning("[!] No Agent Cards found. Cannot generate embeddings.")
        return None

    logger.info("[*] Generating embeddings for loaded Agent Cards (MVP mode)")
    try:
        df = pd.DataFrame({
            'card_uri': card_uris,
            'agent_card': agent_cards
        })
        df['card_embeddings'] = df.apply(
            lambda row: embed_one(json.dumps(row['agent_card'])),
            axis=1
        )

        _agent_cards_df_cache = df
        return df

    except Exception as e:
        logger.error(f"[!] Unexpected error while generating embeddings: {e}", exc_info=True)
        return None

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
    
    mcp.run(transport=transport)
