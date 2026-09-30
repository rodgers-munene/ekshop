"""End-to-end exercise of the fulfillment state machine against the real DB.

Uses the ORM and the real service functions, so it covers schema, model
relationships and state transitions together.
"""
import os
import uuid

os.environ.setdefault("DELIVERY_OTP_PEPPER", "test-pepper-not-for-production")

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.database import SessionLocal
from app.models import User
from app.models.commerce import Order, OrderGroup
from app.models.shop import Shop
from app.models.delivery import DeliveryAgent
from app.models.fulfillment import (
    AssignmentStatus,
    DeliveryJob,
    DeliveryJobStatus,
    FulfillmentMode,
    FulfillmentPayer,
)
from app.services import fulfillment as fs

s = SessionLocal()
fails = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{(' -> ' + str(detail)[:70]) if detail else ''}")
    if not condition:
        fails.append(label)


suffix = uuid.uuid4().hex[:8]
buyer = User(email=f"b-{suffix}@example.com", password_hash="x", first_name="B",
             last_name="Y", role="buyer", status="active")
seller = User(email=f"s-{suffix}@example.com", password_hash="x", first_name="S",
              last_name="B", role="seller", status="active")
s.add_all([buyer, seller])
s.flush()

agent = DeliveryAgent(name="Rider One", email=f"r-{suffix}@example.com",
                      phone="+254700000000", password_hash="x", status="active")
agent2 = DeliveryAgent(name="Rider Two", email=f"r2-{suffix}@example.com",
                       phone="+254700000001", password_hash="x", status="active")
s.add_all([agent, agent2])
s.flush()

shop = Shop(seller_id=seller.id, name="T", slug=f"sh-{suffix}", status="active")
s.add(shop)
s.flush()

group = OrderGroup(buyer_id=buyer.id, status="paid", subtotal="100.00",
                   delivery_fee="60.00", tax_amount="16.00", total="176.00",
                   delivery_address={"county": "Nairobi"})
s.add(group)
s.flush()
order = Order(group_id=group.id, shop_id=shop.id, buyer_id=buyer.id,
              status="confirmed", subtotal="100.00", delivery_fee="60.00",
              tax_amount="16.00", total="176.00")
s.add(order)
s.commit()

print("== create_fulfillment ==")
f = fs.create_fulfillment(s, order.id, mode=FulfillmentMode.ekshop,
                          payer=FulfillmentPayer.customer, quoted_fee="60.00")
check("fulfillment created", f.id is not None)
check("order_id linked", str(f.order_id) == str(order.id))
check("starts pending", f.status.value == "pending", f.status.value)
check("forward job created", f.current_job is not None and f.current_job.attempt == 1)
check("initial event recorded", len(f.current_job.events) == 1, f.current_job.events[0].event_type)
check("no OTP at order creation (by design)", f.current_job.otp_hash is None)
check("quoted fee stored", str(f.quoted_fee) == "60.00", f.quoted_fee)

print("\n== assignment wave (job must be dispatch_requested first) ==")
job = f.current_job
try:
    fs.create_assignment(s, job, agent.id)
    check("cannot offer a job that has not been dispatched", False, "allowed")
except fs.FulfillmentError:
    check("cannot offer a job that has not been dispatched", True)

fs.transition_job(s, job, DeliveryJobStatus.dispatch_requested, event_type="DISPATCH_REQUESTED")
agent_id = agent.id
a1 = fs.create_assignment(s, job, agent_id, wave=1, payout_estimate="35.00",
                          distance_km="4.20", ttl_seconds=90)
check("assignment created as offered", a1.status.value == "offered", a1.status.value)
check("assignment has an id (flushed)", a1.id is not None)
check("offer event logs the assignment id",
      any(e.event_type == "OFFER_SENT" and e.payload.get("assignment_id") == str(a1.id)
          for e in job.events))
