"""The daily sales summary. Days are shop days in Sri Lanka time, whatever the server's zone."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, OrderItem, OrderStatus, Refund, Staff
from app.permissions import Permission, require
from app.pricing import ZERO, money
from app.schemas import DailyReportOut, DaySales, TopProduct
from app.services.purchasing import low_stock_query

SHOP_TIME_ZONE = "Asia/Colombo"
# Orders that brought in money. A later refund shows up on the day it was made.
SOLD = (
    OrderStatus.PAID,
    OrderStatus.PACKING,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
    OrderStatus.REFUNDED,
    OrderStatus.CANCELLED,
)


def shop_day(column):
    """The Sri Lanka calendar day of a timestamp, worked out by the database."""
    return func.date(func.timezone(SHOP_TIME_ZONE, column))


def today(db: Session) -> date:
    return db.scalar(select(shop_day(func.now())))


def daily_report(db: Session, actor: Staff, day: date | None = None) -> DailyReportOut:
    require(actor, Permission.VIEW_REPORTS, "Your role cannot view reports.")
    day = day or today(db)
    paid_on = shop_day(Order.paid_at)
    sold = Order.paid_at.is_not(None) & Order.status.in_(SOLD)

    orders, revenue = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
            sold, paid_on == day
        )
    ).one()
    top = db.execute(
        select(
            OrderItem.product_id,
            func.max(OrderItem.product_name),
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.line_total),
        )
        .join(Order)
        .where(sold, paid_on == day)
        .group_by(OrderItem.product_id)
        .order_by(func.sum(OrderItem.quantity).desc(), func.max(OrderItem.product_name))
    ).all()
    refunds = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(shop_day(Refund.created_at) == day)
    )

    first = day - timedelta(days=13)
    by_day = {
        row_day: (count, total)
        for row_day, count, total in db.execute(
            select(paid_on, func.count(Order.id), func.sum(Order.total))
            .where(sold, paid_on >= first, paid_on <= day)
            .group_by(paid_on)
        )
    }
    series = [
        DaySales(
            day=d,
            orders=by_day.get(d, (0, ZERO))[0],
            revenue=money(Decimal(by_day.get(d, (0, ZERO))[1])),
        )
        for d in (first + timedelta(days=n) for n in range(14))
    ]

    revenue = money(Decimal(revenue))
    return DailyReportOut(
        day=day,
        orders=orders,
        revenue=revenue,
        items_sold=sum(int(quantity) for _, _, quantity, _ in top),
        average_order=money(revenue / orders) if orders else ZERO,
        refunds=money(Decimal(refunds)),
        top_products=[
            TopProduct(product_id=pid, name=name, quantity=int(qty), revenue=money(total))
            for pid, name, qty, total in top[:10]
        ],
        waiting_to_ship=db.scalar(
            select(func.count(Order.id)).where(
                Order.status.in_((OrderStatus.PAID, OrderStatus.PACKING))
            )
        )
        or 0,
        needs_attention=db.scalar(
            select(func.count(Order.id)).where(Order.needs_attention.is_not(None))
        )
        or 0,
        low_stock=db.scalar(select(func.count()).select_from(low_stock_query().subquery())) or 0,
        last_14_days=series,
        currency=get_settings().currency,
    )
