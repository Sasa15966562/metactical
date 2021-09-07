from __future__ import unicode_literals
import frappe
import json
from six import iteritems
from frappe.model.document import Document
from frappe import _
from frappe.model.mapper import get_mapped_doc, map_child_doc
from frappe.utils import cstr, flt, getdate, cint, nowdate, add_days, get_link_to_form, strip_html
from erpnext.stock.doctype.pick_list.pick_list import PickList
import barcode as _barcode
from io import BytesIO
from erpnext.stock.doctype.pick_list.pick_list import validate_item_locations, set_delivery_note_missing_values, update_delivery_note_item
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as create_delivery_note_from_sales_order
import datetime
from pytz import timezone

def custom_before_save(self):
	rv = BytesIO()
	_barcode.get('code128', self.locations[0].sales_order).write(rv)
	bstring = rv.getvalue()
	self.barcode = bstring.decode('ISO-8859-1')
	
	# STO Barcode
	sv = BytesIO()
	_barcode.get('code128', self.name).write(sv)
	stoBarcode = sv.getvalue()
	self.sal_sto_barcode = stoBarcode.decode('ISO-8859-1')


	#Check if Sales Order has Balance Due or Credit Due
	sales_orders = []
	for item in self.locations:
		if item.sales_order and item.sales_order not in sales_orders:
			sales_orders.append(item.sales_order)
			doc = frappe.get_doc("Sales Order", item.sales_order)
			c_or_d = doc.grand_total - doc.advance_paid
			if c_or_d > 0:
				frappe.msgprint('Warning: Sales Order <a href="/desk#Form/Sales Order/{0}">{0}</a> has not been fully paid'.format(item.sales_order))
			elif c_or_d < 0:
				frappe.msgprint('Warning: Sales Order <a href="/desk#Form/Sales Order/{0}">{0}</a> has credit due.'.format(item.sales_order))
			
	
def custom_on_save(self, method):
	PickList.before_save = custom_before_save


def on_submit(self, method):
	pick_list = frappe.get_doc('Pick List', self.name)
	validate_item_locations(pick_list)

	sales_orders = [d.sales_order for d in pick_list.locations if d.sales_order]
	sales_orders = set(sales_orders)

	delivery_note = None
	for sales_order in sales_orders:
		delivery_note = create_delivery_note_from_sales_order(sales_order,
			delivery_note, skip_item_mapping=True)
		#Add pick list submitted date in sales order
		sales_doc = frappe.get_doc("Sales Order", sales_order)
		sales_doc.update({"pick_list_submitted_date": datetime.datetime.now(timezone('US/Pacific')).strftime("%Y-%m-%d %H:%M:%S")})
		sales_doc.save()

	# map rows without sales orders as well
	if not delivery_note:
		delivery_note = frappe.new_doc("Delivery Note")

	item_table_mapper = {
		'doctype': 'Delivery Note Item',
		'field_map': {
			'rate': 'rate',
			'name': 'so_detail',
			'parent': 'against_sales_order',
		},
		'condition': lambda doc: abs(doc.delivered_qty) < abs(doc.qty) and doc.delivered_by_supplier!=1
	}

	item_table_mapper_without_so = {
		'doctype': 'Delivery Note Item',
		'field_map': {
			'rate': 'rate',
			'name': 'name',
			'parent': '',
		}
	}

	for location in pick_list.locations:
		if location.sales_order_item:
			sales_order_item = frappe.get_cached_doc('Sales Order Item', {'name':location.sales_order_item})
		else:
			sales_order_item = None

		source_doc, table_mapper = [sales_order_item, item_table_mapper] if sales_order_item \
			else [location, item_table_mapper_without_so]

		dn_item = map_child_doc(source_doc, delivery_note, table_mapper)

		if dn_item:
			dn_item.warehouse = location.warehouse
			dn_item.qty = location.picked_qty
			dn_item.batch_no = location.batch_no
			dn_item.serial_no = location.serial_no

			update_delivery_note_item(source_doc, dn_item, delivery_note)

	set_delivery_note_missing_values(delivery_note)

	delivery_note.pick_list = pick_list.name
	delivery_note.customer = pick_list.customer if pick_list.customer else None
	delivery_note.save()
	
	
def on_cancel(self, method):
	delivery_notes = frappe.get_all('Delivery Note', filters={'pick_list': self.name, 'docstatus': 0}, fields=['name'])
	for delivery_note in delivery_notes:
		doc = frappe.get_doc('Delivery Note', delivery_note.name)
		doc.delete()
		
	#Clear pick list submitted date in sales order
	pick_list = frappe.get_doc('Pick List', self.name)

	sales_orders = [d.sales_order for d in pick_list.locations if d.sales_order]
	sales_orders = set(sales_orders)
	for sales_order in sales_orders:
		sales_doc = frappe.get_doc("Sales Order", sales_order)
		sales_doc.update({"pick_list_submitted_date": ""})
		sales_doc.save()

	
@frappe.whitelist()
def before_save_on_create():
	PickList.before_save = custom_before_save
	
@frappe.whitelist()
def create_pick_list(source_name, target_doc=None):
	def update_item_quantity(source, target, source_parent):
		target.qty = flt(source.qty) - flt(source.delivered_qty)
		target.stock_qty = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.conversion_factor)
		target.picked_qty = flt(source.qty) - flt(source.delivered_qty)

	doc = get_mapped_doc('Sales Order', source_name, {
		'Sales Order': {
			'doctype': 'Pick List',
			'validation': {
				'docstatus': ['=', 1]
			},
			'field_map': {
				'sales_order': 'name'
			}
		},
		'Sales Order Item': {
			'doctype': 'Pick List Item',
			'field_map': {
				'parent': 'sales_order',
				'name': 'sales_order_item',
				'warehouse': 'warehouse'
			},
			'postprocess': update_item_quantity,
			'condition': lambda doc: abs(doc.delivered_qty) < abs(doc.qty) and doc.delivered_by_supplier!=1
		},
	}, target_doc)

	doc.purpose = 'Delivery'
	PickList.before_save = custom_before_save

	#doc.set_item_locations()

	return doc
	
@frappe.whitelist()
def save_cancel_reason(**args):
	args = frappe._dict(args)
	doc = frappe.get_doc("Pick List", args.docname)
	doc.db_set("cancel_reason", args.cancel_reason, notify=True)
	doc.db_set("pick_list_cancel_date", datetime.datetime.now(timezone('US/Pacific')).strftime("%Y-%m-%d %H:%M:%S"))
	return 'Success'
