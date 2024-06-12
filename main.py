import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from general_operator.app.SQL.database import SQLDB
from general_operator.app.influxdb.influxdb import InfluxDB
from general_operator.app.redis_db.redis import RedisDB
from general_operator.function.exception import GeneralOperatorException

import data.API.API_history
import version
from app.config.loader import ConfigLoader
from routers.API.API_history import APIHistoryRouter

# config handle
config = ConfigLoader("./config/config.yaml").get_config()

app = FastAPI(title="history_tool", version=version.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# redis_db
redis_db = RedisDB(config["redis"]).redis_client()

# SQL DB
db = (SQLDB(config["sql"]))
#   create SQL models
# models.Base.metadata.create_all(bind=db.get_engine())

# Influx DB
influxdb = InfluxDB(config["influxdb"])

#   create SQL session
db_session = db.new_db_session()

# router
app.include_router(APIHistoryRouter(data.API.API_history, redis_db, influxdb,
                                    GeneralOperatorException, db_session).create())


@app.exception_handler(GeneralOperatorException)
async def unicorn_exception_handler(request: Request, exc: GeneralOperatorException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": f"{exc.detail}"},
    )


@app.get("/exception")
async def test_exception():
    raise GeneralOperatorException(status_code=423, detail="test exception")


if __name__ == "__main__":
    uvicorn.run(app="main:app", host='0.0.0.0', port=config["server"]["port"], workers=1, reload=True, loop="asyncio",
                log_level="info", limit_concurrency=1000)