check("offer expiry stamped", a1.expires_at is not None)
fs.respond_to_assignment(s, a1, AssignmentStatus.declined, decline_reason="too far")
check("decline recorded", a1.status.value == "declined", a1.status.value)
a2 = fs.create_assignment(s, job, agent2.id, wave=2, ttl_seconds=90)
check("re-offer is a new row (wave 2)", a2.wave == 2 and a2.id != a1.id)
fs.respond_to_assignment(s, a2, AssignmentStatus.accepted)
check("accept recorded", a2.status.value == "accepted", a2.status.value)
try:
    fs.respond_to_assignment(s, a2, AssignmentStatus.declined)
    check("accepted assignment cannot flip to declined", False, "allowed")
except fs.FulfillmentError:
    check("accepted assignment cannot flip to declined", True)

print("\n== legal happy path ==")
for st in (DeliveryJobStatus.offered,
           DeliveryJobStatus.accepted, DeliveryJobStatus.at_pickup,
           DeliveryJobStatus.picked_up, DeliveryJobStatus.in_transit,
           DeliveryJobStatus.delivered):
    fs.transition_job(s, job, st, event_type=st.name.upper())
check("delivered", job.status.value == "delivered")
check("fulfillment derives delivered", f.status.value == "delivered", f.status.value)
check("delivered_at stamped", job.delivered_at is not None)
check("one event per transition", len(job.events) == 8, len(job.events))
check("last event is DELIVERED", job.events[-1].to_status == "delivered")
s.commit()
check("events survive a commit", len(s.get(DeliveryJob, job.id).events) == 8,
      len(s.get(DeliveryJob, job.id).events))

print("\n== illegal transition is refused ==")
try:
    fs.transition_job(s, job, DeliveryJobStatus.picked_up, event_type="BACK")
    check("backwards transition blocked", False, "it was allowed")
except fs.InvalidTransition:
    check("backwards transition blocked", True)

print("\n== OTP verify against the stored hash ==")
issued = fs.issue_otp(s, job, actor_user_id=seller.id, ttl_minutes=30)
check("issue_otp returns 6 digits", len(issued) == 6 and issued.isdigit())
check("correct code verifies", fs.verify_otp(job, issued))
check("wrong code rejected", not fs.verify_otp(job, "999999" if issued != "999999" else "111111"))
check("blank rejected", not fs.verify_otp(job, ""))
check("not expired", not fs.is_otp_expired(job))

print("\n== settlement ==")
js = fs.record_job_settlement(s, job, fee_collected="60.00", rider_payout="35.00",
                              incentive_paid="5.00", payment_fee="2.00")
check("job settlement created", js.id is not None)
check("contribution = 60-35-5-2 = 18.00", str(js.contribution) == "18.00", js.contribution)
check("job is settled", job.status.value == "settled", job.status.value)
check("job settled_at stamped", job.settled_at is not None)

fset = fs.settle_fulfillment(s, f, actor_user_id=seller.id)
check("fulfillment settlement created", fset.id is not None)
check("fee rolled up", str(fset.fee_collected) == "60.00", fset.fee_collected)
check("contribution rolled up", str(fset.contribution) == "18.00", fset.contribution)
check("margin_pct = 18/60 = 0.30", str(fset.margin_pct) == "0.3", fset.margin_pct)
check("fulfillment settled_at stamped", f.settled_at is not None)

print("\n== retry after failure keeps history ==")
o2 = s.get(Order, order.id)
f2 = fs.create_fulfillment(s, o2.id, mode=FulfillmentMode.ekshop)
j2 = f2.current_job
fs.transition_job(s, j2, DeliveryJobStatus.dispatch_requested, event_type="DISPATCH_REQUESTED")
fs.transition_job(s, j2, DeliveryJobStatus.failed, event_type="FAILED",
                  payload={"reason": "customer unavailable"})
