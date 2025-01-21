import asyncpg
from fastapi import HTTPException, status, Depends, Query
from typing import TypeVar, Optional, List
from pydantic import BaseModel
from asyncpg import Connection


class ObjectNotFound(HTTPException):
    def __init__(self, detail: str = "Object not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConstrainError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BasePModel(BaseModel):
    id: int

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.id == other.id


class CommonQueryParams(BaseModel):
    """
    This is common query class for gets method.
    """
    offset: int = Query(0, ge=0)
    limit: int = Query(0, ge=0, le=1000)
    sort_by: str = Query('f.id', regex="^[a-zA-Z0-9\\.]*$")


def query_params(params: CommonQueryParams = Depends()):
    return params.dict()


# Get Pydantic type
G = TypeVar('G', bound=BasePModel)      # Full pydantic object
C = TypeVar('C', bound=BaseModel)       # Create pydantic object
U = TypeVar('U', bound=BaseModel)      # Update pydantic object


class BaseDBModel:
    class Meta:
        db_table = 'unknow'
        sql_subquery = ''
        PYDANTIC_CLASS: G = BasePModel
        DEFAULT_SORT_BY: str = 'id'
        reload_after_create: bool = False

    @classmethod
    async def get(cls, db: Connection, query: str | int | G, *args, **kwargs
                  ) -> Optional[G]:
        _cls = kwargs.pop('_cls', cls)
        _raise = kwargs.pop('_raise', False)
        _sub_sql = kwargs.pop('_sub_sql', getattr(_cls.Meta, 'sub_sql', ''))
        _sub_columns = kwargs.pop('_sub_columns', getattr(_cls.Meta, 'sub_columns', ''))
        _pydantic_class = kwargs.pop('_pydantic_class', getattr(_cls.Meta, 'PYDANTIC_CLASS', _cls.Meta.PYDANTIC_CLASS))
        _db_table = getattr(_cls.Meta, 'db_view', getattr(_cls.Meta, 'db_table', ''))
        if isinstance(query, _pydantic_class):
            return query
        if isinstance(query, int) and len(args) == 0:
            args = [query]
            query = 'f."id"=$1'

        if row := await db.fetchrow(
                f'SELECT f.* {_sub_columns} FROM "{_db_table}" f {_sub_sql} WHERE {query}',
                *args
        ):
            return _pydantic_class(**row)
        elif not _raise:
            return None
        else:
            raise ObjectNotFound(
                f'Object {_cls.__name__} not found: {query} ({args}).'
            )

    @classmethod
    async def gets(cls, db: Connection, query='1=1', *args, offset: int = 0,
                   limit: int = 0, sort_by='', **kwargs) -> List[G]:
        _cls = kwargs.pop('_cls', cls)
        _sub_sql = kwargs.pop('_sub_sql', getattr(_cls.Meta, 'sub_sql', ''))
        _sub_columns = kwargs.pop('_sub_columns', getattr(_cls.Meta, 'sub_columns', ''))
        _pydantic_class = kwargs.pop('_pydantic_class', getattr(_cls.Meta, 'PYDANTIC_CLASS', object))
        _db_table = getattr(_cls.Meta, 'db_view', getattr(_cls.Meta, 'db_table', ''))
        if not sort_by and hasattr(_cls.Meta, 'DEFAULT_SORT_BY'):
            sort_by = getattr(_cls.Meta, 'DEFAULT_SORT_BY')
        if sort_by:
            sort_by = f'ORDER BY {sort_by}'
        _post_sql = ' '
        if limit:
            _post_sql += f' LIMIT {limit}'
        if offset:
            _post_sql += f' OFFSET {offset}'

        rows = await db.fetch(
            f'SELECT f.* {_sub_columns} FROM "{_db_table}" f {_sub_sql} '
            f'WHERE {query} {sort_by}{_post_sql};',
            *args
        )
        return [_pydantic_class(**row) for row in rows]

    @classmethod
    async def update(cls, db: Connection, obj: str | int | G, update: U, *args, **kwargs) -> G:
        _cls = kwargs.pop('_cls', cls)
        obj = await _cls.get(db, obj, *args, _raise=True)
        if hasattr(_cls, 'pre_update'):
            await _cls.pre_update(db, obj, update, **kwargs)
        columns, values = ([], [])
        fields = update.__class__.__fields__
        fields.update(update.__class__.model_computed_fields)
        for key, meta in fields.items():
            val = getattr(update, key)
            if not getattr(meta, 'exclude', False) and getattr(obj, key, None) != val:
                ix = len(values) + 1
                columns.append(f'"{key}" = ${ix}')
                values.append(val)
                setattr(obj, key, val)
        if not values:
            return obj
        try:
            await db.execute(
                f'UPDATE "{_cls.Meta.db_table}" SET {",".join(columns)} WHERE id = {obj.id}',
                *values
            )
        except asyncpg.exceptions.IntegrityConstraintViolationError as e:
            raise ConstrainError(str(e))
        if hasattr(_cls, 'post_update'):
            await _cls.post_update(db, obj, **kwargs)
        return obj

    @classmethod
    async def create(cls, db: Connection, create: C, **kwargs) -> G:
        _cls = kwargs.pop('_cls', cls)
        _reload_after_create = kwargs.pop('_reload_after_create', getattr(_cls.Meta, 'reload_after_create', False))
        if hasattr(_cls, 'pre_create'):
            await _cls.pre_create(db, create, **kwargs)
        columns, values, indexes = ([], [], [])
        fields = create.__class__.__fields__
        fields.update(create.__class__.model_computed_fields)
        for key, meta in fields.items():
            val = getattr(create, key)
            if not getattr(meta, 'exclude', False):
                columns.append(f'"{key}"')
                values.append(val)
                indexes.append(f'${len(values)}')
        try:
            row = await db.fetchrow(
                f'INSERT INTO "{_cls.Meta.db_table}"  ({",".join(columns)}) VALUES ({",".join(indexes)}) RETURNING *;',
                *values
            )
            data = dict(**row)
            if hasattr(_cls, 'post_sql_create'):
                await _cls.post_sql_create(db, data, create, **kwargs)
        except asyncpg.exceptions.IntegrityConstraintViolationError as e:
            raise ConstrainError(str(e))
        if not _reload_after_create:
            obj = _cls.Meta.PYDANTIC_CLASS(**data)
        else:
            obj = await _cls.get(db, data['id'])
        if hasattr(_cls, 'post_create'):
            await _cls.post_create(db, obj, create, **kwargs)
        return obj

    @classmethod
    async def delete(cls, db: Connection, obj: int | G, **kwargs):
        _cls = kwargs.pop('_cls', cls)
        obj = await _cls.get(db, obj)
        if hasattr(_cls, 'pre_delete'):
            await _cls.pre_delete(db, obj, **kwargs)
        result = (await db.execute(
            f'DELETE FROM "{_cls.Meta.db_table}" WHERE id = $1;',
            obj.id
        )).startswith("DELETE ")
        if not result:
            raise ObjectNotFound(
                f'Object {_cls.__name__} not found: {obj}')
        if hasattr(_cls, 'post_delete'):
            await _cls.post_delete(db, obj, **kwargs)

