frappe.listview_settings['Purchase Invoice'] = {
	onload: function(listview) {
		listview.page.add_actions_menu_item(__('Delete'), function() {
			const selected_items = listview.get_checked_items();
			if (selected_items.length === 0) {
				frappe.msgprint(__('Please select at least one Purchase Invoice.'));
				return;
			}

			const names = selected_items.map(item => item.name);

			frappe.confirm(
				__('Are you sure you want to delete the selected Draft Purchase Invoices? Submitted ones will be skipped.'),
				function() {
					frappe.call({
						method: 'songa_mobility_customizations.services.rest.bulk_delete_purchase_invoices',
						args: {
							names: names
						},
						callback: function(r) {
							if (r.message) {
								const { deleted, skipped } = r.message;
								let msg = '';
								if (deleted.length > 0) {
									msg += __('{0} Draft Purchase Invoices deleted successfully.', [deleted.length]) + '<br>';
								}
								if (skipped.length > 0) {
									msg += __('{0} Purchase Invoices were skipped as they are not in Draft status or had errors.', [skipped.length]);
									frappe.msgprint({
										title: __('Deletion Results'),
										indicator: 'orange',
										message: msg
									});
								} else if (deleted.length > 0) {
									frappe.show_alert({
										message: msg,
										indicator: 'green'
									});
								}
								listview.refresh();
							}
						}
					});
				}
			);
		});
	}
};