check("attempt 1 failed", j2.status.value == "failed")
r2 = fs.open_retry_job(s, f2, actor_user_id=seller.id, reason="customer unavailable")
check("retry is a NEW job", r2.id != j2.id)
check("retry is attempt 2", r2.attempt == 2, r2.attempt)
check("retry type is forward", r2.job_type.value == "forward", r2.job_type.value)
check("fulfillment follows the retry", f2.current_job.id == r2.id)
check("fulfillment status back to pending", f2.status.value == "pending", f2.status.value)
check("attempt 1 still failed and preserved", j2.status.value == "failed")
check("both jobs retained", len(f2.jobs) == 2, len(f2.jobs))
check("retry has its own event", len(r2.events) >= 1, [e.event_type for e in r2.events])

print("\n== return leg ==")
rj = fs.open_return_job(s, f2, actor_user_id=seller.id, reason="customer refused")
check("return job created", rj.job_type.value == "return", rj.job_type.value)
check("return is a new attempt", rj.attempt == 3, rj.attempt)

print("\n== database rejects a duplicate attempt ==")
try:
    s.execute(text(
        "INSERT INTO delivery_jobs (id, fulfillment_id, external_reference, attempt, "
        "job_type, status, created_at, updated_at) "
        "SELECT :i, fulfillment_id, :r, 2, 'forward', 'created', now(), now() "
        "FROM delivery_jobs WHERE id = :j"),
        {"i": uuid.uuid4(), "r": uuid.uuid4().hex, "j": r2.id})
    s.commit()
    check("duplicate (fulfillment, attempt) blocked", False, "accepted")
except IntegrityError as e:
    s.rollback()
    check("duplicate (fulfillment, attempt) blocked", True, str(e.orig).split("\n")[0][:44])

print("\n== append-only event table ==")
for label, sql in [("UPDATE", "UPDATE delivery_job_events SET notes='x' WHERE job_id=:j"),
                   ("DELETE", "DELETE FROM delivery_job_events WHERE job_id=:j")]:
    try:
        s.execute(text(sql), {"j": r2.id})
        s.commit()
        check(f"{label} of a job event blocked", False, "allowed")
    except DBAPIError as e:
        s.rollback()
        check(f"{label} of a job event blocked", True, str(e.orig).split("\n")[0][:56])

# cleanup
s.execute(text("DELETE FROM delivery_job_events WHERE job_id IN (SELECT id FROM delivery_jobs WHERE fulfillment_id IN (SELECT id FROM fulfillments WHERE order_id = :o))"), {"o": order.id})
s.execute(text("DELETE FROM job_settlements WHERE job_id IN (SELECT id FROM delivery_jobs WHERE fulfillment_id IN (SELECT id FROM fulfillments WHERE order_id = :o))"), {"o": order.id})
s.execute(text("DELETE FROM delivery_assignments WHERE job_id IN (SELECT id FROM delivery_jobs WHERE fulfillment_id IN (SELECT id FROM fulfillments WHERE order_id = :o))"), {"o": order.id})
s.execute(text("DELETE FROM delivery_jobs WHERE fulfillment_id IN (SELECT id FROM fulfillments WHERE order_id = :o)"), {"o": order.id})
s.execute(text("DELETE FROM fulfillment_settlements WHERE fulfillment_id IN (SELECT id FROM fulfillments WHERE order_id = :o)"), {"o": order.id})
s.execute(text("DELETE FROM fulfillments WHERE order_id = :o"), {"o": order.id})
s.execute(text("DELETE FROM orders WHERE id = :o"), {"o": order.id})
s.execute(text("DELETE FROM order_groups WHERE id = :g"), {"g": group.id})
s.execute(text("DELETE FROM delivery_agents WHERE id IN (:a,:b)"), {"a": agent.id, "b": agent2.id})
s.execute(text("DELETE FROM shops WHERE id = :s"), {"s": shop.id})
s.execute(text("DELETE FROM users WHERE id IN (:a,:b)"), {"a": buyer.id, "b": seller.id})
s.commit()
s.close()

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))