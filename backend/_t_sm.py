"""Exercise the fulfillment state machine without touching the database."""
import os

os.environ.setdefault("DELIVERY_OTP_PEPPER", "test-pepper-not-for-production")

from app.models.fulfillment import DeliveryJob, DeliveryJobStatus
from app.services.fulfillment import (
    ALLOWED_TRANSITIONS,
    InvalidTransition,
    assert_transition_allowed,
    generate_otp,
    hash_otp,
    verify_otp,
    is_otp_expired,
)

print("== legal transitions ==")
for src, targets in ALLOWED_TRANSITIONS.items():
    print(f"  {src.value:<18} -> {sorted(t.value for t in targets)}")

print("\n== illegal transitions are rejected ==")
cases = [
    (DeliveryJobStatus.created, DeliveryJobStatus.delivered, "skip the whole trip"),
    (DeliveryJobStatus.created, DeliveryJobStatus.in_transit, "skip to transit"),
    (DeliveryJobStatus.delivered, DeliveryJobStatus.in_transit, "backwards"),
    (DeliveryJobStatus.settled, DeliveryJobStatus.delivered, "terminal reopened"),
    (DeliveryJobStatus.cancelled, DeliveryJobStatus.picked_up, "cancelled revived"),
    (DeliveryJobStatus.returned, DeliveryJobStatus.accepted, "returned revived"),
]
for src, dst, why in cases:
    try:
        assert_transition_allowed(src, dst)
        print(f"  FAIL  {src.value} -> {dst.value} was ALLOWED ({why})")
    except InvalidTransition as e:
        print(f"  ok    {src.value:<11} -> {dst.value:<13} rejected ({why})")

print("\n== legal transitions are accepted ==")
ok_cases = [
    (DeliveryJobStatus.created, DeliveryJobStatus.dispatch_requested),
    (DeliveryJobStatus.offered, DeliveryJobStatus.accepted),
    (DeliveryJobStatus.offered, DeliveryJobStatus.dispatch_requested, "wave 2"),
    (DeliveryJobStatus.accepted, DeliveryJobStatus.at_pickup),
    (DeliveryJobStatus.picked_up, DeliveryJobStatus.delivered),
    (DeliveryJobStatus.delivered, DeliveryJobStatus.settled),
    (DeliveryJobStatus.failed, DeliveryJobStatus.settled, "record cost of a failure"),
    (DeliveryJobStatus.accepted, DeliveryJobStatus.picked_up, "self-delivery skips rider trip"),
]
for case in ok_cases:
    src, dst = case[0], case[1]
    why = case[2] if len(case) > 2 else ""
    try:
        assert_transition_allowed(src, dst)
        print(f"  ok    {src.value:<11} -> {dst.value:<18} {why}")
    except InvalidTransition as e:
        print(f"  FAIL  {src.value} -> {dst.value}: {e}")

print("\n== OTP ==")
job = DeliveryJob(external_reference="abc123")
otp = generate_otp()
print("  length 6 and numeric:", len(otp) == 6 and otp.isdigit())
job.otp_hash = hash_otp(otp)
print("  correct code verifies :", verify_otp(job, otp))
print("  wrong code rejected   :", not verify_otp(job, "000000" if otp != "000000" else "111111"))
print("  blank rejected        :", not verify_otp(job, ""))
print("  no hash rejected      :", not verify_otp(DeliveryJob(), otp))
print("  hash is not the code  :", job.otp_hash != otp)

print("\n== pepper fails closed ==")
import importlib
import app.core.config as cfg
from app.services import fulfillment as fs
saved = cfg.settings.DELIVERY_OTP_PEPPER
cfg.settings.DELIVERY_OTP_PEPPER = None
try:
    fs._otp_pepper()
    print("  FAIL  hashing proceeded without a pepper")
except fs.FulfillmentError:
    print("  ok    refuses to hash without DELIVERY_OTP_PEPPER")
cfg.settings.DELIVERY_OTP_PEPPER = saved
