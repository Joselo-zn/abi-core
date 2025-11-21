# mcp/mcp_server/main.py
from .server import serve


if __name__ == "__main__":
    serve("0.0.0.0", 10100, "sse")
