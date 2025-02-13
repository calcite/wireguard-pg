from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN
import loggate
from config import get_config


TOKEN = get_config('API_ACCESS_TOKEN')
logger = loggate.get_logger('access')

def get_token(request: Request) -> str:
    return request.headers.get("Authorization")

def check_token(token: str):
    if not TOKEN:
        logger.warning('You have not setup API_ACCESS_TOKEN. Whole API is '
                       'accessible for everyone.')
        return
    if token != TOKEN:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Not authenticated"
        )
