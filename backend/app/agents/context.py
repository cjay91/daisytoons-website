"""Who an agent is acting for, and so what it may see and do."""

from dataclasses import dataclass

from app.models import ActorKind, Customer, Staff
from app.permissions import Permission, has_permission


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    staff: Staff | None = None
    customer: Customer | None = None
    # A guest's cart, on the storefront. Logged-in customers' carts are found by customer.
    cart_token: str | None = None

    @classmethod
    def for_staff(cls, staff: Staff) -> "Actor":
        return cls(ActorKind.STAFF, staff=staff)

    @classmethod
    def for_customer(
        cls, customer: Customer | None = None, cart_token: str | None = None
    ) -> "Actor":
        """A customer, or a guest on the storefront when `customer` is None."""
        return cls(ActorKind.CUSTOMER, customer=customer, cart_token=cart_token)

    @property
    def staff_id(self) -> int | None:
        return self.staff.id if self.staff else None

    @property
    def customer_id(self) -> int | None:
        return self.customer.id if self.customer else None

    def allows(self, permission: Permission | None) -> bool:
        """Customers have no staff permissions; staff have their role's."""
        if permission is None:
            return True
        return self.staff is not None and has_permission(self.staff, permission)
