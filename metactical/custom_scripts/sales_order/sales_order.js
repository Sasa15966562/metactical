{% include 'erpnext/selling/sales_common.js' %}
var old_tax_template;
var base_in_words;
frappe.ui.form.on('Sales Order', {
	refresh: function(frm){
		console.log(frm);
		//Clear update qty and rate button
		/*if(frm.doc.docstatus === 1 && frm.doc.status !== 'Closed'
			&& flt(frm.doc.per_delivered, 6) < 100 && flt(frm.doc.per_billed, 6) < 100) {
			frm.clear_custom_buttons();
		}*/
		
		
		setTimeout(() => {
			
			frm.remove_custom_button("Pick List", 'Create'); 
			frm.add_custom_button(__('Pick List'), () => frm.events.create_pick_list_custom(), __("Create"));
			frm.remove_custom_button("Work Order", 'Create');
			frm.remove_custom_button("Request for Raw Materials", 'Create'); 
			frm.remove_custom_button("Project", 'Create'); 
			frm.remove_custom_button("Subscription", 'Create'); 
			
		}, 1000);

		// Add Stock Entry (Transfer material) button
		if(frm.doc.docstatus == 1){ 
			frm.add_custom_button(__('Stock Entry'), 
				() => frm.events.create_material_transfer_custom(), __("Create"));
		}
		
		//Code for custom cancel button that saves cancel reason first
		if(frm.doc.docstatus == 1){
			frm.page.clear_secondary_action();
			frm.page.set_secondary_action(__("Cancel"), function(frm) {
				cur_frm.events.before_cancel_event();
			});
		}

		// set taxes and charges after amending
		if (frm.doc.amended_from && !frm.doc.taxes_and_charges) {
			var amended_order = frappe.get_doc("Sales Order", frm.doc.amended_from);
			frm.doc.taxes_and_charges = amended_order.taxes_and_charges ;
		}

		dashboard_sales_order_doctype(frm, "Stock Entry");
		
		//For changing to drop ship
		if(frm.doc.docstatus == 1 && (frm.doc.delivery_status == "Not Delivered" || frm.doc.delivery_status == "Partly Delivered")){
			frm.add_custom_button(__('To Drop Ship'), () => frm.events.change_to_drop_ship(frm), __('Change'));
			frm.add_custom_button(__('Warehouse'), () => frm.events.change_warehouse(frm), __('Change'));
		}
	},

	onload: function(frm){
		old_tax_template = frm.doc.taxes_and_charges;
		base_in_words = frm.doc.base_in_words;
	},
	
	change_to_drop_ship: function(frm){
		var fields = [
			{
				"fieldtype": "Data",
				"fieldname": "docname",
				"read_only": 1,
				"hidden": 1,
				"in_list_view": 0
			},
			{
				"fieldtype": "Link",
				"options": "Item",
				"fieldname": "item_code",
				"read_only": 1,
				"columns": 2,
				"label": __("Item Code"),
				"in_list_view": 1
			},
			{
				"fieldtype": "Data",
				"fieldname": "item_name",
				"read_only": 1,
				"columns": 3,
				"label": __("Item Name"),
				"in_list_view": 1
			},
			{
				"fieldtype": "Check",
				"fieldname": "delivered_by_supplier",
				"read_only": 0,
				"columns": 1,
				"label": __("Delivered By Supplier"),
				"in_list_view": 1
			},
			{
				"fieldtype": "Link",
				"options": "Supplier",
				"fieldname": "supplier",
				"read_only": 0,
				"columns": 3,
				"label": __("Supplier"),
				"in_list_view": 1
			}
		];
		var data = [];
		frm.doc.items.forEach(function(row){
			if(row.delivered_by_supplier != 1 && row.delivered_qty == 0){
				data.push({
					"docname": row.name,
					"item_code": row.item_code,
					"item_name": row.item_name
				})
			}
		});
		var dialog = new frappe.ui.Dialog({
			title: __("Update Drop Ship"),
			fields: [
				{
					fieldname: "drop_ship_items",
					fieldtype: "Table",
					label: "Items",
					cannot_add_rows: true,
					in_place_edit: true,
					reqd: 1,
					data: data,
					get_data: () => {
						return data;
					},
					fields: fields
				}
			],
			primary_action: function() {
				const drop_ship_items = this.get_values()["drop_ship_items"];
				frappe.call({
					method: 'metactical.custom_scripts.sales_order.sales_order.update_drop_shipping',
					freeze: true,
					args: {
						'items': drop_ship_items
					},
					callback: function() {
						frm.reload_doc();
					}
				});
				this.hide();
				refresh_field("items");
			},
			primary_action_label: __('Update')
		});
		
		
		
		dialog.show();
	},
	
	create_pick_list_custom(frm) {
		// confirm item availability
		var items = cur_frm.doc.items
		var flag = 0;
		var item_flag = ""
		items.forEach(function(row){
			if (row.ais_is_stock_item == 1 && (row.actual_qty - (row.qty + row.sal_reserved_qty)) < 0) {
				flag = 1;
				item_flag = row.item_code;
			}
		});
		if (flag != 1) {
			frappe.model.open_mapped_doc({
				method: "metactical.custom_scripts.pick_list.pick_list.create_pick_list",
				frm: cur_frm
			})
		}
		else{
			frappe.confirm(
				'Warning: Insufficient stock for Item ' + item_flag + '. Do you want to proceed anyway?',
				function(){
					frappe.model.open_mapped_doc({
						method: "metactical.custom_scripts.pick_list.pick_list.create_pick_list",
						frm: cur_frm
					})
				},
				function(){
					window.close();
				}
			)
		}
	},

	create_material_transfer_custom() {
		frappe.model.open_mapped_doc({
			method: "metactical.custom_scripts.stock_entry.stock_entry.create_stock_entry",
			frm: cur_frm
		})
	},
	
	before_cancel_event: function(frm){
		frappe.prompt([
			{'fieldname': 'cancel_reason', 'fieldtype': 'Small Text', 'label': 'Enter Reason', 'reqd': 1}
		],
		function(values){
			frappe.call({
				'method': 'metactical.custom_scripts.sales_order.sales_order.save_cancel_reason',
				'args': {
					'docname': cur_frm.docname,
					'cancel_reason': values.cancel_reason
				},
				'callback': function(r){
					cur_frm.savecancel();
				}
			});
		},
		'Please reason for cancellation.',
		'Cancel'
		)
	},
	
	change_warehouse: function(frm){
		var fields = [
			{
				"fieldtype": "Data",
				"fieldname": "docname",
				"read_only": 1,
				"hidden": 1,
				"in_list_view": 0
			},
			{
				"fieldtype": "Link",
				"options": "Item",
				"fieldname": "item_code",
				"read_only": 1,
				"columns": 2,
				"label": __("Item Code"),
				"in_list_view": 1
			},
			{
				"fieldtype": "Data",
				"fieldname": "item_name",
				"read_only": 1,
				"columns": 2,
				"label": __("Item Name"),
				"in_list_view": 1
			},
			{
				"fieldtype": "Link",
				"options": "Warehouse",
				"fieldname": "warehouse",
				"read_only": 0,
				"columns": 3,
				"label": __("Warehouse"),
				"in_list_view": 1
			}
		];
		var data = [];
		frm.doc.items.forEach(function(row){
			data.push({
				"docname": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"warehouse": row.warehouse
			});
		});
		var dialog = new frappe.ui.Dialog({
			title: __("Change Warehouse"),
			fields: [
				{
					fieldname: "items",
					fieldtype: "Table",
					label: "Items",
					cannot_add_rows: true,
					in_place_edit: true,
					reqd: 1,
					data: data,
					get_data: () => {
						return data;
					},
					fields: fields
				}
			],
			primary_action: function() {
				const items = this.get_values()["items"];
				frappe.call({
					method: 'metactical.custom_scripts.sales_order.sales_order.change_warehouse',
					freeze: true,
					args: {
						'items': items
					},
					callback: function() {
						frm.reload_doc();
					}
				});
				this.hide();
				refresh_field("items");
			},
			primary_action_label: __('Update')
		});
		dialog.show();
	}
});
frappe.ui.form.on("Sales Order Item", {
	item_code: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn];
		if (row.item_code && row.warehouse) {
			return frm.call({
					method: "metactical.custom_scripts.sales_order.sales_order.get_bin_details",
					child: row,
					args: {
						item_code: row.item_code,
						warehouse: row.warehouse,
					},
					callback:function(r){
						row.sal_reserved_qty =  r.message['reserved_qty'];
						row.ais_is_stock_item = r.message["is_stock_item"]
						refresh_field("sal_reserved_qty", cdn, "items");
						refresh_field("ais_is_stock_item", cdn, "items");
					}
				});
		}
	},
	
	delivered_by_supplier: function(frm, cdt, cdn){
		if(frm.doc.docstatus == 1){
			var row = locals[cdt][cdn];
			return frm.call({
					method: "metactical.custom_scripts.sales_order.sales_order.get_bin_details",
					args:{
						"item_code": row.item,
						"sales_order": row.sales_order
					},
					callback: function(result){
						console.log(result)
					}
				});
		}
	}
});

