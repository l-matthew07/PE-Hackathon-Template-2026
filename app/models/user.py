from datetime import UTC, datetime

from peewee import AutoField, CharField, DateTimeField

from app.database import BaseModel


class User(BaseModel):
    id = AutoField()
    username = CharField(unique=True)
    email = CharField()
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
