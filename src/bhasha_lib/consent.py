"""Ethical consent verification and compliance module for oral literature and audio."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConsentError(ValueError):
    """Raised when oral literature or audio lacks required ethical consent."""


class ConsentStatus(StrEnum):
    """Permitted consent verification states."""

    PENDING = "pending"
    VERIFIED_WRITTEN = "verified_written"
    COMMUNITY_ELDER_APPROVED = "community_elder_approved"
    INSTITUTIONAL_BSS = "institutional_bss"


APPROVED_STATUSES: frozenset[str] = frozenset(
    {
        ConsentStatus.VERIFIED_WRITTEN.value,
        ConsentStatus.COMMUNITY_ELDER_APPROVED.value,
        ConsentStatus.INSTITUTIONAL_BSS.value,
    }
)


@dataclass(frozen=True)
class ConsentRecord:
    """Validated consent metadata for traditional folk songs and recordings."""

    status: str
    performer_name: str
    consent_holder: str
    document_ref: str | None = None
    institutional_partner: str | None = None
    permitted_uses: list[str] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        """Return True if the consent state is officially approved."""
        return self.status in APPROVED_STATUSES


def validate_consent_dict(
    consent_data: dict[str, Any] | None,
    item_title: str = "item",
) -> ConsentRecord:
    """Validate that consent metadata meets ethical compliance standards.

    Args:
        consent_data: Dictionary extracted from file frontmatter or manifest.
        item_title: Name/title of the item being evaluated (for error reporting).

    Raises:
        ConsentError: If consent block is missing, pending, or incomplete.

    Returns:
        Validated ConsentRecord instance.
    """
    if not consent_data or not isinstance(consent_data, dict):
        raise ConsentError(
            f"Ethical violation: '{item_title}' is missing a 'consent' block. "
            "Oral recordings and folk songs require verified written consent."
        )

    status = str(consent_data.get("status") or "").strip().lower()
    if not status:
        raise ConsentError(
            f"Consent validation failed for '{item_title}': 'status' is required."
        )

    if status == ConsentStatus.PENDING.value:
        raise ConsentError(
            f"Ingestion rejected for '{item_title}': Consent status is 'pending'. "
            "Only verified consent records can be ingested into the archive."
        )

    if status not in APPROVED_STATUSES:
        raise ConsentError(
            f"Invalid consent status '{status}' for '{item_title}'. "
            f"Allowed statuses: {sorted(APPROVED_STATUSES)}"
        )

    performer = str(consent_data.get("performer_name") or "").strip()
    if not performer:
        raise ConsentError(
            f"Consent validation failed for '{item_title}': "
            "'performer_name' is required to ensure proper attribution."
        )

    consent_holder = str(consent_data.get("consent_holder") or "").strip()
    document_ref = str(consent_data.get("document_ref") or "").strip() or None
    institutional_partner = (
        str(consent_data.get("institutional_partner") or "").strip() or None
    )

    # Ensure there is a verifiable documentation reference or institutional oversight
    if not document_ref and not institutional_partner:
        raise ConsentError(
            f"Consent validation failed for '{item_title}': Either 'document_ref' "
            "(path to signed form) or 'institutional_partner' (e.g. Bodo Sahitya "
            "Sabha) must be provided as verification proof."
        )

    permitted_raw = consent_data.get("permitted_uses") or []
    permitted_uses = (
        [str(u).strip() for u in permitted_raw if str(u).strip()]
        if isinstance(permitted_raw, list)
        else [str(permitted_raw).strip()]
    )

    return ConsentRecord(
        status=status,
        performer_name=performer,
        consent_holder=consent_holder,
        document_ref=document_ref,
        institutional_partner=institutional_partner,
        permitted_uses=permitted_uses,
    )
