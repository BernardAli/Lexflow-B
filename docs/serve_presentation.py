"""Serve presentation docs on loopback with HTTP byte ranges for chapter seeking."""
import argparse
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent


async def index(request):
    return RedirectResponse('/docs/LexFlow_AI_Presentation.html')


async def readme(request):
    return FileResponse(ROOT.parent / 'README.md', media_type='text/plain')


app = Starlette(routes=[Route('/', index), Route('/README.md', readme),
                        Mount('/docs', app=StaticFiles(directory=ROOT))])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8002)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Choose a port from 1 to 65535')
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
