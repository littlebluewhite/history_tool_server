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
{id_str}
{uid_str}
{moving_str}
|> aggregateWindow(every: {period}, fn: {fn})
|> fill(usePrevious: true)
"""
        data = self.query(q=stmt)
        result = []
        for table in data:
            for record in table.records:
                result.append(
                    {
                        "id": record.values.get("id"),
                        "uid": record.values.get("uid"),
                        "value": record.get_value(),
                        "timestamp": record.get_time().timestamp(),
                    }
                )
        if limit is not None:
            result = result[skip:skip + limit]
        else:
            result = result[skip:]
        return result
