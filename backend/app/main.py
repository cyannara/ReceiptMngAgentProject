import sys
from pathlib import Path

# Allow importing the backend root module when the app package is executed
# as `uvicorn app.main:app` from the backend directory.
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app

__all__ = ["app"]
