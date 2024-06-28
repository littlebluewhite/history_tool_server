from typing import Annotated

import redis
from general_operator.app.influxdb.influxdb import InfluxDB

from data.enum.fn import FnEnum
from function.API.API_history import APIHistoryOperate
from sqlalchemy.orm import sessionmaker
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse


class APIHistoryRouter(APIHistoryOperate):
    def __init__(self, module, redis_db: redis.Redis, influxdb: InfluxDB,
                 exc, db_session: sessionmaker):
        self.db_session = db_session
        APIHistoryOperate.__init__(self, module, redis_db, influxdb, exc)

    def create(self):
        router = APIRouter(
            prefix="/api/history",
            tags=["API", "history"],
            dependencies=[]
        )

        @router.get("/object/", response_model=list)
        async def get_history_value(
                start: str = Query(...), stop: str = Query(""), _ids: list[str] = Query(None),
                uids: list[str] = Query(None), period: str = Query("1h"), fn: FnEnum = Query(...),
                skip: int = Query(0), limit: int = Query(None)):
            try:
                data = self.read_object_value_history(start, stop, _ids, uids, period, fn, skip, limit)
                return JSONResponse(data)
            # return data
            except Exception as e:
                print(e)
                raise self.exc(status_code=499, detail=f"{e}")

        @router.get("/object/fail_hour/")
        async def get_fail_hour(_id: Annotated[str, Query()] = ""):
            result = self.object_fail_hour(_id)
            print(result)
            return JSONResponse(result)

        @router.get("/object/switch_times/")
        async def get_switch_times(
                _ids: Annotated[list[str] | None, Query()] = ...,
                start: Annotated[str, Query()] = ...,
                period: Annotated[list[int] | None, Query()] = None,
                stop: Annotated[str, Query()] = "",
                recover_value: Annotated[str, Query()] = ...
        ):
            if period is None:
                period = []
            result = self.object_switch_times(start, period, stop, recover_value, _ids)
            return JSONResponse(result)

        @router.get("/object/trigger_seconds/")
        async def get_trigger_seconds(
                _ids: Annotated[list[str] | None, Query()] = None,
                _uids: Annotated[list[str] | None, Query()] = None,
                start: Annotated[int, Query()] = ...,
                stop: Annotated[int, Query()] = ...,
                trigger_value: Annotated[str, Query()] = ...
        ):
            result = self.get_trigger_seconds(trigger_value, start, stop, _ids, _uids)
            return JSONResponse(result)

        return router
