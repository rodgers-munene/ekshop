from app.core.database import SessionLocal
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

s = SessionLocal()
pid = s.execute(text("SELECT id FROM products LIMIT 1")).scalar()
print("product:", pid)

def try_insert(email, user_id=None):
    from app.models.catalog import BackInStockSubscription
    sub = BackInStockSubscription(product_id=pid, email=email, user_id=user_id)
    s.add(sub)
    try:
        s.commit()
        return "inserted"
    except IntegrityError as e:
        s.rollback()
        return "blocked: " + str(e.orig).split("\n")[0][:60]

import uuid
print("guest  1st:", try_insert("g1@example.com"))
print("guest  dup:", try_insert("g1@example.com"))
uid = uuid.uuid4()
print("user   1st:", try_insert("u1@example.com", user_id=uid))
print("user   dup:", try_insert("u1@example.com", user_id=uid))
print("user other email same uid:", try_insert("u2@example.com", user_id=uid))

# cleanup
s.execute(text("DELETE FROM back_in_stock_subscriptions"))
s.commit()
s.close()
