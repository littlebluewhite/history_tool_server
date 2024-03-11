class HistoryException(Exception):
    def __init__(self, detail, status_code):
        self.status_code = status_code
        self.detail = detail
