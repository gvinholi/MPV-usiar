"""Static SQL projections. Caller values are bound; identifiers are allowlisted."""
from dataclasses import fields
from types import SimpleNamespace

from collector.application.human_review.models import HumanReviewDecision, HumanReviewStatus, in_queue
from collector.application.read_model.models import OpportunityListItem

BASE = """
WITH observations AS (
 SELECT o.*, row_number() OVER (PARTITION BY process_id ORDER BY captured_at DESC NULLS LAST, created_at DESC, id DESC) rn
 FROM process_observations o
), resolutions AS (
 SELECT r.*, row_number() OVER (PARTITION BY process_id, profile_id ORDER BY resolved_at DESC, created_at DESC, resolution_fingerprint DESC) rn
 FROM operational_resolutions r WHERE profile_id = :profile_id
), reviews AS (
 SELECT h.*, row_number() OVER (PARTITION BY operational_resolution_id ORDER BY decided_at DESC, created_at DESC, sequence DESC) rn
 FROM human_reviews h
), acquisitions AS (
 SELECT a.*, row_number() OVER (PARTITION BY document_id ORDER BY acquired_at DESC, created_at DESC, id DESC) rn
 FROM document_artifacts a
), extractions AS (
 SELECT e.*, row_number() OVER (PARTITION BY source_id ORDER BY finished_at DESC, created_at DESC, extractor_name DESC, extractor_version DESC, id DESC) rn
 FROM text_extractions e
), document_flags AS (
 SELECT d.id, d.process_id, d.first_seen_at, a.artifact_id,
 EXISTS (SELECT 1 FROM artifact_text_sources s JOIN extractions e ON e.source_id=s.id AND e.rn=1
         WHERE s.artifact_id=a.artifact_id AND e.pages_with_text > 0) has_text
 FROM process_documents d LEFT JOIN acquisitions a ON a.document_id=d.id AND a.rn=1
), document_counts AS (
 SELECT process_id, count(*) documents_count, bool_or(has_text) has_text,
 count(*) FILTER (WHERE artifact_id IS NOT NULL) documents_with_artifact,
 count(*) FILTER (WHERE has_text) documents_with_text
 FROM document_flags GROUP BY process_id
), base AS (
 SELECT p.id process_id, p.created_at first_seen_at,
 o.source, identity.official_id, o.description, left(o.description,300) description_preview,
 o.organization_name, o.organization_cnpj, o.locality municipality_name, o.state uf, o.modality,
 o.estimated_value, o.published_at publication_at, o.closes_at proposal_deadline_at, o.official_url,
 o.notice_number,
 o.captured_at latest_capture_at, o.id observation_id, o.round_id, o.created_at observation_persisted_at,
 r.id operational_resolution_id, r.state operational_state, r.reason_code operational_reason,
 r.resolved_at operational_resolved_at,
 CASE WHEN h.id IS NOT NULL THEN 'REVIEWED'
      WHEN EXISTS (SELECT 1 FROM human_reviews old_h JOIN operational_resolutions old_r ON old_r.id=old_h.operational_resolution_id
                   WHERE old_r.process_id=p.id AND old_r.profile_id=:profile_id) THEN 'STALE'
      ELSE 'UNREVIEWED' END human_review_status,
 h.id review_id, h.decision human_decision, h.reason_code human_reason, h.decided_at reviewed_at,
 h.reviewer_id, h.reviewer_display_name,
 coalesce(d.documents_count,0) documents_count, coalesce(d.has_text,false) has_text,
 coalesce(d.documents_with_artifact,0) documents_with_artifact,
 coalesce(d.documents_with_text,0) documents_with_text,
 EXISTS (SELECT 1 FROM document_screening_evaluations de WHERE de.process_id=p.id AND de.profile_id=:profile_id) has_document_screening
 FROM processes p
 LEFT JOIN observations o ON o.process_id=p.id AND o.rn=1
 LEFT JOIN LATERAL (SELECT official_id FROM source_identities si WHERE si.process_id=p.id AND si.source=o.source ORDER BY official_id LIMIT 1) identity ON true
 LEFT JOIN resolutions r ON r.process_id=p.id AND r.rn=1
 LEFT JOIN reviews h ON h.operational_resolution_id=r.id AND h.rn=1
 LEFT JOIN document_counts d ON d.process_id=p.id
)
"""

LIST_COLUMNS = ', '.join('b.' + f.name for f in fields(OpportunityListItem))


def time_predicate(column, period, params, prefix):
    clauses = []
    if period.from_datetime is not None:
        params[prefix + "_from"] = period.from_datetime
        clauses.append(f"{column} >= :{prefix}_from")
    if period.to_datetime is not None:
        params[prefix + "_to"] = period.to_datetime
        clauses.append(f"{column} < :{prefix}_to")
    return " AND ".join(clauses) or "true"


def queue_predicate(queue, include_discarded=False):
    # Compile the existing Commit 15 pure policy into a finite SQL predicate.
    # There is no separate dashboard definition of what belongs in a queue.
    clauses = []
    for state in ("CANDIDATE", "PENDING", "DISCARDED"):
        for status in HumanReviewStatus:
            decisions = tuple(HumanReviewDecision) if status == HumanReviewStatus.REVIEWED else (None,)
            for decision in decisions:
                item = SimpleNamespace(operational_state=state, human_review_status=status, human_decision=decision)
                if in_queue(item, queue, include_discarded):
                    human = "b.human_decision IS NULL" if decision is None else f"b.human_decision='{decision.value}'"
                    clauses.append(f"(b.operational_state='{state}' AND b.human_review_status='{status.value}' AND {human})")
    return '(' + ' OR '.join(clauses) + ')' if clauses else "false"


def filter_predicate(filters, params):
    clauses = []
    for field, column in (
        ("operational_state", "operational_state"), ("human_review_status", "human_review_status"),
        ("human_decision", "human_decision"), ("uf", "uf"), ("municipality", "municipality_name"),
        ("modality", "modality"), ("has_text", "has_text"), ("has_document_screening", "has_document_screening"),
    ):
        value = getattr(filters, field)
        if value is not None:
            params[field] = value
            clauses.append(f"b.{column}=:{field}")
    if filters.source:
        params['source'] = filters.source
        clauses.append("EXISTS (SELECT 1 FROM source_identities si WHERE si.process_id=b.process_id AND si.source=:source)")
    if filters.has_documents is not None:
        clauses.append("b.documents_count > 0" if filters.has_documents else "b.documents_count = 0")
    for name, column in (("publication", "publication_at"), ("proposal_deadline", "proposal_deadline_at"), ("captured", "latest_capture_at")):
        clauses.append(time_predicate('b.' + column, getattr(filters, name), params, name))
    if filters.search:
        # Literal substring: % and _ supplied by caller are not SQL wildcards.
        params['search'] = '%' + filters.search.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        clauses.append("b.description ILIKE :search ESCAPE '!'")
    if filters.review_queue:
        clauses.append(queue_predicate(filters.review_queue, filters.include_operational_discarded))
    return ' AND '.join(clauses) or 'true'
