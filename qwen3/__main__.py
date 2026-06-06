"""Allow running the package directly: python -m qwen3"""

import uvicorn

from qwen3.config import Settings

cfg = Settings()
uvicorn.run("qwen3.api:app", host=cfg.api_host, port=cfg.api_port, reload=False)
