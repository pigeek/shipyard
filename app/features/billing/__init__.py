from app.core.registry import FeatureModule
from app.features.billing.admin import (
    InvoiceAdmin,
    PlanAdmin,
    SubscriptionAdmin,
    WebhookEventAdmin,
)
from app.features.billing.api import router as api_router
from app.features.billing.tasks import send_invoice_receipt
from app.features.billing.views import router as ssr_router

feature = FeatureModule(
    name="billing",
    api_router=api_router,
    ssr_router=ssr_router,
    admin_views=[PlanAdmin, SubscriptionAdmin, InvoiceAdmin, WebhookEventAdmin],
    tasks=[send_invoice_receipt],
)
