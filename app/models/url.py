from datetime import UTC, datetime

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    TextField,
)

from app.database import BaseModel
from app.models.user import User


class Url(BaseModel):
    id = AutoField()
    user_id = ForeignKeyField(User.id, backref="urls", null=True)
    short_code = CharField(max_length=12, unique=True, index=True)
    original_url = TextField(unique=True)
    title = CharField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))
