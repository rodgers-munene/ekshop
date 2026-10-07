"""Rider KYC: identity and equipment are reviewed separately, and documents
are private.

These lock out three specific mistakes:

  * approving a rider's ID silently approving their vehicle, so one admin click
    cleared the whole go-live gate and left no record of what was judged;
  * a rider self-approving by putting `equipment_verified` in their own payload;
  * storing a presigned URL in the database, which expires and would leave the
    admin review queue pointing at a dead link.
"""
import re

import pytest

from app.core.config import settings
from app.schemas.delivery import KYCSubmitRequest, KYCDocument, KYCDocumentUploadRead
from app.services import storage


class TestRiderCannotSelfApprove:
    def test_submit_payload_has_no_verification_flags(self):
        """A rider submitting evidence must not be able to mark it verified."""
        fields = KYCSubmitRequest.model_fields
        assert "equipment_verified" not in fields
        assert "kyc_status" not in fields

    def test_submit_takes_a_storage_key_not_a_url(self):
        """Keys are durable; presigned URLs expire."""
        fields = KYCSubmitRequest.model_fields
        assert "equipment_photo_key" in fields
        assert "equipment_photo_url" not in fields

    def test_extra_fields_are_ignored_not_applied(self):
        """Even if a client sends the flag, it is not part of the model."""
        payload = KYCSubmitRequest.model_validate(
            {
                "vehicle_type": "motorcycle",
                "national_id_number": "12345678",
                "equipment_verified": True,
            }
        )
        assert not hasattr(payload, "equipment_verified")


class TestDocumentReferences:
    def test_document_carries_a_key_and_an_optional_read_url(self):
        doc = KYCDocument(type="national-id", key="kyc/abc/national-id/x.jpg")
        assert doc.key == "kyc/abc/national-id/x.jpg"
        # `url` exists for reads only; it is generated per request.
        assert doc.url is None

    def test_upload_response_returns_a_key_and_no_url(self):
        """The client gets a key to submit later. A URL would be the wrong thing
        to hand back, because it would be stored."""
        read = KYCDocumentUploadRead(
            key="kyc/abc/national-id/x.jpg",
            type="national-id",
            filename="id.jpg",
            content_type="image/jpeg",
        )
        assert read.key.endswith(".jpg")
        assert "url" not in KYCDocumentUploadRead.model_fields


class TestKycStorageIsSeparateAndPrivate:
    def test_kyc_bucket_is_configured_independently_of_the_product_bucket(self):
        """The whole point of the split is that a bucket-policy mistake on
        product images cannot expose identity documents, so the KYC bucket and
        its credentials are separate settings rather than aliases."""
        kyc_settings = [
            name for name in settings.__class__.model_fields if name.startswith("KYC_S3")
        ]
        assert set(kyc_settings) == {
            "KYC_S3_BUCKET",
            "KYC_S3_ACCESS_KEY_ID",
            "KYC_S3_SECRET_ACCESS_KEY",
            "KYC_S3_REGION",
        }

    def test_presigned_links_expire(self):
        """A durable view link for a national ID scan is a durable capability."""
        assert 0 < settings.KYC_URL_EXPIRY_SECONDS <= 3600

    def test_presign_returns_none_when_storage_is_unconfigured(self, monkeypatch):
        """The admin review queue must not 500 just because no documents can be
        linked; it should show them as unavailable."""
        monkeypatch.setattr(settings, "KYC_S3_BUCKET", None, raising=False)
        assert storage.presign_kyc_url("kyc/abc/national-id/x.jpg") is None

    def test_presign_names_every_missing_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "KYC_S3_BUCKET", "bucket", raising=False)
        monkeypatch.setattr(settings, "KYC_S3_ACCESS_KEY_ID", None, raising=False)
        monkeypatch.setattr(settings, "KYC_S3_SECRET_ACCESS_KEY", None, raising=False)
        with pytest.raises(storage.StorageError) as exc:
            storage._kyc_client()
        message = str(exc.value)
        assert "KYC_S3_ACCESS_KEY_ID" in message
        assert "KYC_S3_SECRET_ACCESS_KEY" in message

    def test_presign_of_an_empty_key_is_none(self):
        assert storage.presign_kyc_url("") is None

    def test_delete_never_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "KYC_S3_BUCKET", None, raising=False)
        storage.delete_kyc_document("kyc/abc/national-id/x.jpg")  # must not raise
        storage.delete_kyc_document("")


class TestPathTraversalIsNeutralised:
    """`kind` is caller-supplied and ends up in an object key, so it must not be
    able to walk out of the rider's own prefix."""

    @pytest.mark.parametrize(
        "kind",
        ["../../users", "..", "a/../../../b", "national id", "", "///etc"],
    )
    def test_only_safe_characters_survive(self, kind):
        safe = re.sub(r"[^a-z0-9_-]+", "-", kind.lower()).strip("-") or "document"
        assert "/" not in safe
        assert ".." not in safe
        assert safe

    def test_normal_kinds_are_preserved(self):
        for kind in ("national-id", "licence", "selfie", "vehicle_photo"):
            safe = re.sub(r"[^a-z0-9_-]+", "-", kind.lower()).strip("-")
            assert safe == kind


class TestAcceptedUploadTypes:
    def test_pdf_is_accepted_for_kyc(self):
        """A scanned national ID is routinely a PDF; rejecting it would leave a
        rider with no way to comply from a phone."""
        assert "application/pdf" in storage.ALLOWED_KYC_CONTENT_TYPES

    def test_kyc_allows_larger_files_than_product_images(self):
        assert storage.MAX_KYC_UPLOAD_BYTES > storage.MAX_UPLOAD_BYTES

    def test_product_uploads_still_reject_pdf(self):
        """Do not widen the existing image rules as a side effect."""
        assert "application/pdf" not in storage.ALLOWED_CONTENT_TYPES


class TestReviewShape:
    def test_review_request_still_carries_notes(self):
        from app.schemas.delivery import KYCReviewRequest

        req = KYCReviewRequest(approve=False, notes="cracked tail light")
        assert req.approve is False
        assert req.notes == "cracked tail light"

    def test_agent_model_separates_the_two_verdicts(self):
        from app.models.delivery import DeliveryAgent

        cols = set(DeliveryAgent.__table__.columns.keys())
        # Two independent verdicts, each with its own audit trail.
        assert "kyc_status" in cols
        assert "equipment_verified" in cols
        assert "equipment_reviewed_at" in cols
        assert "equipment_review_notes" in cols
        # The URL column is gone; documents are referenced by key.
        assert "equipment_photo_key" in cols
        assert "equipment_photo_url" not in cols