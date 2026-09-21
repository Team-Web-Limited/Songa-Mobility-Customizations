frappe.listview_settings['Purchase Invoice'] = {
	onload: function(listview) {
		if (frappe.model.can_create('Payment Entry')) {
			listview.page.add_action_item(__('Bulk Payment'), function() {
				show_bulk_payment_dialog(listview);
			});
		}

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

function show_bulk_payment_dialog(listview) {
	const selected_items = listview.get_checked_items();
	if (!selected_items.length) {
		frappe.msgprint(__('Please select at least one Purchase Invoice.'));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __('Bulk Payment'),
		fields: [
			{
				fieldname: 'posting_date',
				label: __('Posting Date'),
				fieldtype: 'Date',
				default: frappe.datetime.nowdate(),
				reqd: 1
			},
			{
				fieldname: 'paid_from',
				label: __('Bank/Cash Account'),
				fieldtype: 'Link',
				options: 'Account',
				description: __('The account the payment will be made from.'),
				reqd: 1,
				get_query: function() {
					return {
						filters: {
							is_group: 0,
							account_type: ['in', ['Bank', 'Cash']]
						}
					};
				}
			},
			{
				fieldname: 'mode_of_payment',
				label: __('Mode of Payment'),
				fieldtype: 'Link',
				options: 'Mode of Payment',
				reqd: 1
			},
			{
				fieldname: 'reference_no',
				label: __('Reference Number'),
				fieldtype: 'Data',
				description: __('Optional bank transaction or batch reference.')
			},
			{
				fieldname: 'reference_date',
				label: __('Reference Date'),
				fieldtype: 'Date'
			},
			{
				fieldname: 'submit_entries',
				label: __('Submit Payment Entries'),
				fieldtype: 'Check',
				default: 0,
				description: __('Leave unchecked to create Payment Entries as drafts.')
			},
			{
				fieldname: 'group_by_supplier',
				label: __('Group by Supplier'),
				fieldtype: 'Check',
				default: 1,
				description: __('Create one Payment Entry for each compatible supplier group.')
			}
		],
		primary_action_label: __('Create Payments'),
		primary_action: function(values) {
			dialog.disable_primary_action();
			frappe.call({
				method: 'songa_mobility_customizations.services.rest.bulk_pay_purchase_invoices',
				args: {
					names: selected_items.map(item => item.name),
					payment_details: values
				},
				freeze: true,
				freeze_message: __('Creating Payment Entries...'),
				callback: function(r) {
					dialog.hide();
					show_bulk_payment_result(r.message || {});
					listview.refresh();
				},
				error: function() {
					dialog.enable_primary_action();
				}
			});
		}
	});

	dialog.show();
}

function show_bulk_payment_result(result) {
	const created = result.created || [];
	const skipped = result.skipped || [];
	const failed = result.failed || [];
	let message = __('Created: {0}', [created.length]);

	if (skipped.length) {
		message += '<br>' + __('Skipped: {0}', [skipped.length]);
	}
	if (failed.length) {
		message += '<br>' + __('Failed: {0}', [failed.length]);
	}

	const details = skipped.concat(failed).map(item => {
		const invoice = frappe.utils.escape_html(item.invoice || '');
		const reason = frappe.utils.escape_html(item.reason || '');
		return `<li>${invoice}: ${reason}</li>`;
	}).join('');

	frappe.msgprint({
		title: __('Bulk Payment Results'),
		indicator: failed.length ? 'orange' : 'green',
		message: message + (details ? `<br><br><ul>${details}</ul>` : '')
	});
}
