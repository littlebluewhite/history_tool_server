import json
import time

import redis
from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import sessionmaker, Session

from app.value_trace import ValueQueue
from function.API.API_object import APIObjectOperate
from dependencies.get_query_dependencies import CommonQuery, SimpleQuery
from dependencies.db_dependencies import create_get_db
from function.API.API_object import APIObjectFunction
from function.General_operate import GeneralOperate
from function.create_data_structure import create_update_dict, create_delete_dict
from app.influxdb.influxdb import InfluxDB


class APIObjectRouter(APIObjectFunction, APIObjectOperate):
    def __init__(self, module, redis_db: redis.Redis, influxdb: InfluxDB,
                 exc, db_session: sessionmaker, q: ValueQueue):
        self.db_session = db_session
        self.influxdb = influxdb
        self.simple_schemas = module.simple_schemas
        self.q = q
        APIObjectOperate.__init__(self, module, redis_db, exc)

    def create(self):
        router = APIRouter(
            prefix="/api/object",
            tags=["API", "Object"],
            dependencies=[]
        )

        create_schemas = self.create_schemas
        update_schemas = self.update_schemas
        multiple_update_schemas = self.multiple_update_schemas
        insert_schemas = self.insert_schemas
        get_value_schemas = self.get_value_schemas

        @router.on_event("startup")
        async def task_startup_event():
            GeneralOperate.clean_redis_by_name(self, "object_value")

        @router.get("/", response_model=list[self.main_schemas])
        async def get_object(common: CommonQuery = Depends(),
                             db: Session = Depends(create_get_db(self.db_session))):
            if common.pattern == "all":
                objects = self.object_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            else:
                id_set = self.object_operate.execute_sql_where_command(db, common.where_command)
                objects = self.object_operate.read_data_from_redis_by_key_set(id_set)[common.skip:][:common.limit]
            return [self.format_api_object(i) for i in objects]

        @router.get("/simple/", response_model=list[self.simple_schemas])
        async def get_simple_objects(common: SimpleQuery = Depends()):
            objects = self.object_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            return [self.format_simple_api_object(obj) for obj in objects]

        @router.get("/by_object_id/", response_model=list[self.main_schemas])
        async def get_objects_by_object_id(common: CommonQuery = Depends(),
                                           key: str = Query(...),
                                           db: Session = Depends(create_get_db(self.db_session))):
            key_set = set(key.replace(" ", "").split(","))
            id_list = self.object_operate.read_data_from_redis_by_key_set(key_set, 1)
            id_set = {i[0] for i in id_list}
            if common.pattern == "search":
                id_set1 = self.object_operate.execute_sql_where_command(db, common.where_command)
                id_set = id_set | id_set1
            nodes = self.object_operate.read_data_from_redis_by_key_set(id_set)[common.skip:][:common.limit]
            return [self.format_api_object(i) for i in nodes]

        @router.post("/", response_model=self.main_schemas)
        async def create_api_object(create_data: create_schemas,
                                    db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                create_dict = create_data.dict()
                object_base_create = self.object_base_operate.create_schemas(**create_dict["object_base"])
                object_base = self.object_base_operate.create_sql(db, [object_base_create])[0]
                o_create = self.object_operate.create_schemas(**create_dict, object_base_id=object_base.id)
                o = self.object_operate.create_sql(db, [o_create])[0]
                if create_dict.get("fake_data_config", None):
                    fdc_base_create = self.fdcBase_operate.create_schemas(
                        **create_dict["fake_data_config"]["fake_data_config_base"])
                    fdc_base = self.fdcBase_operate.create_sql(db, [fdc_base_create])[0]
                    fdc_create = self.fdc_operate.create_schemas(
                        **create_dict["fake_data_config"], fake_data_config_base_id=fdc_base.id, object_id=o.id)
                    fdc = self.fdc_operate.create_sql(db, [fdc_create])[0]
                db.refresh(o)

                # redis create data
                if create_dict.get("fake_data_config", None):
                    self.fdc_operate.update_redis_table([fdc])
                    self.fdcBase_operate.update_redis_table([fdc_base])
                self.object_operate.update_redis_table([o])
                self.object_base_operate.update_redis_table([object_base])

                # redis reload table
                self.object_operate.reload_redis_table(db, self.object_operate.reload_related_redis_tables, [o])

                return jsonable_encoder(o)

        @router.post("/multiple/", response_model=list[self.main_schemas])
        async def create_api_objects(create_data_list: list[create_schemas],
                                     db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                create_dict_list = []
                o_create_list = []
                o_base_create_list = []
                fdc_dict_list = []
                fdc_create_list = []
                fdc_base_create_list = []
                for create_data in create_data_list:
                    create_dict = create_data.dict()
                    create_dict_list.append(create_dict)
                    if create_dict["fake_data_config"]:
                        fdc_dict_list.append(create_dict["fake_data_config"])
                        fdc_base_create_list.append(self.fdcBase_operate.create_schemas(
                            **create_dict["fake_data_config"]["fake_data_config_base"]))
                    else:
                        fdc_dict_list.append(None)
                    o_base_create_list.append(self.object_base_operate.create_schemas(**create_dict["object_base"]))
                o_base_list = self.object_base_operate.create_sql(db, o_base_create_list)
                for create_dict, o_base in zip(create_dict_list, o_base_list):
                    o_create_list.append(self.object_operate.create_schemas(**create_dict, object_base_id=o_base.id))
                o_list = self.object_operate.create_sql(db, o_create_list)
                fdc_base_list = self.fdcBase_operate.create_sql(db, fdc_base_create_list)
                fdc_base_iterator = iter(fdc_base_list)
                for o, fdc_dict in zip(o_list, fdc_dict_list):
                    if fdc_dict is None:
                        continue
                    else:
                        fdc_base = next(fdc_base_iterator)
                        fdc_create_list.append(self.fdc_operate.create_schemas(
                            **fdc_dict, object_id=o.id, fake_data_config_base_id=fdc_base.id))
                fdc_list = self.fdc_operate.create_sql(db, fdc_create_list)
                # refresh object
                for o in o_list:
                    db.refresh(o)
                # update redis table
                self.fdc_operate.update_redis_table(fdc_list)
                self.fdcBase_operate.update_redis_table(fdc_base_list)
                self.object_operate.update_redis_table(o_list)
                self.object_base_operate.update_redis_table(o_base_list)

                self.object_operate.reload_redis_table(db, self.object_operate.reload_related_redis_tables, o_list)
                return jsonable_encoder(o_list)

        @router.patch("/{object_id}", response_model=self.main_schemas)
        async def update_api_object(update_data: update_schemas, object_id: int,
                                    db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                update_dict = update_data.dict()
                o = create_update_dict(create=False)
                o_base = create_update_dict(create=False)
                fdc = create_update_dict()
                fdc_base = create_update_dict()
                original_o_data = self.object_operate.read_data_from_redis_by_key_set({object_id})[0]
                self_ref_id_dict = self.object_operate.get_self_ref_id(
                    [self.object_operate.main_schemas(**original_o_data)])
                if not original_o_data["fake_data_config"] and update_dict["fake_data_config"]:
                    if update_dict["fake_data_config"]["fake_data_config_base"]:
                        fdc_base["create_list"].append(self.fdcBase_operate.create_schemas(
                            **update_dict["fake_data_config"]["fake_data_config_base"]))
                    else:
                        fdc_base["create_list"].append(self.fdcBase_operate.create_schemas())
                    fdc_base["sql_list"].extend(self.fdcBase_operate.create_sql(db, fdc_base["create_list"]))
                    fdc["create_list"].append(self.fdc_operate.create_schemas(
                        **update_dict["fake_data_config"], object_id=object_id,
                        fake_data_config_base_id=fdc_base["sql_list"][0].id))
                elif original_o_data["fake_data_config"] and update_dict["fake_data_config"]:
                    if update_dict["fake_data_config"]["fake_data_config_base"]:
                        fdc_base["update_list"].append(self.fdcBase_operate.multiple_update_schemas(
                            **update_dict["fake_data_config"]["fake_data_config_base"],
                            id=original_o_data["fake_data_config"]["fake_data_config_base"]["id"]))
                        fdc_base["sql_list"].extend(self.fdcBase_operate.update_sql(db, fdc_base["update_list"]))
                    fdc["update_list"].append(self.fdc_operate.multiple_update_schemas(
                        **update_dict["fake_data_config"], id=original_o_data["fake_data_config"]["id"]))
                    fdc["sql_list"].extend(self.fdc_operate.update_sql(db, fdc["update_list"]))
                if update_dict["object_base"]:
                    o_base["update_list"].append(self.object_base_operate.multiple_update_schemas(
                        **update_dict["object_base"], id=original_o_data["object_base"]["id"]))
                o["update_list"].append(self.object_operate.multiple_update_schemas(
                    **update_dict, id=object_id))
                o_base["sql_list"].extend(self.object_base_operate.update_sql(db, o_base["update_list"]))
                o["sql_list"].extend(self.object_operate.update_sql(db, o["update_list"]))
                # redis operate
                # redis delete index table
                if original_o_data["fake_data_config"]:
                    self.fdcBase_operate.delete_redis_index_table(
                        [original_o_data["fake_data_config"]["fake_data_config_base"]], fdc_base["update_list"])
                    self.fdc_operate.delete_redis_index_table(
                        [original_o_data["fake_data_config"]], fdc["update_list"])
                self.object_base_operate.delete_redis_index_table(
                    [original_o_data["object_id"]], o_base["update_list"])
                self.object_operate.delete_redis_index_table([original_o_data], o["update_list"])
                # reload redis table
                self.fdcBase_operate.update_redis_table(fdc_base["sql_list"])
                print(fdc["sql_list"])
                self.fdc_operate.update_redis_table(fdc["sql_list"])
                self.object_base_operate.update_redis_table(o_base["sql_list"])
                self.object_operate.update_redis_table(o["sql_list"])
                # reload related redis table
                self.object_operate.reload_redis_table(db, self.object_operate.reload_related_redis_tables,
                                                       o["sql_list"], self_ref_id_dict)
                return self.format_api_object(jsonable_encoder(o["sql_list"][0]))

        @router.patch("/multiple/", response_model=list[self.main_schemas])
        async def update_api_object(
                update_list: list[multiple_update_schemas],
                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                update_dict_list = [i.dict() for i in update_list]
                fdc = create_update_dict()
                fdc_base = create_update_dict()
                o = create_update_dict(create=False)
                o_base = create_update_dict(create=False)
                original_data_list = self.object_operate.read_data_from_redis_by_key_set({i.id for i in update_list})
                original_key_id_dict: dict = {i["id"]: i for i in original_data_list}
                self_ref_id_dict = self.object_operate.get_self_ref_id(
                    [self.object_operate.main_schemas(**i) for i in original_data_list])
                for data in update_dict_list:
                    original_o: dict = original_key_id_dict[data["id"]]
                    original_o_base: dict = original_o["object_base"]
                    original_fdc = original_o["fake_data_config"]
                    if not original_fdc and data["fake_data_config"]:
                        if data["fake_data_config"]["fake_data_config_base"]:
                            fdc_base["create_list"].append(self.fdcBase_operate.create_schemas(
                                **data["fake_data_config"]["fake_data_config_base"]))
                        else:
                            fdc_base["create_list"].append(self.fdcBase_operate.create_schemas())
                        fdc["create_list"].append(self.fdc_operate.create_schemas(
                            **data["fake_data_config"], object_id=original_o["id"]))
                    elif original_fdc and data["fake_data_config"]:
                        if data["fake_data_config"]["fake_data_config_base"]:
                            fdc_base["update_list"].append(self.fdcBase_operate.multiple_update_schemas(
                                **data["fake_data_config"]["fake_data_config_base"],
                                id=original_fdc["fake_data_config_base"]["id"]))
                        fdc["update_list"].append(self.fdc_operate.multiple_update_schemas(
                            **data["fake_data_config"], id=original_fdc["id"]))
                    if data["object_base"]:
                        o_base["update_list"].append(self.object_base_operate.multiple_update_schemas(
                            **data["object_base"], id=original_o_base["id"]))
                    o["update_list"].append(self.object_operate.multiple_update_schemas(
                        **data))
                # DB operate
                fdc_base["sql_list"].extend(self.fdcBase_operate.create_sql(db, fdc_base["create_list"]))
                # fdc create schemas add fdc_base_sql_data id
                for fdc_base_sql_data, create_data in zip(fdc_base["sql_list"], fdc["create_list"]):
                    create_data.fake_data_config_base_id = fdc_base_sql_data.id
                fdc["sql_list"].extend(self.fdc_operate.create_sql(db, fdc["create_list"]))
                fdc_base["sql_list"].extend(self.fdcBase_operate.update_sql(db, fdc_base["update_list"]))
                fdc["sql_list"].extend(self.fdc_operate.update_sql(db, fdc["update_list"]))
                o_base["sql_list"].extend(self.object_base_operate.update_sql(db, o_base["update_list"]))
                o["sql_list"].extend(self.object_operate.update_sql(db, o["update_list"]))
                # redis operate
                # redis delete index table
                self.fdcBase_operate.delete_redis_index_table(
                    [i["fake_data_config"]["fake_data_config_base"] for i in original_data_list
                     if i["fake_data_config"]], fdc_base["update_list"])
                self.fdc_operate.delete_redis_index_table(
                    [i["fake_data_config"] for i in original_data_list if i["fake_data_config"]], fdc["update_list"])
                self.object_base_operate.delete_redis_index_table(
                    [i["object_base"] for i in original_data_list if i["object_base"]], o_base["update_list"])
                self.object_operate.delete_redis_index_table([i for i in original_data_list], o["update_list"])
                # update redis table
                self.fdcBase_operate.update_redis_table(fdc_base["sql_list"])
                self.fdc_operate.update_redis_table(fdc["sql_list"])
                self.object_base_operate.update_redis_table(o_base["sql_list"])
                self.object_operate.update_redis_table(o["sql_list"])
                # reload related redis table
                self.object_operate.reload_redis_table(db, self.object_operate.reload_related_redis_tables,
                                                       o["sql_list"], self_ref_id_dict)
                return [self.format_api_object(i) for i in jsonable_encoder(o["sql_list"])]

        @router.delete("/{object_id}")
        async def delete_api_object(object_id: int, db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                original_data_list = self.object_operate.read_data_from_redis_by_key_set({object_id})
                original_data = original_data_list[0]
                fdc = create_delete_dict()
                fdc_base = create_delete_dict()
                original_o_base = original_data["object_base"]
                if original_data["fake_data_config"]:
                    original_fdc = original_data["fake_data_config"]
                    original_fdc_base = original_data["fake_data_config"]["fake_data_config_base"]
                    fdc_base["id_set"].add(original_fdc_base["id"])
                    fdc["id_set"].add(original_fdc["id"])
                    fdc_base["data_list"].append(original_fdc_base)
                    fdc["data_list"].append(original_fdc)
                # delete object_object_group
                try:
                    oo_groups_id_list = self.oo_groups_operate.read_data_from_redis_by_key_set({object_id}, 1)[0]
                except self.exc:
                    oo_groups_id_list = []
                oo_groups_dict_list = self.oo_groups_operate.read_data_from_redis_by_key_set(set(oo_groups_id_list))
                self.oo_groups_operate.delete_sql(db, set(oo_groups_id_list), False)
                self.fdc_operate.delete_sql(db, fdc["id_set"], False)
                self.object_operate.delete_sql(db, {original_data["id"]}, False)
                self.object_base_operate.delete_sql(db, {original_o_base["id"]}, False)
                self.fdcBase_operate.delete_sql(db, fdc_base["id_set"], False)
                # delete redis table
                self.oo_groups_operate.delete_redis_table(oo_groups_dict_list)
                self.fdcBase_operate.delete_redis_table(fdc_base["data_list"])
                self.fdc_operate.delete_redis_table(fdc["data_list"])
                self.object_base_operate.delete_redis_table([original_o_base])
                self.object_operate.delete_redis_table([original_data])
                # reload related redis table
                self.object_operate.reload_redis_table(
                    db, self.object_operate.reload_related_redis_tables, original_data_list)
                self.oo_groups_operate.reload_redis_table(
                    db, self.oo_groups_operate.reload_related_redis_tables, oo_groups_dict_list)
                return "ok"

        @router.delete("/multiple/")
        async def delete_api_objects(id_set: set[int], db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                self.delete_multiple_object(id_set, db)
                return "ok"

        @router.put("/insert_value/")
        async def insert_value(insert_list: list[insert_schemas]):
            id_set = set()
            id_value_dict: dict = dict()
            insert_data: dict = dict()
            for data in insert_list:
                id_value_dict[data.id] = data.value
                id_set.add(data.id)
            object_list = self.object_operate.read_data_from_redis_by_key_set(id_set)
            timestamp = int(time.time())
            for data in object_list:
                v = {
                    "id": data["id"],
                    "object_id": data["object_id"],
                    "value": id_value_dict[data["id"]],
                    "timestamp": timestamp
                }
                insert_data[data["id"]] = v
                self.influxdb.write_in(data["id"], data["object_id"], id_value_dict[data["id"]])
                self.redis.hset("object_value", data["id"], json.dumps(v))
            self.q.insert_data(insert_data)
            return "ok"

        @router.get("/value/", response_model=list[get_value_schemas])
        async def get_value(id_list: list[int] = Query(...)):
            result = []
            for _id in set(id_list):
                data = self.redis.hget("object_value", _id)
                if not data:
                    continue
                data = json.loads(data)
                result.append(get_value_schemas(id=_id, object_id=data["object_id"],
                                                value=data["value"], timestamp=data["timestamp"]))
            return result

        @router.get("/history_value/{_id}", response_model=list[get_value_schemas])
        async def get_history_value(_id: int, start: int = Query(...), end: int = Query(None)):
            return self.influxdb.query_by_id(_id, start, end)

        return router
