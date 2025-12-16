# models.py
from mongoengine import Document, StringField, EmailField, IntField, DateTimeField, EmbeddedDocument, ListField, ObjectIdField, EmbeddedDocumentField, FloatField
from datetime import datetime

class OrderDetails(EmbeddedDocument):
    sku = StringField(required=True, max_length=15)
    sellerSku = StringField(required=False, default=None)
    quantity = IntField(min_value=1, required=True)
    quantityShipped = IntField(min_value=1, required=False, default=1)
    consumerPrice = FloatField(min_value=0, required=False, default=0)
    igst = FloatField(min_value=0, required=False, default = 0)
    cgst = FloatField(min_value=0, required=False, default = 0)
    sgst = FloatField(min_value=0, required=False, default = 0)
    consumerPrice_before_taxes = FloatField(min_value=0, required=False, default = 0)
    title = StringField(required=True, max_length = 500)
    source = StringField(required=True, max_length=100)
    
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
    shippingPhoneNumber = StringField(required=True, max_length=13)
    shippingAddress1 = StringField(required=True, max_length=70)
    shippingAddress2 = StringField(required=False, max_length=70, default=None)
    shippingAddress3 = StringField(required=False, max_length=70, default=None)
    pStatus = StringField(required=True, max_length=5)
    oStatus = StringField(required=False, max_length = 5, default="OB")
    sStatus = StringField(required = False, max_length=5, default="SU")
    dStatus = StringField(required = False, max_length=5, default="DN")
    rStatus = StringField(required = False, max_length=5, default="RN")
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
    total_amount = IntField(required=True)
    createdAt = DateTimeField(default=datetime.utcnow)
    updatedAt = DateTimeField(required=False, default=None)
    
    
    
#Paid date
#merchantID
#mkpOrderId
