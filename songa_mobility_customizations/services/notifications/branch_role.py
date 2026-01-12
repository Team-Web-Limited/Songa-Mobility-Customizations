import frappe


def notify_users_by_branch_and_role(
    *,
    branch: str,
    role: str,
    title: str,
    message: str,
    reference_doctype: str = None,
    reference_name: str = None,
    send_email: bool = False
):
    if not branch or not role:
        return

    # Users allowed for the branch
    permitted_users = frappe.get_all(
        "User Permission",
        filters={
            "allow": "Branch",
            "for_value": branch
        },
        pluck="user"
    )

    if not permitted_users:
        return

    # Users with the role
    users = frappe.get_all(
        "Has Role",
        filters={
            "role": role,
            "parent": ["in", permitted_users]
        },
        pluck="parent"
    )

    for user in users:
        # Desk notification
        frappe.publish_realtime(
            event="notification",
            message={
                "title": title,
                "message": message,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
            },
            user=user
        )

        if send_email:
            email = frappe.get_value("User", user, "email")
            if email:
                frappe.sendmail(
                    recipients=email,
                    subject=title,
                    message=message,
                    reference_doctype=reference_doctype,
                    reference_name=reference_name
                )


def get_users_by_branch_and_role(branch, role):
    print(f"\n\n\n\n\n branch {branch} : {role} \n\n\n\n\n")
    """
    Return a list of emails of users with a given role and branch
    """
    users = frappe.get_all(
        "User Permission",
        filters={"allow": "Branch", "for_value": branch},
        fields=["user"]
    )

    print(f"\n\n\n\n\n users {users} \n\n\n\n\n")

    eligible_users = []
    for u in users:
        has_role = frappe.db.exists("Has Role", {"parent": u.user, "role": role})
        if has_role:
            eligible_users.append(u.user)

    return eligible_users