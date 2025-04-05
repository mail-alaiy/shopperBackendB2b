# models.py
from mongoengine import Document, StringField, EmailField, IntField, DateTimeField, EmbeddedDocument, ListField, ObjectIdField, EmbeddedDocumentField
from datetime import datetime

class OrderDetails(EmbeddedDocument):
    sku = StringField(required=True, max_length=15)
    sellerSku = StringField(required=False, default=None)
    quantity = IntField(min_value=1, required=True)
    quantityShipped = IntField(min_value=1, required=False, default=1)
    consumerPrice = IntField(min_value=0, required=False, default=0)
    title = StringField(required=True, max_length = 500)
    
class OrderShipping(EmbeddedDocument):
    sm_title = StringField(required=True, max_length = 50)
    os_tracking_no = StringField(required=True, max_length = 20)
    os_date_deliver = DateTimeField(required=False, default=None)
    os_date_add = DateTimeField(required=False, default=None)
    os_status = StringField(required=True, max_length = 5)
    os_apply_status = StringField(required=True, max_length = 5)
    os_apply_modi_date = DateTimeField(required=False, default=None)
    carrier_name = StringField(required=True, max_length = 50)
    shipping_method = StringField(required=True, max_length = 100)
    sku = StringField(required=True, max_length = 30)
    
class Order(Document):
    currency = StringField(required=True, max_length=10)
    shippingPhoneNumber = StringField(required=True, unique=True, max_length=13)
    shippingAddress1 = StringField(required=True, max_length=70)
    shippingAddress2 = StringField(required=True, max_length=70)
    shippingAddress3 = StringField(required=True, max_length=70)
    pStatus = StringField(required=True, max_length=5)
    paidDate = DateTimeField(required=False, default=None)
    shipDate = DateTimeField(required=False, default=None)
    shippingMethod = StringField(required=False, default=None, max_length=30)
    source = IntField(required=True)
    merchantId = StringField(required=True, max_length=50)
    mkpOrderId = StringField(required=True, max_length=30)
    orderDetails = ListField(EmbeddedDocumentField(OrderDetails))
    recipientName = StringField(required=True, max_length=20)
    shippingCity = StringField(required=True, max_length=20)
    shippingState = StringField(required=True, max_length=20)
    shippingPostalCode = StringField(required=True, max_length=20)
    shippingCountry = StringField(required=True, max_length=20)
    order_shipping = ListField(EmbeddedDocumentField(OrderShipping), required=False)
    createdAt = DateTimeField(default=datetime.utcnow)
    updatedAt = DateTimeField(required=False, default=None)
    
    
    
