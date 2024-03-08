# 1. update the sql table
# 2. update redis_db tables which the sql table generate
# 3, reload the redis_db tables which are related to the sql table
import redis
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, sessionmaker

from app.SQL.sql_operate import SQLOperate
from app.influxdb.influxdb import InfluxDB
from app.influxdb.influxdb_operate import InfluxOperate
from app.redis_db.redis_operate import RedisOperate


class GeneralOperate(RedisOperate, SQLOperate, InfluxOperate):
    def __init__(self, module, redis_db: redis.Redis, influxdb: InfluxDB, exc):
        self.module = module
        self.redis_tables = module.redis_tables
        self.main_schemas = module.main_schemas
        self.create_schemas = module.create_schemas
        self.update_schemas = module.update_schemas
        self.multiple_update_schemas = module.multiple_update_schemas
        self.reload_related_redis_tables = module.reload_related_redis_tables
        RedisOperate.__init__(self, redis_db, exc)
        SQLOperate.__init__(self, exc)
        InfluxOperate.__init__(self, influxdb, exc)

    # reload redis_db table from sql for INITIAL
    def initial_redis_data(self, db_session: sessionmaker):
        db = db_session()
        # sql 取資料
        sql_data = SQLOperate.get_all_sql_data(db, self.sql_model)
        self.write_to_redis("count", self.module.name, len(sql_data))
        for table in self.redis_tables:
            # 清除redis表
            self.clean_redis_by_name(table["name"])
            # 將sql資料寫入redis表
            self.write_sql_data_to_redis(table["name"], sql_data, self.main_schemas, table["key"])
        db.close()

    def reload_redis_table(self, db, reload_related_redis_tables, sql_data_list, origin_ref_id_dict=None):
        if origin_ref_id_dict is None:
            origin_ref_id_dict = dict()
        dict_data_list = jsonable_encoder(sql_data_list)
        for key in reload_related_redis_tables:
            if key == "self_field":
                for table in reload_related_redis_tables["self_field"]:
                    # ref_id_set = {getattr(i, table["field"]) for i in sql_data_list}
                    ref_id_set = {i[table["field"]] for i in dict_data_list}
                    # 取得需要更新的id交集
                    old_ref_id_set: set = origin_ref_id_dict.get(table["field"], None)
                    if old_ref_id_set:
                        ref_id_set |= old_ref_id_set
                    # print("id_set: ", id_set)
                    sql_data_list2 = self.__reload_redis_from_sql(db, table["module"], ref_id_set)
                    self.reload_redis_table(db, table["module"].reload_related_redis_tables, sql_data_list2)
            elif key == "outside_field":
                for table in reload_related_redis_tables["outside_field"]:
                    # id_set = {getattr(i, "id") for i in sql_data_list}
                    id_set = {i["id"] for i in dict_data_list}
                    sql_data_list2 = self.__reload_redis_from_sql(db, table["module"], id_set, table["field"])
                    self.reload_redis_table(db, table["module"].reload_related_redis_tables, sql_data_list2)
            elif key == "many2many":
                for table in reload_related_redis_tables["many2many"]:
                    old_ref_id_set: set = origin_ref_id_dict.get(table["other_id_field"], set())
                    ref_id_set: set = self.get_many2many_ref_id(
                        # db, {i.id for i in sql_data_list}).get(table["other_id_field"], set())
                        db, {i["id"] for i in dict_data_list}).get(table["other_id_field"], set())
                    ref_id_set |= old_ref_id_set
                    sql_data_list2 = self.__reload_redis_from_sql(db, table["module"], ref_id_set, "id")
                    self.reload_redis_table(db, table["module"].reload_related_redis_tables, sql_data_list2)

    def __reload_redis_from_sql(self, db, module, field_value_set: set, sql_field: str = "id"):
        sql_data_list: list = SQLOperate.get_sql_data(self, db, module.sql_model, field_value_set, sql_field, False)
        for table in module.redis_tables[:1]:
            RedisOperate.write_sql_data_to_redis(
                self, table["name"], sql_data_list, module.main_schemas, table["key"])
        return sql_data_list

    def read_all_data_from_sql(self, db) -> list:
        return SQLOperate.get_all_sql_data(db, self.sql_model)

    def read_data_from_sql_by_id_set(self, db, id_set: set) -> list:
        return SQLOperate.get_sql_data(self, db, self.sql_model, id_set)

    def read_all_data_from_redis(self, table_index: int = 0) -> list:
        return RedisOperate.read_redis_all_data(self, self.redis_tables[table_index]["name"])

    def read_data_from_redis_by_key_set(self, key_set: set, table_index: int = 0) -> list:
        return RedisOperate.read_redis_data(self, self.redis_tables[table_index]["name"], key_set)

    def read_table_count(self):
        return self.read_redis_data("count", {self.module.name})[0]

    def create_data(self, db: Session, data_list: list) -> list:
        sql_data_list = self.create_sql(db, data_list)
        self.update_redis_table(sql_data_list)
        self.reload_redis_table(db, self.reload_related_redis_tables, sql_data_list)
        return sql_data_list

    def update_data(self, db: Session, update_list: list) -> list:
        # 取得更新前的self reference id
        original_data_list = self.read_data_from_redis_by_key_set({i.id for i in update_list})
        self_ref_id_dict = self.get_self_ref_id([self.main_schemas(**i) for i in original_data_list])
        # 取得更新前的many to many reference id
        many_ref_id_dict = self.get_many2many_ref_id(db, {i.id for i in update_list})
        # 合併ref_dict
        original_ref_id_dict = self_ref_id_dict | many_ref_id_dict
        # 刪除有關聯的redis資料
        self.delete_redis_index_table(original_data_list, update_list)
        # 更新SQL
        sql_data_list = self.update_sql(db, update_list)

        # 重寫自身redis表
        self.update_redis_table(sql_data_list)

        # 重寫redis相關表
        self.reload_redis_table(
            db, self.reload_related_redis_tables, sql_data_list, original_ref_id_dict)
        return sql_data_list

    def delete_data(self, db: Session, id_set: set[int]) -> str:
        data_list = self.delete_sql(db, id_set)
        self.delete_redis_table(data_list)
        self.reload_redis_table(db, self.reload_related_redis_tables, data_list)
        return "Ok"

    def delete_redis_table(self, sql_data_list):
        for table in self.redis_tables:
            RedisOperate.delete_redis_data(
                self, table["name"], sql_data_list, self.main_schemas, table["key"]
            )

    def add_id_in_update_data(self, update_data, data_id):
        return self.multiple_update_schemas(**update_data.dict(), id=data_id)

    def create_sql(self, db, data_list: list) -> list:
        sql_data_list = SQLOperate.create_multiple_sql_data(self, db, data_list, self.sql_model)
        c = self.read_table_count()
        self.write_to_redis("count", self.module.name, len(sql_data_list)+c)
        return sql_data_list

    def update_sql(self, db, update_list: list) -> list:
        return SQLOperate.update_multiple_sql_data(self, db, update_list, self.sql_model)

    def delete_sql(self, db, id_set: set, return_sql: bool = True) -> list:
        data_list = []
        if return_sql:
            data_list = RedisOperate.read_redis_data(self, self.redis_tables[0]["name"], id_set)
        SQLOperate.delete_multiple_sql_data(self, db, id_set, self.sql_model)
        c = self.read_table_count()
        self.write_to_redis("count", self.module.name, c-len(id_set))
        return data_list

    def update_redis_table(self, sql_data_list: list):
        for table in self.redis_tables:
            RedisOperate.write_sql_data_to_redis(
                self, table["name"], sql_data_list, self.main_schemas, table["key"]
            )

    # 刪除有關聯的redis資料
    def delete_redis_index_table(self, original_data_list: list, update_list: list):
        for table in self.redis_tables[1:]:
            RedisOperate.delete_redis_data(
                self, table["name"], original_data_list, self.main_schemas, table["key"], update_list
            )

    def reload_relative_table(self, db: Session, sql_data_list: list, original_ref_id_dict=None):
        if original_ref_id_dict is None:
            original_ref_id_dict = dict()
        self.reload_redis_table(db, self.reload_related_redis_tables, sql_data_list, original_ref_id_dict)

    # 取得原本未被更改的reference的id
    def get_self_ref_id(self, update_list) -> dict:
        result = dict()
        if self.reload_related_redis_tables["self_field"]:
            for table in self.reload_related_redis_tables["self_field"]:
                id_set = {getattr(i, table["field"]) for i in update_list}
                result[table["field"]] = id_set
        # print("result: ", result)
        return result

    def get_many2many_ref_id(self, db, id_set) -> dict:
        result = dict()
        if self.reload_related_redis_tables.get("many2many"):
            for table in self.reload_related_redis_tables["many2many"]:
                stmt = self.create_many2many_stmt(table, id_set)
                other_id_set: set = {i[0] for i in db.execute(stmt)}
                result[table["other_id_field"]] = other_id_set
        return result

    def combine_sql_command(self, where_command):
        return f"select id from {self.sql_model.sql_table_name} {where_command}"

    def execute_sql_where_command(self, db: Session, where_command) -> set:
        stmt = self.combine_sql_command(where_command)
        id_set = {i[0] for i in db.execute(stmt)}
        return id_set

    def create_many2many_stmt(self, table: dict, id_set: set) -> str:
        if len(id_set) < 1:
            raise self.exc(status_code=406, detail="reference id is not correct")
        elif len(id_set) == 1:
            where_condition_stmt = f"{str(tuple(id_set))}".replace(',', '')
        else:
            where_condition_stmt = f"{str(tuple(id_set))}"
        ref_table = table["ref_table"]
        other_id_field = table["other_id_field"]
        self_id_field = table["self_id_field"]
        return f"select {other_id_field} from {ref_table} where {self_id_field} in {where_condition_stmt}"
