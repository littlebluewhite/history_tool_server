def create_get_db(db_session):
    def get_db():
        db = db_session()
        try:
            yield db
        finally:
            db.close()
    return get_db
