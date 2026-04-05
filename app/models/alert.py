from datetime import datetime

from peewee import AutoField, CharField, DateTimeField, TextField

from app.database import BaseModel


class Alert(BaseModel):
    id = AutoField()
    alert_name = CharField()
    severity = CharField(default="warning")
    status = CharField(default="firing")
    summary = TextField(default="")
    source = CharField(default="")
    notes = TextField(default="")
    fired_at = DateTimeField(default=datetime.utcnow)
    acknowledged_at = DateTimeField(null=True)
    resolved_at = DateTimeField(null=True)
    acknowledged_by = CharField(null=True)
