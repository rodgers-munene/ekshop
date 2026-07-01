from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, status
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import update, delete

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.commerce import Cart, CartItem, UserAddress, OrderGroup, Order, OrderItem
from app.models.catalog import Product
from app.schemas.commerce import (
    CartRead,
    CartItemRead,
    CartItemCreate,
    CheckoutCreate,
    OrderGroupRead,
    OrderRead,
    OrderStatusUpdate,
)

cart_router = APIRouter(prefix="/cart", tags=["cart"])
checkout_router = APIRouter(prefix="/checkout", tags=["checkout"])
orders_router = APIRouter(prefix="/orders", tags=["orders"])

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
    "/",
    response_model=OrderGroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Checkout — convert cart into orders",
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
        "exact_location": address.exact_location,
        "apartment": address.apartment,
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

    # update group totals now that we know the real sum
    order_group.subtotal = str(group_subtotal)
    order_group.total = str(group_subtotal)

    # clear the cart
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    # single commit — all or nothing
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
    db.commit()
    db.refresh(order)

    return order
