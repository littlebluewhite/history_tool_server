from data.enum.fn import FnEnum
from function.General_operate import GeneralOperate


class APIHistoryOperate(GeneralOperate):
    def __init__(self, module, redis_db, influxdb, exc):
        self.exc = exc
        GeneralOperate.__init__(self, module, redis_db, influxdb, exc)

    def read_object_value_history(self, start: str, stop: str, _id: str = "",
                                  uid: str = "", period: str = "",
                                  fn: FnEnum = FnEnum.mean):
        stop_value = ""
        if stop != "":
            stop_value = f", stop : {stop}"
        id_value = ""
        if _id != "":
            id_value = f"""|> filter(fn:(r) => r.id == "{_id}")"""
        uid_value = ""
        if uid != "":
            uid_value = f"""|> filter(fn:(r) => r.uid == "{uid}")"""
        moving_value = ""
        match fn:
            case FnEnum.mean:
                fn = "last"
                moving_value = f"|> timedMovingAverage(every: {period}, period: {period})"
            case FnEnum.max:
                fn = "max"
            case FnEnum.last:
                fn = "last"
        stmt = f"""from(bucket:"node_object")
|> range(start: {start}{stop_value})
|> filter(fn:(r) => r._measurement == "object_value")
{id_value}
{uid_value}
{moving_value}
|> aggregateWindow(every: {period}, fn: {fn})
|> fill(usePrevious: true)
"""
        print(stmt)
        data = self.query(q=stmt)
        result = []
        for table in data:
            for record in table.records:
                result.append(
                    {
                        "id": record.values.get("id"),
                        "object_id": record.values.get("object_id"),
                        "value": record.get_value(),
                        "timestamp": record.get_time().timestamp(),
                    }
                )
        return result
