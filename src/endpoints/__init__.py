from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED
import loggate
from config import get_config


TOKEN = get_config('API_ACCESS_TOKEN')
logger = loggate.get_logger('access')


def check_token(request: Request) -> bool:
    if not TOKEN:
        logger.warning('You have not setup API_ACCESS_TOKEN. Whole API is '
                       'accessible for everyone.')
        return True
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    if authorization != TOKEN:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Not authenticated"
        )
    return True
