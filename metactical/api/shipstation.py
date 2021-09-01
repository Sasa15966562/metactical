import frappe
from lxml import etree
from werkzeug.wrappers import Response
import requests
from requests.auth import HTTPBasicAuth
import json
from urllib.parse import urlparse, parse_qs

def get_orders(start_date, end_date):
	orders = frappe.get_all('Sales Order', fields=['name', 'transaction_date', 'status', 'modified', 'currency', 'grand_total', 'customer', 
									'customer_address', 'shipping_address_name'], 
									filters={"delivery_status": ("in", ("Not Delivered", "Partly Delivered")), "billing_status": "Fully Billed", 
									"modified": ("between", (start_date, end_date))})
	return orders

@frappe.whitelist(allow_guest=True)
def test():
	'''response = requests.get('https://ssapi.shipstation.com/stores',
				auth=('249b9201157349939742f12101a8cc80', '1d7b6409ba6e41e1aeae73b97384613d'))'''
	data = {"resource_url": "https://ssapi6.shipstation.com/shipments?batchId=190671332&includeShipmentItems=False", "resource_type": "SHIP_NOTIFY" }
	response = requests.post('http://deverp.metactical.com/api/method/metactical.api.shipstation.orders_shipped_webhook?settingid=8f3a7e2cac',
				json=data)				
	print(response)
	print(response.json())
	#return frappe.db.get_value('Delivery Note', {"pick_list": 'STO-PICK-2021-00032', 'docstatus': 0})
	'''orders = frappe.get_all('Delivery Note', {'posting_date': '2021-08-27'})
	for order in orders:
		create_shipstation_orders(order.name)'''


@frappe.whitelist(allow_guest=True)
def connect():
	response = requests.get('https://ssapi.shipstation.com/orders',
				auth=('42edf2c7a56e4289b0cb184dc040eb4b', 'f124798829b144f7a14752e67a1a7ec4'))	
	print(response)
	print(response.json())
	
@frappe.whitelist()
def create_shipstation_orders(order_no=None, is_cancelled=False):
	#order_no = 'MAT-DN-2021-00039'
	if order_no is not None:
		order = frappe.get_doc('Delivery Note', order_no)
		if order.get('is_return') == 1:
			return
		source = None
		if order.get('source') is not None:
			source = order.get('source')
		settings = get_settings(source)
	
		data = order_json(order, is_cancelled, settings)
		response = requests.post('https://ssapi.shipstation.com/orders/createorder',
					auth=(settings.api_key, settings.get_password('api_secret')),
					json=data)
		#print(response.status_code)
		#print(response.json())
		if response.status_code == 200:
			sorder = response.json()
			frappe.db.set_value('Delivery Note', order_no, "ais_shipstation_orderid", sorder.get('orderId'))
		
	
	

