"""The fulfillment state machine's rules, tested without a database.

These cover the transition table, OTP handling and the exception hierarchy --
the three things that are pure logic and can be verified anywhere. The
database-backed behaviour (persistence, the append-only trigger, HTTP
authorisation) needs a live PostgreSQL and is exercised separately.
"""
import pytest

from datetime import datetime, timedelta, timezone

from app.models.fulfillment import DeliveryJob, DeliveryJobStatus
from app.services import fulfillment as fs


# --- exception hierarchy -----------------------------------------------------------

def test_invalid_transition_is_a_fulfillment_error():
    """It was a sibling class once, so every `except FulfillmentError` in a
    handler missed it and a rider got a 500 instead of a 409."""
    assert issubclass(fs.InvalidTransition, fs.FulfillmentError)


def test_a_rejected_transition_is_caught_by_the_base_class():
    try:
        raise fs.InvalidTransition("nope")
    except fs.FulfillmentError:
        return
    pytest.fail("InvalidTransition escaped `except FulfillmentError`")


# --- transition table --------------------------------------------------------------

@pytest.mark.parametrize(
    "src,dst",
    [
        (DeliveryJobStatus.created, DeliveryJobStatus.delivered),
        (DeliveryJobStatus.created, DeliveryJobStatus.in_transit),
        (DeliveryJobStatus.in_transit, DeliveryJobStatus.created),
        (DeliveryJobStatus.delivered, DeliveryJobStatus.in_transit),
        (DeliveryJobStatus.settled, DeliveryJobStatus.delivered),
        (DeliveryJobStatus.cancelled, DeliveryJobStatus.picked_up),
        (DeliveryJobStatus.returned, DeliveryJobStatus.accepted),
    ],
    ids=[
        "skips-the-trip", "skips-to-transit", "backwards", "backwards-after-delivery",
        "terminal-reopened", "cancelled-revived", "returned-revived",
    ],
)
def test_illegal_transitions_are_refused(src, dst):
    with pytest.raises(fs.InvalidTransition):
        fs.assert_transition_allowed(src, dst)


@pytest.mark.parametrize(
    "src,dst",
    [
        (DeliveryJobStatus.created, DeliveryJobStatus.dispatch_requested),
        (DeliveryJobStatus.offered, DeliveryJobStatus.accepted),
        (DeliveryJobStatus.offered, DeliveryJobStatus.dispatch_requested),
        (DeliveryJobStatus.accepted, DeliveryJobStatus.at_pickup),
        (DeliveryJobStatus.accepted, DeliveryJobStatus.picked_up),
        (DeliveryJobStatus.picked_up, DeliveryJobStatus.in_transit),
        (DeliveryJobStatus.in_transit, DeliveryJobStatus.delivered),
        (DeliveryJobStatus.delivered, DeliveryJobStatus.settled),
        (DeliveryJobStatus.failed, DeliveryJobStatus.settled),
    ],
    ids=[
        "dispatch", "accept", "re-offer", "arrive-at-pickup", "self-delivery-skips-rider",
        "in-transit", "delivered", "settle-a-delivery", "settle-a-failure",
    ],
)
def test_legal_transitions_are_allowed(src, dst):
    fs.assert_transition_allowed(src, dst)


@pytest.mark.parametrize(
    "status",
    [DeliveryJobStatus.settled, DeliveryJobStatus.cancelled, DeliveryJobStatus.returned],
)
def test_terminal_states_explain_themselves(status):
    """The message should tell the caller to create a new job, because that is
    the only legal way forward."""
    with pytest.raises(fs.InvalidTransition, match="new delivery job"):
        fs.assert_transition_allowed(status, DeliveryJobStatus.accepted)


# --- OTP ---------------------------------------------------------------------------

def test_generated_otp_is_six_digits():
    otp = fs.generate_otp()
    assert len(otp) == 6 and otp.isdigit()


def test_otp_verifies_and_rejects(monkeypatch):
    job = DeliveryJob(external_reference="abc123")
    otp = fs.generate_otp()
    job.otp_hash = fs.hash_otp(otp)
    assert fs.verify_otp(job, otp)
    assert not fs.verify_otp(job, "000000" if otp != "000000" else "111111")
    assert not fs.verify_otp(job, "")
    assert job.otp_hash != otp, "the code must not be stored in the clear"


def test_a_job_without_a_hash_never_verifies():
    assert not fs.verify_otp(DeliveryJob(), fs.generate_otp())


def test_hashing_refuses_without_the_pepper(monkeypatch):
    """A 6-digit code has a million possible values, so an unkeyed hash would be
    brute-forceable from a database dump."""
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "DELIVERY_OTP_PEPPER", None)
    with pytest.raises(fs.FulfillmentError):
        fs.hash_otp("123456")


def test_expiry():
    job = DeliveryJob(external_reference="abc")
    job.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert not fs.is_otp_expired(job)
    job.otp_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert fs.is_otp_expired(job)
    assert not fs.verify_otp(job, fs.generate_otp()), "an expired code must not verify"


# --- the two guards that protect the money ------------------------------------------

def test_otp_verification_requires_a_live_code():
    """The pricing path and the delivery path share one idea: a missing fact
    must fail closed rather than default to something plausible."""
    job = DeliveryJob(external_reference="abc")
    job.otp_hash = fs.hash_otp("123456")
    job.otp_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert fs.is_otp_expired(job)
    assert not fs.verify_otp(job, "123456")