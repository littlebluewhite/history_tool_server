from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class SQLDB:
    def __init__(self, db_config):
        self.host = db_config["host"]
        self.port = db_config["port"]
        self.db = db_config["db"]
        self.user = db_config["user"]
        self.password = db_config["password"]
        self.url = f"mysql+pymysql://{self.user}:{self.password}" \
                   f"@{self.host}:{self.port}/{self.db}"
        # self.url = "postgresql://postgres:123456@localhost:5432/dispatch"
        self.engine = create_engine(self.url, echo=True)

    def get_engine(self):
        return self.engine

    def new_db_session(self):
        return sessionmaker(autocommit=False, autoflush=False, bind=self.engine)


Base = declarative_base()

if __name__ == "__main__":
    pass
