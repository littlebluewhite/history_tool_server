import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

from .influxdb import InfluxDB


class InfluxOperate:
    def __init__(self, influxdb: InfluxDB, exc):
        self.influxdb = influxdb
        self.exc = exc
        self.__bucket = influxdb.bucket
        self.__org = influxdb.org
        self.writer = self.influxdb.client.write_api(write_options=SYNCHRONOUS)
        self.reader = self.influxdb.client.query_api()

    def change_bucket(self, bucket: str):
        self.__bucket = bucket

    def change_org(self, org: str):
        self.__org = org

    def show_bucket(self):
        return self.__bucket

    def show_org(self):
        return self.__org

    def write(self, p: influxdb_client.Point):
        # ex:
        # p = influxdb_client.Point(
        #     "object_value").tag("id", str(_id)) \
        #     .tag("uid", str(uid)) \
        #     .field("value", str(value))
        self.writer.write(bucket=self.__bucket, org=self.__org, record=p)

    def query(self, q: str):
        # ex:
        # query = f'''from(bucket:"node_object")
        # |> range(start: {start}, stop: {end})
        # |> filter(fn:(r) => r._measurement == "object_value")
        # |> filter(fn:(r) => r.id == "{_id}")
        # |> filter(fn:(r) => r._field == "value")'''
        data = self.reader.query(org=self.__org, query=q)
        return data
