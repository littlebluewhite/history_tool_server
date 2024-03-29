import math
import time

from data.enum.fn import FnEnum
from function.General_operate import GeneralOperate


class APIHistoryOperate(GeneralOperate):
    def __init__(self, module, redis_db, influxdb, exc):
        self.exc = exc
        GeneralOperate.__init__(self, module, redis_db, influxdb, exc)

    def read_object_value_history(self, start: str, stop: str, _id: str = "",
                                  uid: str = "", period: str = "",
                                  fn: FnEnum = FnEnum.mean, skip: int = 0,
                                  limit: int = None):
        stop_str = ""
        if stop != "":
            stop_str = f", stop : {stop}"
        id_str = ""
        if _id != "":
            id_str = f"""|> filter(fn:(r) => r.id == "{_id}")"""
        uid_str = ""
        if uid != "":
            uid_str = f"""|> filter(fn:(r) => r.uid == "{uid}")"""
        moving_str = ""
        match fn:
            case FnEnum.mean:
                fn = "last"
                moving_str = f"|> timedMovingAverage(every: {period}, period: {period})"
            case FnEnum.max:
                fn = "max"
            case FnEnum.last:
                fn = "last"
        stmt = f"""from(bucket:"node_object")
|> range(start: {start}{stop_str})
|> filter(fn:(r) => r._measurement == "object_value")
|> filter(fn:(r) => r._field == "value")
{id_str}
{uid_str}
{moving_str}
|> aggregateWindow(every: {period}, fn: {fn})
|> fill(usePrevious: true)"""
        result = self.query_object_history(stmt=stmt)
        if limit is not None:
            result = result[skip:skip + limit]
        else:
            result = result[skip:]
        return result

    def object_fail_hour(self, _id: str = ""):
        id_str = ""
        if _id != "":
            id_str = f"""|> filter(fn:(r) => r.id == "{_id}")"""
        stmt = f"""from(bucket:"node_object")
    |> range(start: 0)
    |> filter(fn:(r) => r._measurement == "object_value")
    {id_str}
    |> filter(fn:(r) => r._field == "value")"""
        result = self.query_object_history(stmt=stmt)
        start = math.inf
        end = time.time()
        fail_start = 0
        fail_second = 0
        value = 0
        times = 0
        result = sorted(result, key=lambda x: x["timestamp"])
        for i in result:
            if i["timestamp"] < start:
                start = i["timestamp"]
            if str(int(i["value"])) == "1" and value == 0:
                value = 1
                times += 1
                fail_start = i["timestamp"]
            if str(int(i["value"])) == "0" and value == 1:
                value = 0
                fail_second += i["timestamp"] - fail_start
                fail_start = end
        fail_second += end - fail_start
        if times == 0:
            return 0
        else:
            r = (end - start - fail_second)/times/3600
        return r

    def query_object_history(self, stmt: str):
        d = self.query(q=stmt)
        result = []
        for table in d:
            for record in table.records:
                result.append(
                    {
                        "id": record.values.get("id"),
                        "uid": record.values.get("uid"),
                        "value": record.get_value(),
                        "timestamp": record.get_time().timestamp(),
                    }
                )
        return result
