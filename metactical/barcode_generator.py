# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import shutil
import barcode
from pathlib import Path
import pyqrcode
from frappe.utils import cstr
from io import BytesIO


def generate(self, method):
	site = cstr(frappe.local.site)
	code = self.name
	name_tobe = code+".svg"
	check_file = Path(site+"/public/files/"+name_tobe)
	if not check_file.is_file():
		bar = barcode.get('code128', str(code))
		result = bar.save(code)
		shutil.move(result, site+'/public/files')

def po_validate(self, method):
	self.customer_address=None
	for d in self.items:
		if d.sales_order:
			self.customer_address = frappe.db.get_value("Sales Order", d.sales_order, "address_display")
			break

@frappe.whitelist()
def get_barcode(name):
	rv = BytesIO()
	barcode.get('code128', name).write(rv, options={"write_text": False})
	bstring = rv.getvalue()
	return bstring.decode('ISO-8859-1')
