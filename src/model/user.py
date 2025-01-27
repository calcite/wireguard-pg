import hashlib
from typing import Optional
from fastapi import Depends
from fastapi.security import OAuth2
import jwt
import loggate
from pydantic import BaseModel, Field
from model.base import BaseDBModel
from asyncpg import Connection
from config import get_config, to_bool


JWT_SECRET = get_config('JWT_SECRET')
oauth2_scheme = OAuth2( auto_error=False)
logger = loggate.get_logger('user')


# class UserCreate(BaseModel):
#     username: str = Field(max_length=32)
#     pw_hash: str = Field(max_length=64)


class User(BaseModel):
    id: int
    username: str = Field(max_length=32)


# class LoginRequest(BaseModel):
#     username: str = Field(max_length=32)
#     password: str = Field(max_length=64)
#     # grant_type: Optional[str]

#     @property
#     def hash(self) -> str:
#         return hashlib.sha256(f"{self.password}@{self.username}".encode('utf-8')).hexdigest()


class JWT(BaseModel):
    token_type: str = Field('Bearer')
    access_token: Optional[str]

    def get_user(self) -> User:
        """
        @raise DecodeError
        """
        if self.access_token:
            try:
                return User(**jwt.decode(self.access_token.encode('utf-8'), JWT_SECRET, algorithms=["HS256"]))
            except jwt.exceptions.DecodeError:
                logger.warning('User try to login with wrong token')
        return None

    @classmethod
    def get_jwt(cls, user: User) -> 'JWT':
        return JWT(
            access_token=jwt.encode({
                'id': user.id,
                'username': user.username,
            }, get_config('JWT_SECRET'), algorithm="HS256")
        )


def get_service_token(username, id):
    """
        This method generate service token
    """
    return JWT.get_jwt(User(id=id, username=username)).access_token


def get_user(token: str = Depends(oauth2_scheme)) -> User:
    if get_config('REQUIRED_API_TOKEN', wrapper=to_bool):
        return JWT(access_token=token).get_user()
    return User(username='service_token', id=1)


# class UserDB(BaseDBModel):
#     class Meta:
#         db_table = 'user'
#         PYDANTIC_CLASS = User

#     @classmethod
#     async def create_init_user(cls, db: Connection, login: LoginRequest) -> None:
#         """
#         Create a new user in the database (application initialization)
#         """
#         users = await db.fetchval(f'SELECT count(*) FROM "{cls.Meta.db_table}"')

#         if users == 0:
#             user = UserCreate(
#                 username=login.username,
#                 pw_hash=login.hash
#             )
#             await user.save(db)

#     @classmethod
#     async def login(cls, db: Connection, login: LoginRequest) -> JWT:
#         row = await db.fetchrow(
#             f'SELECT * FROM "{cls.Meta.db_table}" WHERE username = $1 AND pw_hash = $2',
#             login.username, login.hash
#         )
#         return JWT.get_jwt(User(**row)) if row else None
