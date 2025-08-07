import json
import os

import numpy as np
import pandas as pd
import google.generativeai as genai

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger


logger = get_logger(__name__)
AGENT_CARD_DIR = 'agent_cards'
MODEL = 'models/embedding-001'
SQLLITE_DB = 'abi_context.db'

def generate_embedding(text):
    """Generates Embeddings
    Args:
        text: Input string from generate embeddings.
    
    Returns:
        A list of embeddings representing the input text.
    """
    return genai.embed_content(
        model=MODEL,
        content=text,
        task_type='retrival_document',
    )['embedding']

def load_agent_cards():
    """Loads Agent cards datarom JSON files within a specified directory.

    Returns:
        List() JSON data from Agent.
        Empty List() directory from agent card is empty.
        Empty List() empty if json files enconter an error during processing.
    """

    card_uris = []
    agent_cards = []
    dir_path = Path(AGENT_CARD_DIR)

    if not dir_path.is_dir():
        logger.error(f'[!] Agent card directory not found {AGENT_CARD_DIR}')
        return agent_cards
    
    logger.info(f'[*]Loading Agent cards from:{ AGENT_CARD_DIR}')

    for filename in os.listdir(AGENT_CARD_DIR):
        if filename.lower().endswith('.json'):
            file_path = dir_path / filename

            if file_path.is_file():
                logger.info('[*]Reading files {filename}')
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        card_uris.append(
                            f'resource://agent_cards/{Path(filename).stem}'
                        )
                        agent_cards.append(data)
                except json.JSONDecodeError as jde:
                    logger.error(f'[!] JSON decoder error {filename}:{jde}')
                except OSError as ose:
                    logger.erro(f'[!] Error reading the file {filename}:{ose}')
                except Exception as e:
                    logger.error(
                        f'[!] An un expected error accours {filename}:{e}'
                    )

    logger.info(f'[✓] Finished to loading agents cards. {len(agent_cards)} cards found!')

    return card_uris, agent_cards


def bulding_agent_card_embeddings() -> pd.DataFrame:
    """Loads the Agent Cards generates the embeddings for them and return data frame

    Return:
        Optional[pd.DataFrame]
        Pandas data frame conteining the original agent_card and its Embeddings.
        None
        If the agent card was not found
    """ 
    card_uris, agent_cards = load_agent_cards()
    
    logger.info('[*] Generating Embeddings for the Agent Card')

    try:
        if agent_cards:
            df = pd.DataFrame(
                {'card_uri': card_uris, 'agent_card': agent_cards}
            )
            df['cards_embeddings'] = df.apply(
                lambda row: generate_embedding(json.dumps(row['agent_card'])),
                axis=1
            )
            return df
    except Exception as e:
        logger.error(f'[!] An unexpected error accourred: {e}', exe_info=True)

    def serve(host, port, transport):
        """Start the MCP Agent Card Server
        Args:
            host: Hostname or IP address to bind the Server to.
            port: Port number to bind the server to.
        """
        logger.info('[*] Starting Agents Cards MCP Server')
        mcp = FastMCP('agent-cards', host=host, port=port)

        df = bulding_agent_card_embeddings()

        @mcp.tool(
            name='find_agent',
            decription='Finds the most adecuate agent cards base in natural laguage query string.'
        )
        def find_agent(query: str) -> str:
            """Finds the most adecuate agent cards base in natural laguage query string.
            Args:
                query: Natural language query string used to search relevant agent card
            
            Return:
                JSON: Most relevan Agent card, based on embedding similarity
            """
            query_embedding = genai.embedding_content(
                model=MODEL,
                content=query,
                task_type='retrival_query'
            )
            dot_products = np.dot(
                np.stack(df['card_embeddings']),
                query_embedding['embedding']
            )
            best_match_index = np.argmax(dot_products)

            return df.iloc[best_match_index]['agent_card']
        
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
