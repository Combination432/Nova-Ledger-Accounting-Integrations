from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryItemViewSet, InventoryLocationViewSet,
    InventoryTransactionViewSet, PurchaseOrderViewSet
)

router = DefaultRouter()
router.register(r'items', InventoryItemViewSet, basename='inventoryitem')
router.register(r'locations', InventoryLocationViewSet, basename='inventorylocation')
router.register(r'transactions', InventoryTransactionViewSet, basename='inventorytransaction')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchaseorder')

urlpatterns = [
    path('', include(router.urls)),
]
