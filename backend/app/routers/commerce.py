from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, status
import uuid

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import update, delete

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.commerce import Cart, CartItem, UserAddress, OrderGroup, Order, OrderItem
from app.models.catalog import Product
from app.models.delivery import PricingModel
from app.models.shop import Shop
from app.schemas.commerce import (
    CartRead,
    CartItemRead,
    CartItemCreate,
    CheckoutCreate,
    OrderGroupRead,
    OrderRead,
    OrderStatusUpdate,
    DeliveryFeePreviewRequest,
    DeliveryFeePreviewResponse,
)
from app.services.notifications import create_notification
from app.services.delivery_pricing import (
    calculate_delivery_fee_from_cart_total,
    get_or_create_rate_settings,
    parse_weight_kg,
    point_from_location,
    quote_delivery_fee,
)

cart_router = APIRouter(prefix="/cart", tags=["cart"])
checkout_router = APIRouter(prefix="/checkout", tags=["checkout"])
orders_router = APIRouter(prefix="/orders", tags=["orders"])


def _shops_by_id(db: Session, shop_ids) -> dict[uuid.UUID, Shop]:
    """Shops keyed by id, with wards eager-loaded.

    The ward is what lets cost-based pricing resolve a leg below county level,
    and loading it here keeps that from firing a query per seller in the cart.
    """
    ids = list(shop_ids)
    if not ids:
        return {}
    shops = (
        db.query(Shop)
        .options(selectinload(Shop.ward))
        .filter(Shop.id.in_(ids))
        .all()
    )
    return {s.id: s for s in shops}

# cart
@cart_router.get(
    "/",
    response_model=CartRead,
    status_code=status.HTTP_200_OK,
    summary="Get my cart",
)
def get_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart is empty")

    return cart


@cart_router.post(
    "/items",
    response_model=CartItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product to cart",
)
def add_product_to_cart(
    payload: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # get or create the user's cart
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        db.flush()  # generates cart.id before we use it below

    # check if this product+variant combination is already in the cart
    cart_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == payload.product_id,
        CartItem.variant_id == payload.variant_id,
    ).first()

    if cart_item:
        # increment quantity by however many the client is adding
        db.execute(
            update(CartItem)
            .where(CartItem.id == cart_item.id)
            .values(quantity=CartItem.quantity + payload.quantity)
        )
        db.commit()
        db.refresh(cart_item)
        return cart_item

    new_item = CartItem(
        cart_id=cart.id,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return new_item


@cart_router.patch(
    "/items/{item_id}",
    response_model=CartItemRead,
    summary="Update quantity of a cart item",
)
def update_cart_item(
    item_id: uuid.UUID,
    quantity: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if quantity < 1:
        raise HTTPException(status_code=422, detail="Quantity must be at least 1")

    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart_item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.execute(
        update(CartItem)
        .where(CartItem.id == item_id)
        .values(quantity=quantity)
    )
    db.commit()
    db.refresh(cart_item)

    return cart_item


@cart_router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an item from cart",
)
def remove_cart_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart_item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.execute(delete(CartItem).where(CartItem.id == item_id))
    db.commit()


@cart_router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear the entire cart",
)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    db.commit()
    
    
# checkout

