import redis

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import sessionmaker, Session

from dependencies.get_query_dependencies import CommonQuery, SimpleQuery
from dependencies.db_dependencies import create_get_db
from function.API.API_node import APINodeOperate
from function.create_data_structure import create_update_dict


class APINodeRouter(APINodeOperate):
    def __init__(self, module, redis_db: redis.Redis, exc, db_session: sessionmaker):
        self.db_session = db_session
        self.simple_schemas = module.simple_schemas
        APINodeOperate.__init__(self, module, redis_db, exc)

    def create(self):
        router = APIRouter(
            prefix="/api/node",
            tags=["API", "Node"],
            dependencies=[]
        )

        create_schemas = self.create_schemas
        update_schemas = self.update_schemas
        multiple_update_schemas = self.multiple_update_schemas

        @router.get("/", response_model=list[self.main_schemas])
        async def get_nodes(common: CommonQuery = Depends(),
                            db: Session = Depends(create_get_db(self.db_session))):
            if common.pattern == "all":
                nodes = self.node_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            else:
                id_set = self.node_operate.execute_sql_where_command(db, common.where_command)
                nodes = self.node_operate.read_data_from_redis_by_key_set(id_set)[common.skip:][:common.limit]
            return [self.format_api_node(i) for i in nodes]

        @router.get("/simple/", response_model=list[self.simple_schemas])
        async def get_simple_nodes(common: SimpleQuery = Depends()):
            nodes = self.node_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            return [self.format_simple_api_node(node) for node in nodes]

        @router.get("/by_node_id/", response_model=list[self.main_schemas])
        async def get_nodes_by_node_id(common: CommonQuery = Depends(),
                                       key: str = Query(...),
                                       db: Session = Depends(create_get_db(self.db_session))):
            key_set = set(key.replace(" ", "").split(","))
            id_list = self.node_operate.read_data_from_redis_by_key_set(key_set, 1)
            id_set = {i[0] for i in id_list}
            if common.pattern == "search":
                id_set1 = self.node_operate.execute_sql_where_command(db, common.where_command)
                id_set = id_set | id_set1
            nodes = self.node_operate.read_data_from_redis_by_key_set(id_set)[common.skip:][:common.limit]
            return [self.format_api_node(i) for i in nodes]

        @router.post("/", response_model=self.main_schemas)
        async def create_api_node(create_data: create_schemas,
                                  db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                create_dict = create_data.dict()
                # DB table "node_base" create data
                node_base_create = self.node_base_operate.create_schemas(**create_dict["node_base"])
                node_base = self.node_base_operate.create_sql(db, [node_base_create])[0]
                # DB table "node" create data
                node_create = self.node_operate.create_schemas(**create_dict, node_base_id=node_base.id)
                node = self.node_operate.create_sql(db, [node_create])[0]
                # if "device info" exists, DB table "device_info" create data
                if create_dict["node_base"]["device_info"]:
                    device_info_create = self.device_info_operate.create_schemas(
                        **create_dict["node_base"]["device_info"], node_base_id=node_base.id)
                    device_info_list = self.device_info_operate.create_sql(db, [device_info_create])
                # if "third_dimension_instance" exists, DB table "third_dimension_instance" create data
                if create_dict["third_dimension_instance"]:
                    third_dimension_instance_create = self.third_d_operate.create_schemas(
                        **create_dict["third_dimension_instance"], node_id=node.id)
                    third_dimension_instance_list = self.third_d_operate.create_sql(
                        db, [third_dimension_instance_create])
                db.refresh(node_base)
                db.refresh(node)

                # redis_db create data
                if create_dict["node_base"]["device_info"]:
                    self.device_info_operate.update_redis_table(device_info_list)
                if create_dict["third_dimension_instance"]:
                    self.third_d_operate.update_redis_table(third_dimension_instance_list)
                self.node_base_operate.update_redis_table([node_base])
                self.node_operate.update_redis_table([node])

                # redis_db reload table --> parent node
                self.node_operate.reload_redis_table(db, self.node_operate.reload_related_redis_tables, [node])

                return jsonable_encoder(node)

        @router.post("/multiple/", response_model=list[self.main_schemas])
        async def create_api_nodes(create_data_list: list[create_schemas],
                                   db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                create_dict_list = []
                node_base_create_list = []
                device_info_dict_list = []
                tdi_dict_list = []
                for create_data in create_data_list:
                    create_dict = create_data.dict()
                    create_dict_list.append(create_dict)
                    if create_dict["node_base"]["device_info"]:
                        device_info_dict_list.append(create_dict["node_base"]["device_info"])
                    else:
                        device_info_dict_list.append(None)
                    if create_dict["third_dimension_instance"]:
                        tdi_dict_list.append(create_dict["third_dimension_instance"])
                    else:
                        tdi_dict_list.append(None)
                    node_base_create_list.append(self.node_base_operate.create_schemas(**create_dict["node_base"]))
                node_base_list = self.node_base_operate.create_sql(db, node_base_create_list)
                node_create_list = []
                for create_dict, node_base in zip(create_dict_list, node_base_list):
                    node_create = self.node_operate.create_schemas(**create_dict, node_base_id=node_base.id)
                    node_create_list.append(node_create)
                node_list = self.node_operate.create_sql(db, node_create_list)
                device_info_create_list = []
                for node_base, device_info_dict in zip(node_base_list, device_info_dict_list):
                    if device_info_dict is None:
                        continue
                    else:
                        device_info_create = self.device_info_operate.create_schemas(
                            **device_info_dict, node_base_id=node_base.id)
                        device_info_create_list.append(device_info_create)
                device_info_list = self.device_info_operate.create_sql(db, device_info_create_list)
                tdi_create_list = []
                for node, tdi_dict in zip(node_list, tdi_dict_list):
                    if tdi_dict is None:
                        continue
                    else:
                        tdi_create_list.append(self.third_d_operate.create_schemas(**tdi_dict, node_id=node.id))
                tdi_list = self.third_d_operate.create_sql(db, tdi_create_list)
                for node_base in node_base_list:
                    db.refresh(node_base)
                for node in node_list:
                    db.refresh(node)
                if device_info_list:
                    self.device_info_operate.update_redis_table(device_info_list)
                if tdi_list:
                    self.third_d_operate.update_redis_table(tdi_list)
                self.node_base_operate.update_redis_table(node_base_list)
                self.node_operate.update_redis_table(node_list)

                self.node_operate.reload_redis_table(db, self.node_operate.reload_related_redis_tables, node_list)
                return jsonable_encoder(node_list)

        @router.patch("/{node_id}", response_model=self.main_schemas)
        async def update_api_node(update_data: update_schemas, node_id: int,
                                  db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                update_dict = update_data.dict()
                device_info_list = []
                tdi_list = []
                original_node_data = self.node_operate.read_data_from_redis_by_key_set({node_id})[0]
                self_ref_id_dict = self.node_operate.get_self_ref_id(
                    [self.node_operate.main_schemas(**original_node_data)])
                if not original_node_data["node_base"]["device_info"] and update_dict["node_base"]["device_info"]:
                    # db table "device_info" create data
                    device_info_create = self.device_info_operate.create_schemas(
                        **update_dict["node_base"]["device_info"], node_base_id=original_node_data["node_base"]["id"])
                    device_info_list = self.device_info_operate.create_sql(db, [device_info_create])
                elif original_node_data["node_base"]["device_info"] and update_dict["node_base"]["device_info"]:
                    # db table "device_info" modify data
                    device_info_update = self.device_info_operate.multiple_update_schemas(
                        **update_dict["node_base"]["device_info"],
                        id=original_node_data["node_base"]["device_info"]["id"])
                    device_info_list = self.device_info_operate.update_sql(db, [device_info_update])
                    self.device_info_operate.delete_redis_index_table(
                        [original_node_data["node_base"]["device_info"]], [device_info_update])
                if not original_node_data["third_dimension_instance"] and update_dict["third_dimension_instance"]:
                    # db table "third_dimension_instance" create data
                    tdi_create = self.third_d_operate.create_schemas(
                        **update_dict["third_dimension_instance"], node_id=original_node_data["id"])
                    tdi_list = self.third_d_operate.create_sql(db, [tdi_create])
                elif original_node_data["third_dimension_instance"] and update_dict["third_dimension_instance"]:
                    # db table "third_dimension_instance" modify data
                    tdi_update = self.third_d_operate.multiple_update_schemas(
                        **update_dict["third_dimension_instance"],
                        id=original_node_data["third_dimension_instance"]["id"])
                    tdi_list = self.third_d_operate.update_sql(db, [tdi_update])
                    self.third_d_operate.delete_redis_index_table(
                        [original_node_data["third_dimension_instance"]], [tdi_update])
                node_base_update = self.node_base_operate.multiple_update_schemas(
                    **update_dict["node_base"], id=original_node_data["node_base"]["id"])
                node_base_list = self.node_base_operate.update_sql(db, [node_base_update])
                node_update = self.node_operate.multiple_update_schemas(**update_dict, id=original_node_data["id"])
                node_list = self.node_operate.update_sql(db, [node_update])
                # delete index redis_db table
                self.node_base_operate.delete_redis_index_table([original_node_data["node_base"]], [node_base_update])
                self.node_operate.delete_redis_index_table([original_node_data], [node_update])
                # update redis_db table
                if device_info_list:
                    self.device_info_operate.update_redis_table(device_info_list)
                if tdi_list:
                    self.third_d_operate.update_redis_table(tdi_list)
                self.node_base_operate.update_redis_table(node_base_list)
                self.node_operate.update_redis_table(node_list)
                # reload related redis_db table
                self.node_operate.reload_redis_table(db, self.node_operate.reload_related_redis_tables,
                                                     node_list, self_ref_id_dict)
                return self.format_api_node(jsonable_encoder(node_list[0]))

        @router.patch("/multiple/", response_model=list[self.main_schemas])
        async def update_api_nodes(
                update_list: list[multiple_update_schemas],
                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                update_dict_list = [i.dict() for i in update_list]
                node = create_update_dict(create=False)
                node_base = create_update_dict(create=False)
                device_info = create_update_dict()
                tdi = create_update_dict()
                original_data_list = self.node_operate.read_data_from_redis_by_key_set({i.id for i in update_list})
                original_key_id_dict: dict = {i["id"]: i for i in original_data_list}
                self_ref_id_dict = self.node_operate.get_self_ref_id(
                    [self.node_operate.main_schemas(**i) for i in original_data_list])
                for data in update_dict_list:
                    original_node: dict = original_key_id_dict[data["id"]]
                    original_node_base: dict = original_node["node_base"]
                    original_tdi = original_node["third_dimension_instance"]
                    if not original_node_base["device_info"] and data["node_base"]["device_info"]:
                        device_info["create_list"].append(self.device_info_operate.create_schemas(
                            **data["node_base"]["device_info"], node_base_id=original_node_base["id"]))
                    elif original_node_base["device_info"] and data["node_base"]["device_info"]:
                        device_info["update_list"].append(self.device_info_operate.multiple_update_schemas(
                            **data["node_base"]["device_info"], id=original_node_base["device_info"]["id"]))
                    if not original_tdi and data["third_dimension_instance"]:
                        tdi["create_list"].append(self.third_d_operate.create_schemas(
                            **data["third_dimension_instance"], node_id=data["id"]))
                    elif original_tdi and data["third_dimension_instance"]:
                        tdi["update_list"].append(self.third_d_operate.multiple_update_schemas(
                            **data["third_dimension_instance"], id=original_tdi["id"]))
                    node_base["update_list"].append(self.node_base_operate.multiple_update_schemas(
                        **data["node_base"], id=original_node_base["id"]))
                    node["update_list"].append(self.node_operate.multiple_update_schemas(
                        **data))
                # DB operate
                device_info["sql_list"].extend(self.device_info_operate.create_sql(db, device_info["create_list"]))
                device_info["sql_list"].extend(self.device_info_operate.update_sql(db, device_info["update_list"]))
                tdi["sql_list"].extend(self.third_d_operate.create_sql(db, tdi["create_list"]))
                tdi["sql_list"].extend(self.third_d_operate.update_sql(db, tdi["update_list"]))
                node_base["sql_list"].extend(self.node_base_operate.update_sql(db, node_base["update_list"]))
                node["sql_list"].extend(self.node_operate.update_sql(db, node["update_list"]))
                # redis_db operate
                # redis_db delete index table
                self.device_info_operate.delete_redis_index_table(
                    [i["node_base"]["device_info"] for i in original_data_list if i["node_base"]["device_info"]],
                    device_info["update_list"])
                self.third_d_operate.delete_redis_index_table(
                    [i["third_dimension_instance"] for i in original_data_list if i["third_dimension_instance"]],
                    tdi["update_list"])
                self.node_base_operate.delete_redis_index_table([i["node_base"] for i in original_data_list],
                                                                node_base["update_list"])
                self.node_operate.delete_redis_index_table([i for i in original_data_list], node["update_list"])
                # update redis_db table
                self.device_info_operate.update_redis_table(device_info["sql_list"])
                self.third_d_operate.update_redis_table(tdi["sql_list"])
                self.node_base_operate.update_redis_table(node_base["sql_list"])
                self.node_operate.update_redis_table(node["sql_list"])
                # reload related redis_db table
                self.node_operate.reload_redis_table(db, self.node_operate.reload_related_redis_tables,
                                                     node["sql_list"], self_ref_id_dict)
                return [self.format_api_node(i) for i in jsonable_encoder(node["sql_list"])]

        @router.delete("/{node_id}")
        async def delete_api_node(node_id: int, db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                return self.delete_nodes(db, {node_id})

        @router.delete("/multiple/")
        async def delete_api_nodes(id_set: set[int], db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                return self.delete_nodes(db, id_set)

        return router
