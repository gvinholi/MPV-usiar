"""Bounded event projection, without page text or arbitrary error metadata."""
TIMELINE = """
WITH events AS (
 SELECT 'PROCESS_FIRST_SEEN' event_type, p.created_at occurred_at, 'Process persisted' summary,
 p.id reference_id, 'processes.created_at' timestamp_field FROM processes p WHERE p.id=:id
 UNION ALL
 SELECT 'PROCESS_CAPTURED', coalesce(o.captured_at,o.created_at), 'Process observation', o.id,
 CASE WHEN o.captured_at IS NULL THEN 'process_observations.created_at' ELSE 'process_observations.captured_at' END
 FROM process_observations o WHERE o.process_id=:id
 UNION ALL
 SELECT 'INITIAL_SCREENED', e.evaluated_at, e.state || ' / ' || e.reason_code, e.id, 'screening_evaluations.evaluated_at'
 FROM screening_evaluations e WHERE e.process_id=:id AND e.profile_id=:profile_id
 UNION ALL
 SELECT 'DOCUMENT_DISCOVERED',d.first_seen_at,'Document discovered',d.id,'process_documents.first_seen_at'
 FROM process_documents d WHERE d.process_id=:id
 UNION ALL
 SELECT 'DOCUMENT_ACQUIRED',a.acquired_at,CASE WHEN a.complete THEN 'Acquisition complete' ELSE 'Acquisition incomplete' END,
 a.id,'document_artifacts.acquired_at' FROM document_artifacts a JOIN process_documents d ON d.id=a.document_id WHERE d.process_id=:id
 UNION ALL
 SELECT 'TEXT_EXTRACTED',e.finished_at,e.status,e.id,'text_extractions.finished_at'
 FROM text_extractions e JOIN artifact_text_sources s ON s.id=e.source_id
 WHERE EXISTS (SELECT 1 FROM document_artifacts a JOIN process_documents d ON d.id=a.document_id WHERE d.process_id=:id AND a.artifact_id=s.artifact_id)
 UNION ALL
 SELECT 'DOCUMENT_SCREENED',e.evaluated_at,e.state || ' / ' || e.reason_code,e.id,'document_screening_evaluations.evaluated_at'
 FROM document_screening_evaluations e WHERE e.process_id=:id AND e.profile_id=:profile_id
 UNION ALL
 SELECT 'OPERATIONAL_RESOLVED',r.resolved_at,r.state || ' / ' || r.reason_code,r.id,'operational_resolutions.resolved_at'
 FROM operational_resolutions r WHERE r.process_id=:id AND r.profile_id=:profile_id
 UNION ALL
 SELECT 'HUMAN_REVIEWED',h.decided_at,h.decision || ' / ' || h.reason_code,h.id,'human_reviews.decided_at'
 FROM human_reviews h JOIN operational_resolutions r ON r.id=h.operational_resolution_id WHERE r.process_id=:id AND r.profile_id=:profile_id
)
"""
