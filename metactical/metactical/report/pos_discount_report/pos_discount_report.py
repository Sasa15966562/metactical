# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.reportview import build_match_conditions
from frappe.utils import flt, cint, getdate, now, date_diff 

def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_column()
	data=[]

	item_sales = get_data(filters)
	for d in item_sales:
		row = {}
		row['si_date'] = d.posting_date
		row['warehouse'] = d.warehouse
		row['si_name'] = d.name
		row['ifw_retailskusuffix'] = d.ifw_retailskusuffix
		row['item_code'] = d.item_code
		row['item_name'] = d.item_name
		row['qty'] = d.qty
		row['rate'] = d.rate
		row['price_list_rate'] = d.price_list_rate
		row['discount_percentage'] = d.discount_percentage
		row['uom'] = d.uom
		row['ifw_location'] = d.ifw_location

		data.append(row)

	return columns, data


def get_column():
	return [
		{
			"fieldname":"warehouse",
			"label": "Pos location",
			"fieldtype": "Data",
			'width': 200
		},
		{
			"fieldname": "si_name",
			"label": "Invoice Number",
			"fieldtype": 'Link',
			'options': 'Sales Invoice',
			'width': 120
		},
		{
			"fieldname":"ifw_retailskusuffix",
			"label": "Retail SkuSuffix",
			"fieldtype": "Data",
			'width': 200
		},
		{
			"fieldname":"item_name",
			"label": "Item Name",
			"fieldtype": "Data",
			'width': 200
		},
		{
			"fieldname":"price_list_rate",
			"label": "PriceList Price",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname":"rate",
			"label": "Discount Price sold for",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname":"discount_percentage",
			"label": "Percentage Amount(%)",
			"fieldtype": "Percent",
			'width': 120
		},
	]


def get_data(filters):
	where_filter = {"from_date": filters.from_date, "to_date": filters.to_date}
	where = ""

	data = frappe.db.sql("""select c.item_code, c.item_name, c.qty, c.price_list_rate, c.rate, c.discount_percentage,
		c.uom, c.ifw_retailskusuffix, c.ifw_location, c.warehouse,
		p.name, p.posting_date
		from `tabSales Invoice Item` c inner join `tabSales Invoice` p on p.name = c.parent
		inner join `tabItem` i on c.item_code = i.name 
		where p.docstatus = 1 and p.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND c.discount_percentage > 15
		order by p.posting_date
		"""+ where, where_filter, as_dict=1)
	return data