erpnext.selling.SalesOrderController = erpnext.selling.SalesOrderController.extend({
	customer_address: function(doc, dt, dn){
		if(doc.docstatus == 1){
			erpnext.utils.get_address_display(this.frm, "customer_address");		
		}
		else{
			erpnext.utils.get_address_display(this.frm, "customer_address");
			erpnext.utils.set_taxes_from_address(this.frm, "customer_address", "customer_address", "shipping_address_name");
		}
	},
	warehouse: function(doc, cdt, cdn){
		var row = locals[cdt][cdn];
		if (row.item_code && row.warehouse) {
			return this.frm.call({
					method: "metactical.custom_scripts.sales_order.sales_order.get_bin_details",
					child: row,
					args: {
						item_code: row.item_code,
						warehouse: row.warehouse,
					},
					callback:function(r){
						console.log(r);
						row.sal_reserved_qty =  r.message['reserved_qty'];
						row.ais_is_stock_item = r.message["is_stock_item"]
						refresh_field("sal_reserved_qty", cdn, "items");
						refresh_field("ais_is_stock_item", cdn, "items");
					}
				});
		}
	},

});

$.extend(cur_frm.cscript, new erpnext.selling.SalesOrderController({frm: cur_frm}));


//Add Stock Entry in dashboard
var dashboard_sales_order_doctype = function (frm, doctype) {
		frappe.call({
				'method': 'metactical.custom_scripts.sales_order.sales_order.get_open_count',
				'args': {
					'docname': cur_frm.docname,
				},
				'callback': function(r){
					var items = [];
					$.each((r.message), function(i, d){
						items.push(d.name);		
					})
					load_template_links(frm, doctype, items);
				}
		});
}

var load_template_links = function(frm, doctype, items){
	var sales_orders = ['in'];
	var count_links = 0;
	items.forEach(function(item){
		console.log("in loop");		
		if( sales_orders.indexOf(item) == -1){
			count_links++;
			sales_orders.push(item);
		}
	});

	var parent = $('.form-dashboard-wrapper [data-doctype="Purchase Order"]').closest('div').parent();
	parent.find('[data-doctype="' + doctype + '"]').remove();
	parent.append(frappe.render_template("dashboard_sales_order_doctype", {
		doctype: doctype
	}));

	var self = parent.find('[data-doctype="' + doctype + '"]');
	

	// bind links
	self.find(".badge-link").on('click', function () {
		frappe.route_options = {
			"sales_order_no": frm.doc.name
		}
		frappe.set_route("List", doctype);
	});

	self.find('.count').html(count_links);
}

frappe.templates["dashboard_sales_order_doctype"] = ' \
    	<div class="document-link" data-doctype="{{ doctype }}"> \
    	<a class="badge-link small">{{ __(doctype) }}</a> \
    	<span class="text-muted small count"></span> \
    	<span class="open-notification hidden" title="{{ __("Open {0}", [__(doctype)])}}"></span> \
    	</div>';
