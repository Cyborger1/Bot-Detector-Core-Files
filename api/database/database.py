from enum import Enum, auto

from api import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


class EngineType(Enum):
    """"""
    PLAYERDATA = auto()
    DISCORD = auto()

class Engine():
    def __init__(self, engine_type: EngineType = EngineType.PLAYERDATA):
        if engine_type == EngineType.PLAYERDATA:
            connection_string = Config.sql_uri
        elif engine_type == EngineType.DISCORD:
            connection_string = Config.discord_sql_uri
        else:
            raise ValueError(f"Engine type {engine_type} not valid.")

        self.engine = create_async_engine(connection_string, poolclass=NullPool)
        self.session = sessionmaker(self.engine, class_= AsyncSession, expire_on_commit=False, autoflush=True)


engine = Engine(EngineType.PLAYERDATA)
discord_engine = Engine(EngineType.DISCORD)