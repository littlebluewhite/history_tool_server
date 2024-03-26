import json
from typing import Any

import redis
from fastapi.encoders import jsonable_encoder


class RedisOperate:
    def __init__(self, redis_db: redis.Redis, exc):
        self.redis = redis_db
        self.exc = exc

    def clean_redis_by_name(self, table_name):
        if self.redis.exists(table_name):
            if self.redis.delete(table_name) == 1:
                print(f"clean redis table: {table_name}")

    def write_to_redis(self, table_name: str, key: str | None = None,
                       value: str | int | None = None, mapping: dict | None = None, items: list | None = None):
        self.redis.hset(table_name, key, value, mapping, items)

    def write_sql_data_to_redis(self, table_name: str,
                                sql_data_list: list, schemas_model,
                                key: str = "id", update_list: list = None) -> list:
        """

        :param table_name:
        :param sql_data_list:
        :param schemas_model:
        :param key:
        :param update_list: update sql table可以加此參數，減少對redis的訪問，不加也可以
        :return:
        """
        update_dict = dict()
        if update_list is None:
            update_list = list()
        for update_data in update_list:
            update_dict[update_data.id] = update_data
        result: list[Any] = list()
        # 將要寫入redis的資料
        set_items: list[tuple[str, str]] = list()
        for sql_data in sql_data_list:
            row = schemas_model(**jsonable_encoder(sql_data))
            # 寫入主表
            if key == "id":
                value = row.json()
                set_items.extend((getattr(row, key), value))
            # 寫入附表(index table)
            elif not update_list or getattr(update_dict.get(row.id, None), key, None) is not None:
                # sql type 是 json list的情況
                if isinstance(getattr(row, key), list):
                    for item in getattr(row, key):
                        value_list = list()
                        original_data = self.redis.hget(table_name, item)
                        if original_data:
                            value_list = json.loads(original_data)
                        set_items.extend((item, json.dumps(list(set(value_list + [row.id])))))
                # sql type 是單一值的情況
                else:
                    item = getattr(row, key)
                    # key可能為空值得情況
                    if item is not None:
                        value_list = list()
                        original_data = self.redis.hget(table_name, item)
                        if original_data:
                            value_list = json.loads(original_data)
                        set_items.extend((item, json.dumps(list(set(value_list + [row.id])))))

            result.append(row)
        # 統一set data
        if set_items:
            self.redis.hset(table_name, items=set_items)
        return result

    def read_redis_return_dict(self, table_name: str, key_set: set) -> dict:
        if not key_set:
            return dict()
        key_list = list(key_set)
        raw_data = self.redis.hmget(table_name, key_list)
        # return {key.decode("utf-8"): json.loads(value.decode("utf-8"))
        #         for key, value in raw_data.items()}
        return {key: json.loads(data.decode("utf-8")) for key, data in zip(key_list, raw_data)}

    def read_redis_all_data(self, table_name: str) -> list[dict]:
        result = []
        for datum in self.redis.hvals(table_name):
            result.append(json.loads(datum))
        return result

    def read_redis_data_without_exception(self, table_name: str, key_set: set) -> list:
        if not key_set:
            return list()
        raw_data = self.redis.hmget(table_name, list(key_set))
        return [json.loads(data) for data in raw_data if data is not None]

    def read_redis_data(self, table_name: str, key_set: set) -> list:
        if not key_set:
            return list()
        raw_data = self.redis.hmget(table_name, list(key_set))
        if None in raw_data:
            raise self.exc(status_code=404, detail=f"id:{key_set} is not exist")
        return [json.loads(data) for data in raw_data]

    def delete_redis_data(self, table_name: str, data_list: list, schemas_model,
                          key: str = "id", update_list: list = None) -> str:
        """

        :param table_name:
        :param data_list:
        :param schemas_model:
        :param key:
        :param update_list: 如果是因為update sql table需要刪除redis，要加此參數
        :return:
        """
        p = self.redis.pipeline()
        update_dict = dict()
        if update_list is None:
            update_list = list()
        for update_data in update_list:
            update_dict[update_data.id] = update_data
        for data in data_list:
            row = schemas_model(**jsonable_encoder(data))
            # 刪除主表
            if key == "id":
                p.hdel(table_name, getattr(row, key))
            # 刪除附表(index table)
            elif not update_list or getattr(update_dict.get(row.id, None), key, None) is not None:
                # sql type 是 json list的情況
                if isinstance(getattr(row, key), list):
                    for item in getattr(row, key):
                        value_list = json.loads(self.redis.hget(table_name, item))
                        value_list.remove(row.id)
                        if not value_list:
                            p.hdel(table_name, item)
                        else:
                            p.hset(table_name, item, json.dumps(value_list))
                # sql type 是單一值的情況
                else:
                    item = getattr(row, key)
                    # key可能為空值得情況
                    if item is not None:
                        value_list = json.loads(self.redis.hget(table_name, item))
                        value_list.remove(row.id)
                        if not value_list:
                            p.hdel(table_name, item)
                        else:
                            p.hset(table_name, item, json.dumps(value_list))
        p.execute()
        return "Ok"
