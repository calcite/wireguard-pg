from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from model.base import BaseDBModel, BasePModel


class Link(BasePModel):
    url: str
    owner: Optional[str]
    created_at: datetime


class LinkUpdate(BaseModel):
    url: str = Field(max_length=256)


class LinkCreate(BaseModel):
    url: str = Field(max_length=256)
    owner: Optional[str] = Field(default=None, max_length=32)
    created_at: datetime = Field(default_factory=datetime.now)


class LinkDB(BaseDBModel):
    class Meta:
        db_table = 'link'
        PYDANTIC_CLASS = Link
        DEFAULT_SORT_BY: str = 'id'
