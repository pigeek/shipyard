from sqladmin import ModelView

from app.features.notifications.models import EmailLog


class EmailLogAdmin(ModelView, model=EmailLog):
    name = "Email log"
    name_plural = "Email logs"
    icon = "fa-solid fa-envelope"
    can_create = False
    can_edit = False
    column_list = [
        EmailLog.id,
        EmailLog.recipient,
        EmailLog.subject,
        EmailLog.template,
        EmailLog.status,
        EmailLog.created_at,
    ]
    column_searchable_list = [EmailLog.recipient, EmailLog.subject]
    column_sortable_list = [EmailLog.created_at, EmailLog.status]
