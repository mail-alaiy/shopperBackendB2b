from mongoengine import Document, StringField, FloatField, DateTimeField
from datetime import datetime


class Payment(Document):
    merchantTransactionId = StringField(required=True, unique=True)
    userId = StringField(required=True)
    date_added = DateTimeField(default=datetime.utcnow)
    amount = FloatField(required=True, min_value=0)
    orderId = StringField(required=True)
    status = StringField(required=True, choices=["PENDING", "SUCCESS", "FAILED"])

    meta = {
        "collection": "payments"
    }