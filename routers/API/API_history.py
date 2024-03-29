import redis

from app.influxdb.influxdb import InfluxDB
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
                start: str = Query(...), stop: str = Query(""), _id: str = Query(""),
                uid: str = Query(""), period: str = Query("1h"), fn: FnEnum = Query(...),
                skip: int = Query(0), limit: int = Query(None)):
            try:
                data = self.read_object_value_history(start, stop, _id, uid, period, fn, skip, limit)
                return JSONResponse(data)
            # return data
            except Exception as e:
                print(e)
                raise self.exc(status_code=499, detail=f"{e}")

        @router.get("/object/fail_hour/")
        async def get_fail_hour(_id: str = Query("")):
            result = self.object_fail_hour(_id)
            return JSONResponse(result)

        return router
