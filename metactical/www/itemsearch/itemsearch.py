import frappe


def get_context(context):
	context.no_cache = True
	search_text = frappe.request.args["searchtext"]
	items = get_items(search_text)
	if "columns" in items and "data" in items:
		context.columns = items["columns"]
		context.data = items["data"]


def get_items(search_value=""):
	data = dict()
	result = []

	query = """
		SELECT
		it1.item_code,
		it1.item_name,
		it1.stock_uom,
		it1.is_stock_item,
		it1.ifw_retailskusuffix,
		it1.ifw_location,
		it1.variant_of,
		GROUP_CONCAT(DISTINCT it1.barcode SEPARATOR '<br>') AS barcode,
		ip.price_list_rate,
		ip.currency,
		GROUP_CONCAT(DISTINCT it1.sqoh SEPARATOR '<br>') AS sqoh
		FROM 
		(
			SELECT
			it.item_code,
			it.item_name,
			it.stock_uom,
			it.is_stock_item,
			it.ifw_retailskusuffix,
			it.ifw_location,
			it.variant_of,
			ib.barcode,
			it.disabled,
			it.has_variants,
			it.is_sales_item,
			tis.ifw_supplier_qoh AS sqoh
			FROM
				`tabItem` it
			LEFT JOIN
				`tabItem Barcode` ib
				ON ib.parent = it.name
			LEFT JOIN
				`tabItem Supplier` tis ON tis.parent = it.item_code 
			where ib.barcode = "{search_text}" or it.ifw_retailskusuffix like "{search_text}%"
		) it1
		LEFT JOIN
			`tabItem Price` ip
			on ip.item_code = it1.item_code and ip.price_list = "RET - Camo"
		WHERE
			it1.disabled = 0
			AND it1.has_variants = 0
			AND it1.is_sales_item = 1
		GROUP BY
			item_code, item_name, stock_uom, is_stock_item, ifw_retailskusuffix, it1.ifw_location, it1.variant_of,
			ip.price_list_rate, ip.currency
		ORDER BY
			it1.ifw_retailskusuffix asc""".format(
			search_text=search_value
		)
	items_data = frappe.db.sql(query ,as_dict=1)

	if items_data:
		table_columns = ["RetailSKU", "Item Name", "Price", "SQOH"]
		table_data = []
		items = [d.item_code for d in items_data]

		bin_data = {}

		# prepare filter for bin query
		bin_filters = {"item_code": ["in", items]}

		# query item bin
		bin_data = frappe.get_all(
			"Bin",
			fields=["item_code", "warehouse", "sum(actual_qty) as actual_qty", "SUM(reserved_qty) AS reserved_qty"],
			filters=bin_filters,
			group_by="item_code, warehouse",
		)

		# Get Warehouses and its display name from Item Search Settings
		item_search_settings = frappe.get_doc("Item Search Settings")
		if not item_search_settings:
			frappe.msgpring("Please Enter Item Search Settings")
		
		warehouses = item_search_settings.warehouses
		warehouses_to_display = {}
		warehouse_wise_items = {}

		for warehouse in warehouses:
			warehouses_to_display[warehouse.warehouse] = warehouse.display_name
			warehouse_wise_items[warehouse.warehouse] = {}

		# convert list of dict into dict as {item_code: actual_qty}
		bin_dict = {}
		for b in bin_data:
			warehouse = b.get("warehouse")
			item_code = b.get("item_code")
			qty = b.get("actual_qty") - b.get("reserved_qty")
			if warehouse not in warehouses_to_display:
				continue
			warehouse_wise_items[warehouse][item_code] = qty
			bin_dict[b.get("item_code")] = b.get("actual_qty")

		warehouses = warehouse_wise_items.keys()
		print(warehouses_to_display)
		for warehouse in warehouses:
			if warehouse not in warehouses_to_display:
				continue
			frappe.msgprint(warehouses_to_display[warehouse])
			table_columns.append(warehouses_to_display[warehouse])

		table_columns.extend(["Barcode", "IFW_location", "ERPItemCode", "ERPNextTemplateSKU"])

		for item in items_data:
			item_row = []
			item_code = item.item_code
			item_name = item.item_name
			item_price = item.price_list_rate
			retail_skusuffix = item.ifw_retailskusuffix
			ifw_location = item.ifw_location
			variant_of = item.variant_of
			barcode = item.barcode
			sqoh = item.sqoh

			item_row.extend([retail_skusuffix, item_name, item_price, sqoh])
			for warehouse in warehouses:
				warehouse_qty = 0.0
				if item_code in warehouse_wise_items[warehouse]:
					warehouse_qty = warehouse_wise_items[warehouse][item_code]
				item_row.append(warehouse_qty)

			item_row.extend([barcode, ifw_location, item_code, variant_of])
			table_data.append(item_row)

		res = {"data": table_data, "columns": table_columns}
		return res
	else:
		return {}


def search_barcode(search_value):
	# search barcode no
	barcode_data = frappe.db.get_value(
		"Item Barcode",
		{"barcode": search_value},
		["barcode", "parent as item_code"],
		as_dict=True,
	)
	if barcode_data:
		return barcode_data

	return {}


def get_conditions(item_code, barcode):
	if barcode:
		return "name = {0}".format(frappe.db.escape(item_code))

	return "ifw_retailskusuffix like {0}".format(
		frappe.db.escape("%" + item_code + "%")
	)
