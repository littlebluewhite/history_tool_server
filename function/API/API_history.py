import math
import time

from general_operator.function.General_operate import GeneralOperate

from data.enum.fn import FnEnum


class APIHistoryFunction:
    def __init__(self):
        pass

    @staticmethod
    def get_trigger_time(trigger_value: str, start: int, stop: int, data: list) -> dict:
        # search start value
        value = ""
        new_data = []
        for i, d in enumerate(data):
            if d["timestamp"] < start:
                value = str(int(d["value"]))
            else:
                new_data = data[i:]
                break
        for i, d in enumerate(new_data):
            if d["timestamp"] > stop:
                new_data = new_data[:i]
                break

        times = 0

        # initial trigger start
        trigger_start = 0
        if value == trigger_value:
            trigger_start = start
            times += 1

        trigger_second = 0
        # count trigger time second
        for d in new_data:
            if str(int(d["value"])) == trigger_value and value != trigger_value:
                value = trigger_value
                times += 1
                trigger_start = d["timestamp"]
            elif str(int(d["value"])) != trigger_value and value == trigger_value:
                value = str(d["value"])
                trigger_second += d["timestamp"] - trigger_start
                trigger_start = stop
        trigger_second += stop - trigger_start
        result = {
            "trigger_times": times,
            "trigger_second": trigger_second,
        }
        if times == 0:
            result["trigger_second"] = 0
        return result

    @staticmethod
    def check_error_times(records, period, recover_value: str) -> list[int]:
        result = [0 for i in period]
        check = 1
        flag = False
        for r in records:
            if str(int(r["value"])) != recover_value and not flag:
                while check < len(period) and period[check] < r["timestamp"]:
                    check += 1
                for i in range(0, check):
                    result[i] += 1
                flag = True
            if str(int(r["value"])) == recover_value and flag:
                flag = False
        return result

    @staticmethod
    def deal_data_list(data) -> list[list]:
        result = []
        for table in data:
            r = []
            for record in table.records:
                r.append(
                    {
                        "id": record.values.get("id"),
                        "uid": record.values.get("uid"),
                        "value": record.get_value(),
                        "timestamp": record.get_time().timestamp(),
                    }
                )
            r = sorted(r, key=lambda x: x["timestamp"])
            result.append(r)
        return result


class APIHistoryOperate(GeneralOperate, APIHistoryFunction):
    def __init__(self, module, redis_db, influxdb, exc):
        self.exc = exc
        GeneralOperate.__init__(self, module, redis_db, influxdb, exc)
        self.query_before_seconds = 60 * 60 * 24 * 3

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
        result = sorted(result, key=lambda x: x["timestamp"])
        trigger_data = self.get_trigger_time("1", 0, int(time.time()), result)
        start = math.inf
        end = time.time()
        fail_start = 0
        fail_second = 0
        value = 0
        times = 0
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
        if trigger_data["trigger_times"] == 0:
            return "infinity"
        else:
            r = (end - result[0]["timestamp"] - trigger_data["trigger_second"]) / times / 3600
        return r

    def query_object_history(self, stmt: str) -> list:
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

    def object_switch_times(self, start: str, period: list[int], stop: str, recover_value: str,
                            _ids: list[str]) -> dict[int, dict[str, any]]:
        stop_str = ""
        if stop != "":
            stop_str = f", stop : {stop}"
        ids_str = """|> filter(fn:(r) => """
        combine = " or ".join([f'''r.id == "{_id}"''' for _id in _ids]) + ")"
        ids_str += combine
        stmt = f"""from(bucket:"node_object")
|> range(start: {start}{stop_str})
|> filter(fn:(r) => r._measurement == "object_value")
|> filter(fn:(r) => r._field == "value")
{ids_str}"""
        d = self.query(q=stmt)
        result = dict()
        data = self.deal_data_list(d)
        for r in data:
            period2 = period.copy()
            if r:
                period2 = [r[0]["timestamp"]] + period2
            error_times = self.check_error_times(r, period2, recover_value)
            last_value = r[-1]["value"]
            result[r[0]["id"]] = {
                "error_times": error_times,
                "last_value": last_value
            }
        return result

    def get_trigger_seconds(self, trigger_value, start: int, stop: int, _ids, _uids):
        if _ids is None:
            _ids = []
        if _uids is None:
            _uids = []
        start = start - self.query_before_seconds
        stop_str = ""
        if stop != "":
            stop_str = f", stop : {stop}"
        ids_str = """|> filter(fn:(r) => """
        combine = " or ".join([f'''r.id == "{_id}"''' for _id in _ids])
        combine2 = " or ".join([f'''r.uid == "{_uid}"''' for _uid in _uids]) + ")"
        ids_str = ids_str + combine + combine2
        stmt = f"""from(bucket:"node_object")
|> range(start: {start}{stop_str})
|> filter(fn:(r) => r._measurement == "object_value")
|> filter(fn:(r) => r._field == "value")
{ids_str}"""
        d = self.query(q=stmt)
        result = dict()
        data = self.deal_data_list(d)
        for r in data:
            s = self.get_trigger_time(trigger_value, start, stop, r)["trigger_second"]
            result[r[0]["id"]] = s
            result[r[0]["uid"]] = s

        return result
