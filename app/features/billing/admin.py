from sqladmin import ModelView

from app.features.billing.models import Invoice, Plan, Subscription, WebhookEvent


class PlanAdmin(ModelView, model=Plan):
    name = "Plan"
    name_plural = "Plans"
    icon = "fa-solid fa-tags"
    column_list = [Plan.name, Plan.amount, Plan.currency, Plan.interval, Plan.is_active]
    column_searchable_list = [Plan.name, Plan.stripe_price_id]


class SubscriptionAdmin(ModelView, model=Subscription):
    name = "Subscription"
    name_plural = "Subscriptions"
    icon = "fa-solid fa-repeat"
    can_create = False
    column_list = [
        Subscription.id,
        Subscription.user_id,
        Subscription.status,
        Subscription.current_period_end,
        Subscription.cancel_at_period_end,
    ]


class InvoiceAdmin(ModelView, model=Invoice):
    name = "Invoice"
    name_plural = "Invoices"
    icon = "fa-solid fa-file-invoice-dollar"
    can_create = False
    can_edit = False
    column_list = [
        Invoice.stripe_invoice_id,
        Invoice.user_id,
        Invoice.amount_paid,
        Invoice.currency,
        Invoice.status,
    ]


class WebhookEventAdmin(ModelView, model=WebhookEvent):
    name = "Webhook event"
    name_plural = "Webhook events"
    icon = "fa-solid fa-bolt"
    can_create = False
    can_edit = False
    column_list = [
        WebhookEvent.stripe_event_id,
        WebhookEvent.type,
        WebhookEvent.processed,
        WebhookEvent.created_at,
    ]
    column_searchable_list = [WebhookEvent.stripe_event_id, WebhookEvent.type]
