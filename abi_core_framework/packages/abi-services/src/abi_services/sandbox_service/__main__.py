"""Run sandbox-service: python -m abi_services.sandbox_service"""

import os

import uvicorn

from abi_services.sandbox_service.app import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "11500")))