def order_json(order, is_cancelled, settings):
	#order = frappe.get_doc('Delivery Note', order_no)
	
	#Order no is either pick list name or delivery note name
	order_no = None
	if order.pick_list and order.pick_list is not None:
		order_no = order.pick_list
	else:
		order_no = order.name
		
	orderStatus = "awaiting_shipment"
	if is_cancelled:
		orderStatus = "cancelled"
	
	#For shipping and taxes charges
	shipping_settings = settings.shipping_charges_specified
	shipping_item = None
	shipping_charges = 0
	taxes = 0
	if shipping_settings == 'In Item Table':
		shipping_item = settings.shipping_item
		taxes = order.total_taxes_and_charges
	elif shipping_settings == 'In Charges Table':
		shipping_item = settings.shipping_charge
		for charge in order.taxes:
			if charge.account_head == shipping_item:
				shipping_charges = charge.tax_amount_after_discount_amount
			else:
				taxes = taxes + float(charge.tax_amount_after_discount_amount)
	
	#For address
	'''customer_address = {
		'address_line1': None,
		'address_line2': None,
		'city': None,
		'state': None,
		'pincode': None,
		'phone': None,
		'email_id': None
	}'''
	customer_address = {}
	customer_country = None
	if order.customer_address and order.customer_address is not None:
		customer_address = frappe.get_doc('Address', order.customer_address)
		customer_country = frappe.get_value('Country', customer_address.country, "code")
		customer_country = customer_country.upper()
	
	#Get shipping address, if none, use customer address
	shipping_address = {}
	shipping_country = None
	if order.shipping_address_name and order.shipping_address_name is not None:
		shipping_address = frappe.get_doc('Address', order.shipping_address_name)
		shipping_country = frappe.get_value('Country', shipping_address.country, "code")
		shipping_country = shipping_country.upper()
	elif order.customer_address and order.customer_address is not None:
		shipping_address = customer_address
		shipping_country = frappe.get_value('Country', shipping_address.country, "code")
		shipping_country = shipping_country.upper()
		
	#For stores
	storeId = None
	if order.source and order.source is not None:
		for store in settings.store_mapping:
			if order.source == store.source:
				storeId = store.store_id
		
	items = []
	for item in order.items:
		#Check if it is a shipping item
		if shipping_settings == 'In Item Table' and item.item_code == shipping_item:
			shipping_charges = item.amount
		else:
			row = {}
			row.update({
				"lineItemKey": item.name,
				"sku": item.item_code,
				"name": item.item_name,
				"imageUrl": None,
				"weight": None,
				"quantity": int(item.qty),
				"unitPrice": float(item.rate),
				"taxAmount": None,
				"shippingAmount": None,
				"warehouseLocation": None,
				"options": None,
				"productId": None,
				"fulfillmentSku": None,
				"adjustment": False,
				"upc": None
			})
			items.append(row)
	data = {}
	data.update({
		"orderNumber": order_no,
		"orderKey": order_no,
		"orderDate": str(order.posting_date),
		"paymentDate": None,
		"shipByDate": "",
		"orderStatus": orderStatus,
		"customerUsername": order.customer,
		"customerEmail": customer_address.get('email_id'),
		"billTo": {
			"name": order.customer,
			"company": '',
			"street1": customer_address.get('address_line1'),
			"street2": customer_address.get('address_line2'),
			"street3": '',
			"city": customer_address.get('city'),
			"state": customer_address.get('state'),
			"postalCode": customer_address.get('pincode'),
			"country": customer_country,
			"phone": customer_address.get('phone'),
			"residential": None
		},
		"shipTo": {
			"name": order.customer,
			"company": "",
			"street1": shipping_address.get('address_line1'),
			"street2": shipping_address.get('address_line2'),
			"street3": '',
			"city": shipping_address.get('city'),
			"state": shipping_address.get('state'),
			"postalCode": shipping_address.get('pincode'),
			"country": shipping_country,
			"phone": shipping_address.get('phone'),
			"residential": None
		},
		"items": items,
		"amountPaid": order.grand_total,
		"taxAmount": float(taxes),
		"shippingAmount": float(shipping_charges),
		"customerNotes": None,
		"internalNotes": None,
		"gift": False,
		"giftMessage": None,
		"paymentMethod": None,
		"requestedShippingService": None,
		"carrierCode": None,
		"serviceCode": None,
		"packageCode": None,
		"confirmation": "none",
		"shipDate": None,
		"weight": None,
		"dimensions": None,
		"advancedOptions": {
			"storeId": storeId
		}
	})
	return data

def get_settings(source=None, settingid=None):
	settings = None
	if source is not None:
		parent = frappe.db.sql('''SELECT parent FROM `tabShipstation Store Map` WHERE source = %(source)s''', {"source": source}, as_dict=1)
		if len(parent) > 0:
			settings = frappe.get_doc('Shipstation Settings', parent[0].parent)
			
	if settingid is not None:
		settings = frappe.get_doc('Shipstation Settings', settingid)
		
	if settings is None:
		default = frappe.db.get_value('Shipstation Settings', {"is_default": 1})
		settings = frappe.get_doc('Shipstation Settings', default)
	return settings
	
