# Copyright (c) 2023, Techlift Technologies and contributors
# For license information, please see license.txt

from locale import currency
import frappe
import requests


def execute(filters=None):
	columns, data = [], []
	columns = get_columns()
	data = get_data()
	return columns, data
	
def get_data():
	data = []
	default_rate = filters.get("default_currency")
	exchange_rate = requests.get("https://api.frankfurter.app/latest?amount=1&from=USD&to=CAD")
	#return exchange_rate.json()
	if exchange_rate.json():
		exchange_rate = exchange_rate.json().get("rates").get("CAD")
		data = frappe.db.sql("""
							with cte
								as
								(
									select itm.name sku, max(itm.item_name) item_name,
									max(itm.last_purchase_rate) last_purchase_rate_default_currency,
									max(itm.valuation_rate) valuation_rate,
									-- Evalumating the supplier price according to the price list currency
									max(case when prc.currency != %(default_currency)s then prc.price_list_rate * %(conversion_rate)s else prc.price_list_rate end) supplier_price_evaluated
									from `tabItem` itm
									join `tabItem Price` prc on itm.name = prc.item_code and buying = 1
									group by itm.name
								)
								-- Fetching from the CTE joining the bin table
								select cte.sku, cte.item_name, sum(bin.actual_qty) qty_all_warehoues,
								-- Using the evaluated supplier price if there is no purchase transaction
								max(case when last_purchase_rate_default_currency = 0 then supplier_price_evaluated else last_purchase_rate_default_currency end) purchase_rate_or_supplier_price,
								%(default_currency)s Currency

								from cte
								join `tabBin` bin on cte.sku = bin.item_code
								where bin.actual_qty > 0
								group by sku
							""", {'conversion_rate': exchange_rate}, {'default_currency': default_rate}, as_dict=1)
								
	return data
	
def get_columns():
	columns = [
		{
			"fieldname": "sku",
			"fieldtype": "Data",
			"label": "SKU",
			"width": "150"
		},
		{
			"fieldname": "item_name",
			"fieldtype": "Data",
			"label": "Item Name",
			"width": "150"
		},
		{
			"fieldname": "qty_all_warehouse",
			"fieldtype": "Int",
			"label": "All Warehouse Qty",
			"width": "150"
		},
		{
			"fieldname": "purchase_rate_or_supplier_price",
			"fieldtype": "Currency",
			"label": "Purchase Rate/ Supplier Price",
			"width": "200"
		}
	]
	return columns
