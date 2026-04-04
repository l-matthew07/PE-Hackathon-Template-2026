from peewee import AutoField, CharField, DateTimeField, ForeignKeyField, IntegerField, TextField

from app.database import BaseModel
from app.models.user import User


class Event(BaseModel):
    id = AutoField()
    # url_id is intentionally not a foreign key so event logs survive URL deletes.
    url_id = IntegerField()
    user = ForeignKeyField(User, backref="events")
    event_type = CharField()
    timestamp = DateTimeField()
    details = TextField(null=True)