@frappe.whitelist(allow_guest=True)
def orders_shipped_webhook():
	url = urlparse(frappe.request.url)
	params = parse_qs(url.query)
	settingid = params.get("settingid")
	data = json.loads(frappe.request.data)
	resource_url = data.get("resource_url")
	resource_type = data.get("resource_type")
	#resource_url = 'https://ssapi6.shipstation.com/shipments?batchId=191142513&includeShipmentItems=False'
	#resource_type = "SHIP_NOTIFY"
	#settingid = []
	#settingid.append("a9faca509c")
	if settingid is not None:
		frappe.set_user('Administrator')
		#Log the request
		new_req = frappe.get_doc({
			"doctype": "Shipstation API Requests",
			"start_date": resource_url,
			"end_date": resource_type,
			"settingid": settingid[0]
		})
		if resource_type == 'SHIP_NOTIFY':
			settings = get_settings(settingid=settingid[0])
			response = requests.get(resource_url,
						auth=('249b9201157349939742f12101a8cc80', '1d7b6409ba6e41e1aeae73b97384613d'))
			new_req.update({
				"result": json.dumps(response.json())
			})
			shipments = response.json()
			weight_display = ''
			size = ''
			for shipment in shipments.get('shipments'):
				weight = shipment.get('weight')
				if weight_display != '':
					weight_display =+ ' | '
				weight_display += str(weight.get('value')) + ' ' + weight.get('units')
				dimensions = shipment.get('dimensions')
				if size != '':
					size += ' | '
				size += str(dimensions.get('length')) + 'l x ' + str(dimensions.get('width')) + 'w x ' + str(dimensions.get('height')) + 'h'
				#For carrier mapping
				transporter = ''
				for row in settings.transporter_mapping:
					if row.carrier_code == shipment.get('carrierCode'):
						transporter = row.transporter
				pick_list = shipment.get('orderNumber')
				shipDate = shipment.get('shipDate')
				trackingNumber = shipment.get('trackingNumber')
				shipmentCost = shipment.get('shipmentCost')
				existing_delivery = frappe.db.get_value('Delivery Note', {'pick_list': pick_list})
				if existing_delivery:
					delivery_note = frappe.get_doc('Delivery Note', existing_delivery)
					delivery_note.update({
						'lr_date': shipDate,
						'lr_no': trackingNumber,
						'transporter': transporter,
						'ais_shipment_cost': shipmentCost,
						'ais_package_weight': weight_display,
						'ais_package_size': size,
						'ais_updated_by_shipstation': 1
					})
					delivery_note.submit()
		new_req.insert(ignore_if_duplicate=True)
	
	
@frappe.whitelist(allow_guest=True)
def shipstation_xml():
	root = etree.Element("Orders")
	out = etree.tostring(root, pretty_print=True)
	response = Response()
	response.mimetype = "text/xml"
	response.charset = "utf-8"
	response.data = out
	return response
	
@frappe.whitelist()
def get_shipment():
	response = requests.get('https://ssapi6.shipstation.com/shipments?batchId=187980859&includeShipmentItems=False',
				auth=('249b9201157349939742f12101a8cc80', '1d7b6409ba6e41e1aeae73b97384613d'))
	print(response.status_code)
	print(response.json())
	shipments = response.json()
	for shipment in shipments.get('shipments'):
		existing_delivery = frappe.db.get_value('Delivery Note', {'po_no': shipment.get('orderNumber'), 'docstatus': 0})
		if existing_delivery:
			delivery_note = frappe.get_doc('Delivery Note', existing_delivery)
			delivery_note.update({
				'lr_date': shipment.get('shipDate'),
				'lr_no': shipment.get('trackingNumber')
			})
			delivery_note.save()
			
def delete_order(order_no):
	#order_no = 'MAT-DN-2021-00030'
	settings = get_settings()
	orderId = frappe.db.get_value('Delivery Note', order_no, 'ais_shipstation_orderid')
	if orderId is not None:
		response = requests.delete('https://ssapi.shipstation.com/orders/' + orderId,
				auth=(settings.api_key, settings.get_password('api_secret')))
	print(response.status_code)
	print(response.json())
