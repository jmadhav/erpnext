# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import webnotes
import webnotes.utils
from webnotes.utils import cstr
from webnotes import _

class DocType():
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def test_send(self, doctype="Lead"):
		self.recipients = self.doc.test_email_id.split(",")
		self.send_to_doctype = "Lead"
		self.send_bulk()
		webnotes.msgprint("""Scheduled to send to %s""" % self.doc.test_email_id)

	def send_emails(self):
		"""send emails to leads and customers"""
		if self.doc.email_sent:
			webnotes.msgprint("""Newsletter has already been sent""", raise_exception=1)

		self.recipients = self.get_recipients()
		self.send_bulk()
		
		webnotes.msgprint("""Scheduled to send to %d %s(s)""" % (len(self.recipients), 
			self.send_to_doctype))

		webnotes.conn.set(self.doc, "email_sent", 1)
	
	def get_recipients(self):
		if self.doc.send_to_type=="Contact":
			self.send_to_doctype = "Contact"
			if self.doc.contact_type == "Customer":		
				return webnotes.conn.sql_list("""select email_id from tabContact 
					where ifnull(email_id, '') != '' and ifnull(customer, '') != ''""")

			elif self.doc.contact_type == "Supplier":		
				return webnotes.conn.sql_list("""select email_id from tabContact 
					where ifnull(email_id, '') != '' and ifnull(supplier, '') != ''""")
	
		elif self.doc.send_to_type=="Lead":
			self.send_to_doctype = "Lead"
			conditions = []
			if self.doc.lead_source and self.doc.lead_source != "All":
				conditions.append(" and source='%s'" % self.doc.lead_source)
			if self.doc.lead_status and self.doc.lead_status != "All":
				conditions.append(" and status='%s'" % self.doc.lead_status)

			if conditions:
				conditions = "".join(conditions)
				
			return webnotes.conn.sql_list("""select email_id from tabLead 
				where ifnull(email_id, '') != '' %s""" % (conditions or ""))

		elif self.doc.email_list:
			email_list = [cstr(email).strip() for email in self.doc.email_list.split(",")]
			for email in email_list:
				create_lead(email)
					
			self.send_to_doctype = "Lead"
			return email_list
	
	def send_bulk(self):
		self.validate_send()

		sender = self.doc.send_from or webnotes.utils.get_formatted_email(self.doc.owner)
		
		from webnotes.utils.email_lib.bulk import send
		webnotes.conn.auto_commit_on_many_writes = True
		
		send(recipients = self.recipients, sender = sender, 
			subject = self.doc.subject, message = self.doc.message,
			doctype = self.send_to_doctype, email_field = "email_id")

		webnotes.conn.auto_commit_on_many_writes = False

	def validate_send(self):
		if self.doc.fields.get("__islocal"):
			webnotes.msgprint(_("""Please save the Newsletter before sending."""),
				raise_exception=1)

		import conf
		if getattr(conf, "status", None) == "Trial":
			webnotes.msgprint(_("""Sending newsletters is not allowed for Trial users, \
				to prevent abuse of this feature."""), raise_exception=1)

@webnotes.whitelist()
def get_lead_options():
	return {
		"sources": ["All"] + webnotes.conn.sql_list("""select distinct source from tabLead"""),
		"statuses": ["All"]+ webnotes.conn.sql_list("""select distinct status from tabLead""")
	}


lead_naming_series = None
def create_lead(email_id):
	"""create a lead if it does not exist"""
	from email.utils import parseaddr
	real_name, email_id = parseaddr(email_id)
	
	if webnotes.conn.get_value("Lead", {"email_id": email_id}):
		return
	
	lead = webnotes.bean({
		"doctype": "Lead",
		"email_id": email_id,
		"lead_name": real_name or email_id,
		"status": "Contacted",
		"naming_series": lead_naming_series or get_lead_naming_series(),
		"company": webnotes.conn.get_default("company"),
		"source": "Email"
	})
	lead.insert()
	
def get_lead_naming_series():
	"""gets lead's default naming series"""
	global lead_naming_series
	naming_series_field = webnotes.get_doctype("Lead").get_field("naming_series")
	if naming_series_field.default:
		lead_naming_series = naming_series_field.default
	else:
		latest_naming_series = webnotes.conn.sql("""select naming_series
			from `tabLead` order by creation desc limit 1""")
		if latest_naming_series:
			lead_naming_series = latest_naming_series[0][0]
		else:
			lead_naming_series = filter(None, naming_series_field.options.split("\n"))[0]
	
	return lead_naming_series
