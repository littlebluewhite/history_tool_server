import pydantic.error_wrappers
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import sessionmaker, Session

from dependencies.get_query_dependencies import CommonQuery, SimpleQuery
from dependencies.db_dependencies import create_get_db
from function.API.API_control_href_group import APIControlHrefGroupOperate
from function.create_data_structure import create_update_dict, create_delete_dict


class APIControlHrefGroup(APIControlHrefGroupOperate):
    def __init__(self, module, redis_db, exc, db_session: sessionmaker):
        self.db_session = db_session
        self.simple_schemas = module.simple_schemas
        APIControlHrefGroupOperate.__init__(self, module, redis_db, exc)

    def create(self):
        router = APIRouter(
            prefix='/api/control_href_group',
            tags=["API", "Control Href Group"],
            dependencies=[]
        )

        create_schemas = self.create_schemas
        update_schemas = self.update_schemas
        multiple_update_schemas = self.multiple_update_schemas

        @router.get("/", response_model=list[self.main_schemas])
        async def get_control_href_group(common: CommonQuery = Depends(),
                                         db: Session = Depends(create_get_db(self.db_session))):
            if common.pattern == "all":
                chg = self.chg_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            else:
                id_set = self.chg_operate.execute_sql_where_command(db, common.where_command)
                chg = self.chg_operate.read_data_from_redis_by_key_set(id_set)[common.skip:][:common.limit]
            return chg

        @router.get("/simple/", response_model=list[self.simple_schemas])
        async def get_simple_objects(common: SimpleQuery = Depends()):
            chgs = self.chg_operate.read_all_data_from_redis()[common.skip:][:common.limit]
            return [self.format_simple_api_chg(chg) for chg in chgs]

        @router.post("/", response_model=self.main_schemas)
        async def create_api_control_href_group(create_data: create_schemas,
                                                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                create_dict = create_data.dict()
                chg_create = self.chg_operate.create_schemas(**create_dict)
                chg = self.chg_operate.create_sql(db, [chg_create])[0]
                chi_create_list = list()
                for chi in create_dict["control_href_items"]:
                    chi_create_list.append(self.chi_operate.create_schemas(**chi, control_href_group_id=chg.id))
                chi_list = self.chi_operate.create_sql(db, chi_create_list)
                db.refresh(chg)

                # redis_db create data
                self.chg_operate.update_redis_table([chg])
                self.chi_operate.update_redis_table(chi_list)

                return jsonable_encoder(chg)

        @router.post("/multiple/", response_model=list[self.main_schemas])
        async def create_api_control_href_groups(create_data_list: list[create_schemas],
                                                 db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                chg_create_list = list()
                chg_dict_list = []
                chi_create_list = list()
                for create_data in create_data_list:
                    create_dict = create_data.dict()
                    chg_dict_list.append(create_dict)
                    chg_create = self.chg_operate.create_schemas(**create_dict)
                    chg_create_list.append(chg_create)

                chg_list = self.chg_operate.create_sql(db, chg_create_list)
                for i, chg in enumerate(chg_list):
                    for chi in chg_dict_list[i]["control_href_items"]:
                        chi_create_list.append(self.chi_operate.create_schemas(**chi, control_href_group_id=chg.id))
                chi_list = self.chi_operate.create_sql(db, chi_create_list)
                for chg in chg_list:
                    db.refresh(chg)

                # redis_db create data
                self.chg_operate.update_redis_table(chg_list)
                self.chi_operate.update_redis_table(chi_list)

                return jsonable_encoder(chg_list)

        @router.patch("/{chg_id}", response_model=self.main_schemas)
        async def update_api_control_href_group(update_data: update_schemas, chg_id: int,
                                                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                update_dict = update_data.dict()
                chg = create_update_dict(create=False)
                chg_original_list = self.chg_operate.read_data_from_redis_by_key_set({chg_id})
                chi_id_set = set()
                chg["update_list"].append(self.chg_operate.multiple_update_schemas(**update_dict, id=chg_id))
                chi = create_update_dict()
                for i in update_dict["control_href_items"]:
                    if i["id"] is None:
                        chi["create_list"].append(self.chi_operate.create_schemas(**i, control_href_group_id=chg_id))
                    else:
                        chi_id_set.add(i["id"])
                        chi["update_list"].append(self.chi_operate.multiple_update_schemas(**i))
                chi["sql_list"].extend(self.chi_operate.create_sql(db, chi["create_list"]))
                chi["sql_list"].extend(self.chi_operate.update_sql(db, chi["update_list"]))
                chg["sql_list"].extend(self.chg_operate.update_sql(db, chg["update_list"]))
                # redis operate
                # redis delete index table
                chi_original_list = self.chi_operate.read_data_from_redis_by_key_set(chi_id_set)
                self.chi_operate.delete_redis_index_table(chi_original_list, chi["update_list"])
                self.chg_operate.delete_redis_index_table(chg_original_list, chg["update_list"])
                # reload redis table
                self.chg_operate.update_redis_table(chg["sql_list"])
                self.chi_operate.update_redis_table(chi["sql_list"])
                return jsonable_encoder(chg["sql_list"][0])

        @router.patch("/multiple/", response_model=list[self.main_schemas])
        async def update_api_control_href_groups(
                update_list: list[multiple_update_schemas],
                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                chg_original_list = self.chg_operate.read_data_from_redis_by_key_set({i.id for i in update_list})
                chi_id_dict = {item["id"]: item for group in chg_original_list for item in
                               group["control_href_items"]}
                chg = create_update_dict(create=False)
                chi = create_update_dict(delete=True)
                chi_id_set = set()
                for data in update_list:
                    chg["update_list"].append(self.chg_operate.multiple_update_schemas(**data.dict()))
                    for i in data.control_href_items:
                        if i.id is None:
                            try:
                                chi_create_data = self.chi_operate.create_schemas(
                                    **i.dict(), control_href_group_id=data.id)
                                if chi_create_data.tags is None:
                                    chi_create_data.tags = []
                                chi["create_list"].append(chi_create_data)
                            except pydantic.error_wrappers.ValidationError as e:
                                raise self.exc(status_code=422, detail=e)
                        elif i.id < 0:
                            # delete
                            chi["delete_id_set"].add(abs(i.id))
                            _data = chi_id_dict.get(abs(i.id), None)
                            if _data is not None:
                                chi["delete_data_list"].append(_data)
                            else:
                                raise self.exc(status_code=433, detail=f"can't find control_href_item id: {-i.id}")
                        else:
                            chi_id_set.add(i.id)
                            chi["update_list"].append(self.chi_operate.multiple_update_schemas(**i.dict()))
                chi["sql_list"].extend(self.chi_operate.create_sql(db, chi["create_list"]))
                chi["sql_list"].extend(self.chi_operate.update_sql(db, chi["update_list"]))
                self.chi_operate.delete_sql(db, chi["delete_id_set"], False)
                chg["sql_list"].extend(self.chg_operate.update_sql(db, chg["update_list"]))
                # redis delete index table
                chi_original_list = self.chi_operate.read_data_from_redis_by_key_set(chi_id_set)
                self.chi_operate.delete_redis_index_table(chi_original_list, chi["update_list"])
                self.chg_operate.delete_redis_index_table(chg_original_list, chg["update_list"])
                # reload redis table
                self.chg_operate.update_redis_table(chg["sql_list"])
                self.chi_operate.update_redis_table(chi["sql_list"])
                # delete redis table
                self.chi_operate.delete_redis_table(chi["delete_data_list"])
                return jsonable_encoder(chg["sql_list"])

        @router.delete("/{chg_id}")
        async def delete_api_control_href_group(chg_id: int, db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                chg_original_list = self.chg_operate.read_data_from_redis_by_key_set({chg_id})
                chg = create_delete_dict()
                chi = create_delete_dict()
                for g in chg_original_list:
                    chg["data_list"].append(g)
                    chg["id_set"].add(g["id"])
                    for i in g["control_href_items"]:
                        chi["id_set"].add(i["id"])
                        chi["data_list"].append(i)
                # delete sql
                self.chi_operate.delete_sql(db, chi["id_set"], False)
                self.chg_operate.delete_sql(db, chg["id_set"], False)
                # delete redis table
                self.chg_operate.delete_redis_table(chg["data_list"])
                self.chi_operate.delete_redis_table(chi["data_list"])
                return "ok"

        @router.delete("/multiple/")
        async def delete_api_control_href_group(
                id_set: set[int],
                db: Session = Depends(create_get_db(self.db_session))):
            with db.begin():
                chg_original_list = self.chg_operate.read_data_from_redis_by_key_set(id_set)
                chg = create_delete_dict()
                chi = create_delete_dict()
                for g in chg_original_list:
                    chg["data_list"].append(g)
                    chg["id_set"].add(g["id"])
                    for i in g["control_href_items"]:
                        chi["id_set"].add(i["id"])
                        chi["data_list"].append(i)
                # delete sql
                self.chi_operate.delete_sql(db, chi["id_set"], False)
                self.chg_operate.delete_sql(db, chg["id_set"], False)
                # delete redis table
                self.chg_operate.delete_redis_table(chg["data_list"])
                self.chi_operate.delete_redis_table(chi["data_list"])
                return "ok"

        return router
