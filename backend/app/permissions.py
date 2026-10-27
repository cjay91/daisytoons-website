"""Who may do what. Checked in services, so the API, console and agents all get the same rules."""

import enum

from app.errors import Forbidden
from app.models import Staff, StaffRole


class Permission(enum.StrEnum):
    MANAGE_STAFF = "manage_staff"
    MANAGE_PRODUCTS = "manage_products"  # create products, change details and prices
    MANAGE_STOCK = "manage_stock"  # on hand, reorder point, bin location
    VIEW_CATALOG = "view_catalog"
    VIEW_ORDERS = "view_orders"
    FULFIL_ORDERS = "fulfil_orders"  # packing, shipping, marking delivered
    SUPPORT_ORDERS = "support_orders"  # resend emails, clear an order's attention flag
    REFUND_ORDERS = "refund_orders"  # cancel a paid order, record refunds
    MANAGE_PURCHASING = "manage_purchasing"  # suppliers and purchase orders
    VIEW_REPORTS = "view_reports"


ROLE_PERMISSIONS: dict[StaffRole, frozenset[Permission]] = {
    StaffRole.ADMIN: frozenset(Permission),
    StaffRole.PACKER: frozenset(
        {
            Permission.MANAGE_STOCK,
            Permission.VIEW_CATALOG,
            Permission.VIEW_ORDERS,
            Permission.FULFIL_ORDERS,
        }
    ),
    StaffRole.SUPPORT: frozenset(
        {Permission.VIEW_CATALOG, Permission.VIEW_ORDERS, Permission.SUPPORT_ORDERS}
    ),
}


def has_permission(staff: Staff, permission: Permission) -> bool:
    return staff.is_active and permission in ROLE_PERMISSIONS[staff.role]


def require(staff: Staff, permission: Permission, message: str) -> None:
    if not has_permission(staff, permission):
        raise Forbidden(message)
