from django.db import DatabaseError


class DatabaseErrorWithMessages(DatabaseError):
    def __init__(self, messages=None):
        super().__init__()
        self.messages = messages if messages is not None else []