@checkout_router.post(
    "/delivery-fee-preview",
    response_model=DeliveryFeePreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview delivery fee for a cart + address, before placing the order",
)
def preview_delivery_fee(
    payload: DeliveryFeePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    address = db.query(UserAddress).filter(
        UserAddress.id == payload.address_id,
        UserAddress.user_id == current_user.id,
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    cart_total = Decimal("0.00")
    cart_weight_kg = Decimal("0")
    products_by_shop: dict[uuid.UUID, list] = {}
    if payload.items:
        product_ids = [item.product_id for item in payload.items]
        products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
        for item in payload.items:
            product = products.get(item.product_id)
            if product:
                cart_total += Decimal(product.price) * item.quantity
                cart_weight_kg += parse_weight_kg(product.weight_kg) * item.quantity
                products_by_shop.setdefault(product.shop_id, []).append(product)

    settings = get_or_create_rate_settings(db)
    db.commit()

    if settings.pricing_model == PricingModel.cost_based.value:
        shops = _shops_by_id(db, products_by_shop.keys())
        quote = quote_delivery_fee(
            point_from_location(address),
            {shop_id: point_from_location(shops.get(shop_id)) for shop_id in products_by_shop},
            cart_weight_kg,
            settings,
        )
        return DeliveryFeePreviewResponse(
            total_delivery_fee=str(quote.total),
            pricing_model=settings.pricing_model,
            band=quote.charged_band.value,
            band_label=quote.band_label,
            band_fee=str(quote.band_fee),
            weight_surcharge=str(quote.weight_surcharge),
            billable_weight_kg=str(quote.billable_weight_kg),
        )

    fee = calculate_delivery_fee_from_cart_total(cart_total)
    return DeliveryFeePreviewResponse(
        total_delivery_fee=str(fee),
        pricing_model=settings.pricing_model,
    )


@checkout_router.post(
    "/",
    response_model=OrderGroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Checkout: convert cart into orders",
)
def checkout(
    payload: CheckoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # validate cart 
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # get delivery address
    address = db.query(UserAddress).filter(
        UserAddress.id == payload.address_id,
        UserAddress.user_id == current_user.id,
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    # Addresses saved before the ward-level geography tables existed (migration
    # f4a29b7c1e05 added ward_id as nullable and never backfilled it) have no
    # ward. Without one the delivery fee can only ever resolve at county
    # granularity and the rider has no final-leg detail, so make the buyer
    # complete it here rather than quietly charging the coarser rate.
    if not address.ward_id:
        raise HTTPException(
            status_code=400,
            detail="This delivery address is missing its ward. Update the address and try again.",
        )

    # lock products and check stock
    product_ids = [item.product_id for item in cart.items]
    products = {
        p.id: p
        for p in db.query(Product)
            .filter(Product.id.in_(product_ids))
            .with_for_update()
            .all()
    }

    for item in cart.items:
        product = products[item.product_id]
        if product.stock_qty < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"'{product.name}' only has {product.stock_qty} units left in stock",
            )

    # create OrderGroup
    address_snapshot = {
        "first_name": address.first_name,
        "last_name": address.last_name,
        "phone": address.phone,
        "county": address.county,
        "town": address.town,
        "subcounty": address.ward.subcounty_name if address.ward else None,
        "ward": address.ward.name if address.ward else None,
        "exact_location": address.exact_location,
        "apartment": address.apartment,
        "lat": address.lat,
        "lng": address.lng,
        "sublocation": address.sublocation,
    }

    order_group = OrderGroup(
        buyer_id=current_user.id,
        delivery_address=address_snapshot,
        subtotal="0.00",
        delivery_fee="0.00",
        total="0.00",
    )
    db.add(order_group)
    db.flush()  # generates order_group.id

    # group cart items by shop
    items_by_shop: dict[uuid.UUID, list] = {}
    for item in cart.items:
        shop_id = products[item.product_id].shop_id
        items_by_shop.setdefault(shop_id, []).append(item)

    delivery_settings = get_or_create_rate_settings(db)

    group_fee_flat = Decimal("0.00")
    if delivery_settings.pricing_model == PricingModel.cost_based.value:
        # One journey for the whole cart, priced on distance and weight only.
        shops = _shops_by_id(db, items_by_shop.keys())
        cart_weight_kg = sum(
            (parse_weight_kg(products[item.product_id].weight_kg) * item.quantity for item in cart.items),
            Decimal("0"),
        )
        group_fee_flat = quote_delivery_fee(
            point_from_location(address),
            {shop_id: point_from_location(shops.get(shop_id)) for shop_id in items_by_shop},
            cart_weight_kg,
            delivery_settings,
        ).total
    else:
        # cart-total-tiered fee, charged once for the whole order group
        cart_total = sum(
            (Decimal(products[item.product_id].price) * item.quantity for item in cart.items),
            Decimal("0.00"),
        )
        group_fee_flat = calculate_delivery_fee_from_cart_total(cart_total)

    # create Orders, OrderItems, decrement stock
    group_subtotal = Decimal("0.00")

    for shop_id, shop_items in items_by_shop.items():
        order_subtotal = Decimal("0.00")

        order = Order(
            group_id=order_group.id,
            shop_id=shop_id,
            buyer_id=current_user.id,
            notes=payload.notes,
            subtotal="0.00",
            # Both pricing models charge one journey for the whole cart, so the
            # fee belongs to the group and no single order carries a share of it.
            delivery_fee="0.00",
            total="0.00",
        )
        db.add(order)
        db.flush()  # generates order.id

        for item in shop_items:
            product = products[item.product_id]
            unit_price = Decimal(product.price)
            line_total = unit_price * item.quantity
            order_subtotal += line_total

            snapshot = {
                "name": product.name,
                "price": product.price,
                "sku": product.sku,
                "image_url": product.images[0].url if product.images else None,
            }

            db.add(OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_snapshot=snapshot,
                quantity=item.quantity,
                unit_price=str(unit_price),
                discount_amount="0.00",
                line_total=str(line_total),
            ))

            # decrement stock on the locked product object
            product.stock_qty -= item.quantity

        order.subtotal = str(order_subtotal)
        order.total = str(order_subtotal)
        group_subtotal += order_subtotal

    group_delivery_fee = group_fee_flat

    # update group totals now that we know the real sum
    order_group.subtotal = str(group_subtotal)
    order_group.delivery_fee = str(group_delivery_fee)
    order_group.total = str(group_subtotal + group_delivery_fee)

    # clear the cart
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    # single commit, all or nothing
    db.commit()
    db.refresh(order_group)

    return order_group


# ── Orders ────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    "pending":    ["confirmed", "cancelled"],
    "confirmed":  ["processing"],
    "processing": ["shipped"],
    "shipped":    ["delivered"],
}


@orders_router.get(
    "/",
    response_model=list[OrderGroupRead],
    status_code=status.HTTP_200_OK,
    summary="Get my order history",
)
def get_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return (
        db.query(OrderGroup)
        .filter(OrderGroup.buyer_id == current_user.id)
        .order_by(OrderGroup.created_at.desc())
        .all()
    )


@orders_router.get(
    "/{order_group_id}",
    response_model=OrderGroupRead,
    status_code=status.HTTP_200_OK,
    summary="Get a single order group with all sub-orders",
)
def get_order(
    order_group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    order_group = db.query(OrderGroup).filter(
        OrderGroup.id == order_group_id,
        OrderGroup.buyer_id == current_user.id,
    ).first()

    if not order_group:
        raise HTTPException(status_code=404, detail="Order not found")

    return order_group


@orders_router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Seller updates the status of an order",
)
def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # confirm the order belongs to this seller's shop
    from app.models.shop import Shop
    shop = db.query(Shop).filter(
        Shop.id == order.shop_id,
        Shop.seller_id == current_user.id,
    ).first()
    if not shop:
        raise HTTPException(status_code=403, detail="Not your order")

    allowed = VALID_TRANSITIONS.get(order.status, [])
    if payload.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot move order from '{order.status}' to '{payload.status}'",
        )

    order.status = payload.status

    create_notification(
        db,
        user_id=order.buyer_id,
        type="order_status",
        title=f"Order update: {shop.name}",
        body=f"Your order is now '{payload.status.value}'.",
        data={"order_id": str(order.id), "status": payload.status.value},
    )

    db.commit()
    db.refresh(order)

    return order


@orders_router.patch(
    "/{order_id}/cancel",
    response_model=OrderRead,
    summary="Buyer cancels an order and stock is restored",
)
def cancel_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.buyer_id == current_user.id,
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in ("pending", "confirmed"):
        raise HTTPException(
            status_code=422,
            detail=f"Order cannot be cancelled once it is '{order.status}'",
        )

    # restore stock for each item in this order
    for item in order.items:
        if item.product_id:
            product = db.query(Product).filter(
                Product.id == item.product_id
            ).with_for_update().first()
            if product:
                product.stock_qty += item.quantity

    order.status = "cancelled"

    create_notification(
        db,
        user_id=order.shop.seller_id,
        type="order_cancelled",
        title="Order cancelled",
        body=f"{current_user.first_name} cancelled an order.",
        data={"order_id": str(order.id)},
    )

    db.commit()
    db.refresh(order)

    return order
