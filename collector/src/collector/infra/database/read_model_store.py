"""Read-only, consistent PostgreSQL projections over the existing schema."""
from contextlib import contextmanager
from dataclasses import fields, replace
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy import text

from collector.application.human_review.models import (
    HumanReviewDecision, HumanReviewReason, HumanReviewStatus, ReviewQueue, ReviewQueueItem, ReviewerIdentity,
)
from collector.application.read_model.errors import (
    AmbiguousProfileError, CollectionRoundNotFoundError, OpportunityNotFoundError, ProfileNotFoundError,
)
from collector.application.read_model.filters import OpportunityFilters, OpportunitySort, TimeRange
from collector.application.read_model.models import (
    CollectionRoundDetail, CollectionRoundListItem, CurrentSnapshot, DashboardReviewQueueItem,
    DashboardSummary, DocumentCoverage, DocumentEvidenceItem, DocumentMemberItem, DocumentScreeningItem,
    ExtractionMetadata, HumanReviewItem, InitialEvidenceItem, InitialScreeningItem, LatestObservation,
    ModalityOutcomeItem, OperationalResolutionItem, OpportunityCounters, OpportunityDetail,
    OpportunityDocumentItem, OpportunityListItem, OpportunityTimelineItem, PeriodActivity, PilotFunnel,
    SourceCoverageSummary, SourceIdentityItem,
)
from collector.application.read_model.pagination import Page, Pagination
from .read_model_sql import BASE, LIST_COLUMNS, filter_predicate, queue_predicate, time_predicate


def public_url(value):
    """Only public HTTP(S) references; never storage keys or signed/query URLs."""
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return None
        if host == 'localhost' or '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
            return None
        try:
            if not ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value
    except ValueError:
        return None


def _dto(cls, row):
    return cls(**{f.name: row[f.name] for f in fields(cls)})


def _item(row):
    values = {f.name: row[f.name] for f in fields(OpportunityListItem)}
    values['human_review_status'] = HumanReviewStatus(values['human_review_status'])
    if values['human_decision']:
        values['human_decision'] = HumanReviewDecision(values['human_decision'])
    values['official_url'] = public_url(values['official_url'])
    return OpportunityListItem(**values)


class SqlAlchemyReadModelStore:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @contextmanager
    def _snapshot(self):
        with self._session_factory() as session:
            session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})
            session.execute(text('SET TRANSACTION READ ONLY'))
            yield session
            # Close rolls back the read transaction; there is no write/commit path.

    def _profile(self, session, scope):
        column = 'id' if scope.profile_id is not None else 'code'
        rows = session.execute(text(f'SELECT id FROM screening_profiles WHERE {column}=:value'),
                               {'value': scope.profile_id or scope.profile_code}).scalars().all()
        if not rows:
            raise ProfileNotFoundError(str(scope))
        if len(rows) > 1:
            raise AmbiguousProfileError('profile_code has multiple versions; use profile_id')
        return rows[0]

    def _require_process(self, session, process_id):
        if not session.scalar(text('SELECT id FROM processes WHERE id=:id'), {'id': process_id}):
            raise OpportunityNotFoundError(str(process_id))

    def _list(self, session, profile_id, filters, pagination, sort, *, queue=False):
        params = {'profile_id': profile_id, 'limit': pagination.page_size, 'offset': pagination.offset}
        predicate = filter_predicate(filters, params)
        total = session.scalar(text(BASE + f'SELECT count(*) FROM base b WHERE {predicate}'), params)
        # Enum validation also applies to direct adapter callers.
        sort = OpportunitySort(sort.field, sort.direction)
        columns = LIST_COLUMNS + (', b.reviewer_id, b.reviewer_display_name' if queue else '')
        rows = session.execute(text(BASE + f'SELECT {columns} FROM base b WHERE {predicate} '
            f'ORDER BY b.{sort.field.value} {sort.direction.value} NULLS LAST, b.process_id ASC LIMIT :limit OFFSET :offset'), params).mappings()
        items = []
        for row in rows:
            item = _item(row)
            if queue:
                review = ReviewQueueItem(item.process_id, profile_id, item.operational_resolution_id,
                    item.operational_state, item.operational_reason, item.operational_resolved_at,
                    item.human_review_status, item.human_decision,
                    HumanReviewReason(item.human_reason) if item.human_reason else None,
                    ReviewerIdentity(row['reviewer_id'], row['reviewer_display_name']) if row['reviewer_id'] else None,
                    item.reviewed_at)
                items.append(DashboardReviewQueueItem(item, review))
            else:
                items.append(item)
        return Page(tuple(items), pagination.page, pagination.page_size, total)

    def list_opportunities(self, scope, filters=OpportunityFilters(), pagination=Pagination(), sort=OpportunitySort()):
        with self._snapshot() as session:
            return self._list(session, self._profile(session, scope), filters, pagination, sort)

    def review_queue(self, scope, queue=ReviewQueue.NEEDS_REVIEW, filters=OpportunityFilters(), pagination=Pagination(), sort=OpportunitySort()):
        filters = replace(filters, review_queue=ReviewQueue(queue))
        with self._snapshot() as session:
            return self._list(session, self._profile(session, scope), filters, pagination, sort, queue=True)

    def get_opportunity(self, process_id, scope):
        with self._snapshot() as session:
            return self._detail(session, process_id, self._profile(session, scope))

    def get_opportunity_by_source_identity(self, source, official_id, scope):
        with self._snapshot() as session:
            process_id = session.scalar(text('SELECT process_id FROM source_identities WHERE source=:source AND official_id=:official_id'),
                                        {'source': source, 'official_id': official_id})
            if process_id is None:
                raise OpportunityNotFoundError(f'{source}/{official_id}')
            return self._detail(session, process_id, self._profile(session, scope))

    def _detail(self, session, process_id, profile_id):
        params = {'profile_id': profile_id, 'id': process_id}
        row = session.execute(text(BASE + 'SELECT * FROM base WHERE process_id=:id'), params).mappings().first()
        if row is None:
            raise OpportunityNotFoundError(str(process_id))
        identities = tuple(_dto(SourceIdentityItem, r) for r in session.execute(text(
            'SELECT source, official_id FROM source_identities WHERE process_id=:id ORDER BY source, official_id'), params).mappings())
        initial = session.execute(text('SELECT * FROM screening_evaluations WHERE process_id=:id AND profile_id=:profile_id ORDER BY evaluated_at DESC, created_at DESC, engine_version DESC, id DESC LIMIT 1'), params).mappings().first()
        initial_item = None
        if initial:
            evidence = tuple(_dto(InitialEvidenceItem, e) for e in session.execute(text(
                'SELECT category, configured_term, matched_text, field FROM screening_evidence WHERE evaluation_id=:evaluation ORDER BY category, configured_term, id'), {'evaluation': initial['id']}).mappings())
            initial_item = InitialScreeningItem(initial['id'], initial['state'], initial['reason_code'], initial['engine_version'], initial['evaluated_at'], evidence)
        document = self._latest_document_screening(session, params)
        document_item = None
        if document:
            coverage = DocumentCoverage(*(document[k] for k in ('documents_considered', 'sources_considered', 'pages_considered', 'pages_with_text', 'likely_scanned_sources', 'failed_sources', 'unsupported_sources', 'complete')))
            document_item = DocumentScreeningItem(document['id'], document['state'], document['reason_code'], document['engine_version'], document['document_set_fingerprint'], document['evaluated_at'], coverage)
        resolution_item = None
        if row['operational_resolution_id']:
            r = session.execute(text('SELECT * FROM operational_resolutions WHERE id=:id'), {'id': row['operational_resolution_id']}).mappings().one()
            divergence = None if r['state_diverged'] is None or r['reason_diverged'] is None else (
                'STATE_AND_REASON' if r['state_diverged'] and r['reason_diverged'] else
                'STATE_ONLY' if r['state_diverged'] else 'REASON_ONLY' if r['reason_diverged'] else 'NONE')
            resolution_item = OperationalResolutionItem(r['id'], r['initial_evaluation_id'], r['document_evaluation_id'], r['state'], r['reason_code'], r['rule_code'], r['resolution_fingerprint'], r['resolved_at'], r['state_diverged'], r['reason_diverged'], divergence)
        current = self._human_review(session, row['review_id']) if row['review_id'] else None
        historical = session.execute(text('SELECT h.id FROM human_reviews h JOIN operational_resolutions r ON r.id=h.operational_resolution_id WHERE r.process_id=:id AND r.profile_id=:profile_id ORDER BY h.decided_at DESC,h.created_at DESC,h.sequence DESC LIMIT 1'), params).scalar()
        last_review = current if current and current.review_id == historical else self._human_review(session, historical) if historical else None
        counts = session.execute(text(BASE + '''SELECT
            (SELECT count(*) FROM document_flags WHERE process_id=:id) documents,
            (SELECT count(DISTINCT artifact_id) FROM document_flags WHERE process_id=:id) artifacts,
            count(DISTINCT e.source_id) extracted_sources, coalesce(sum(e.page_count),0) pages,
            coalesce(sum(e.pages_with_text),0) pages_with_text
            FROM extractions e WHERE e.rn=1 AND e.source_id IN (
              SELECT s.id FROM artifact_text_sources s WHERE s.artifact_id IN (SELECT artifact_id FROM document_flags WHERE process_id=:id))'''), params).mappings().one()
        observation = LatestObservation(row['observation_id'], row['round_id'], row['source'], row['latest_capture_at'], row['observation_persisted_at']) if row['observation_id'] else None
        return OpportunityDetail(_item(row), row['description'], identities, observation, initial_item,
            document_item, resolution_item, current, last_review, _dto(OpportunityCounters, counts))

    def _human_review(self, session, review_id):
        row = session.execute(text('SELECT * FROM human_reviews WHERE id=:id'), {'id': review_id}).mappings().one()
        return HumanReviewItem(row['id'], row['operational_resolution_id'], HumanReviewDecision(row['decision']), row['reason_code'], row['reviewer_id'], row['reviewer_display_name'], row['comment'], row['decided_at'], row['was_stale_at_decision'])

    def _latest_document_screening(self, session, params):
        return session.execute(text('SELECT * FROM document_screening_evaluations WHERE process_id=:id AND profile_id=:profile_id ORDER BY evaluated_at DESC,created_at DESC,document_set_fingerprint DESC,id DESC LIMIT 1'), params).mappings().first()

    def document_evidence(self, process_id, scope, pagination=Pagination()):
        with self._snapshot() as session:
            self._require_process(session, process_id)
            params = {'id': process_id, 'profile_id': self._profile(session, scope)}
            evaluation = self._latest_document_screening(session, params)
            if not evaluation:
                return Page((), pagination.page, pagination.page_size, 0)
            params = {'id': evaluation['id'], 'limit': pagination.page_size, 'offset': pagination.offset}
            total = session.scalar(text('SELECT count(*) FROM document_screening_evidence WHERE evaluation_id=:id'), params)
            columns = ','.join(f.name for f in fields(DocumentEvidenceItem))
            rows = session.execute(text(f'SELECT {columns} FROM document_screening_evidence WHERE evaluation_id=:id ORDER BY source_path,page_number,start_offset,id LIMIT :limit OFFSET :offset'), params).mappings()
            return Page(tuple(_dto(DocumentEvidenceItem, r) for r in rows), pagination.page, pagination.page_size, total)

    def documents(self, process_id, pagination=Pagination()):
        with self._snapshot() as session:
            self._require_process(session, process_id)
            params = {'id': process_id, 'profile_id': None, 'limit': pagination.page_size, 'offset': pagination.offset}
            total = session.scalar(text('SELECT count(*) FROM process_documents WHERE process_id=:id'), params)
            rows = session.execute(text(BASE + '''SELECT d.*, a.artifact_id, a.complete, a.reason_code,
                a.acquired_at, art.sha256 artifact_sha256, art.detected_type
                FROM process_documents d LEFT JOIN acquisitions a ON a.document_id=d.id AND a.rn=1
                LEFT JOIN artifacts art ON art.id=a.artifact_id WHERE d.process_id=:id
                ORDER BY d.first_seen_at,d.id LIMIT :limit OFFSET :offset'''), params).mappings().all()
            artifact_ids = list({r['artifact_id'] for r in rows if r['artifact_id']})
            extraction_by_artifact = {}
            members_by_artifact = {}
            if artifact_ids:
                extractions = session.execute(text(BASE + '''SELECT s.artifact_id,s.archive_entry_id,s.sha256,s.detected_type,
                    e.id extraction_id,s.id source_id,e.extractor_name,e.extractor_version,e.status,
                    e.page_count pages,e.pages_with_text,e.likely_scanned,e.started_at,e.finished_at
                    FROM artifact_text_sources s LEFT JOIN extractions e ON e.source_id=s.id AND e.rn=1
                    WHERE s.artifact_id=ANY(:ids) ORDER BY s.source_path,s.id'''), {'profile_id': None, 'ids': artifact_ids}).mappings().all()
                by_entry = {}
                for e in extractions:
                    if e['extraction_id'] is not None:
                        extraction_by_artifact.setdefault(e['artifact_id'], []).append(_dto(ExtractionMetadata, e))
                    if e['archive_entry_id']:
                        by_entry[e['archive_entry_id']] = e
                members = session.execute(text('''SELECT id,artifact_id,original_path,is_directory,is_encrypted,is_symlink,has_unsafe_path
                    FROM artifact_archive_entries WHERE artifact_id=ANY(:ids) ORDER BY original_path,id'''), {'ids': artifact_ids}).mappings()
                for member in members:
                    e = by_entry.get(member['id'])
                    item = DocumentMemberItem(member['original_path'], e['sha256'] if e else None,
                        e['detected_type'] if e else None,
                        not (member['has_unsafe_path'] or member['is_encrypted'] or member['is_symlink']),
                        bool(e and e['status'] in ('DIGITAL_TEXT', 'EMPTY_TEXT', 'LIKELY_SCANNED')),
                        e['pages'] if e else None, e['status'] if e else None)
                    members_by_artifact.setdefault(member['artifact_id'], []).append(item)
            items = []
            for row in rows:
                extracts = tuple(extraction_by_artifact.get(row['artifact_id'], ()))
                statuses = {e.status for e in extracts}
                status = next(iter(statuses)) if len(statuses) == 1 else 'MIXED' if statuses else None
                acquisition = None if row['acquired_at'] is None else 'COMPLETE' if row['complete'] else 'INCOMPLETE'
                items.append(OpportunityDocumentItem(row['id'], row['official_document_id'], row['title'], row['document_type'],
                    row['source'], public_url(row['url']), row['first_seen_at'], row['last_seen_at'], row['artifact_id'] is not None,
                    row['artifact_sha256'], row['detected_type'], acquisition, row['acquired_at'], status,
                    sum(e.pages for e in extracts) if extracts else None,
                    any(e.likely_scanned for e in extracts) if extracts else None, extracts,
                    tuple(members_by_artifact.get(row['artifact_id'], ()))))
            return Page(tuple(items), pagination.page, pagination.page_size, total)

    def timeline(self, process_id, scope, pagination=Pagination()):
        from .read_model_timeline import TIMELINE
        with self._snapshot() as session:
            self._require_process(session, process_id)
            params = {'id': process_id, 'profile_id': self._profile(session, scope),
                      'limit': pagination.page_size, 'offset': pagination.offset}
            total = session.scalar(text(TIMELINE + 'SELECT count(*) FROM events'), params)
            rows = session.execute(text(TIMELINE + 'SELECT * FROM events ORDER BY occurred_at ASC,event_type ASC,reference_id ASC LIMIT :limit OFFSET :offset'), params).mappings()
            items = tuple(OpportunityTimelineItem(r['event_type'], r['occurred_at'], r['event_type'].replace('_', ' ').title(),
                r['summary'], r['reference_id'], (('timestamp_field', r['timestamp_field']),)) for r in rows)
            return Page(items, pagination.page, pagination.page_size, total)

    def _round_items(self, session, rows):
        ids = [r['id'] for r in rows]
        outcomes = {}
        if ids:
            for r in session.execute(text('''SELECT round_id, modality_code, complete, pages_processed,records_received,
                processes_mapped,failed_page, failure_reason IS NOT NULL has_failure,
                jsonb_array_length(mapping_errors) mapping_errors_count
                FROM collection_modality_outcomes WHERE round_id=ANY(:ids) ORDER BY modality_code'''), {'ids': ids}).mappings():
                # Free-form transport errors can contain URLs/headers. Expose a
                # structured failure indicator, never raw exception payloads.
                item = ModalityOutcomeItem(r['modality_code'],r['complete'],r['pages_processed'],r['records_received'],
                    r['processes_mapped'],r['failed_page'],'COLLECTION_FAILURE' if r['has_failure'] else None,r['mapping_errors_count'])
                outcomes.setdefault(r['round_id'], []).append(item)
        return tuple(CollectionRoundListItem(r['id'],r['source'],r['started_at'],r['finished_at'],r['status'],
            r['pages_expected'],r['pages_processed'],r['pages_with_error'],r['records_collected'],r['unique_processes'],
            tuple(o.modality_code for o in outcomes.get(r['id'], ())),tuple(outcomes.get(r['id'], ()))) for r in rows)

    def collection_rounds(self, period=TimeRange(), pagination=Pagination(), source=None):
        with self._snapshot() as session:
            params = {'limit': pagination.page_size, 'offset': pagination.offset}
            predicate = time_predicate('started_at', period, params, 'rounds')
            if source is not None:
                predicate += ' AND source=:source'
                params['source'] = source
            total = session.scalar(text(f'SELECT count(*) FROM collection_rounds WHERE {predicate}'), params)
            rows = session.execute(text(f'SELECT * FROM collection_rounds WHERE {predicate} ORDER BY started_at DESC,id LIMIT :limit OFFSET :offset'), params).mappings().all()
            return Page(self._round_items(session, rows), pagination.page, pagination.page_size, total)

    def collection_round_detail(self, round_id):
        with self._snapshot() as session:
            row = session.execute(text('SELECT * FROM collection_rounds WHERE id=:id'), {'id': round_id}).mappings().first()
            if row is None:
                raise CollectionRoundNotFoundError(str(round_id))
            item = self._round_items(session, [row])[0]
            return CollectionRoundDetail(item, *(row[k] for k in ('errors','candidates','selected','pending','discarded','documents_found')))

    def _source_coverage(self, session, period):
        params = {}
        predicate = time_predicate('r.started_at', period, params, 'coverage')
        rows = session.execute(text(f'''WITH scoped AS (SELECT r.* FROM collection_rounds r WHERE {predicate})
            SELECT r.source, count(*) rounds, count(*) FILTER (WHERE status='SUCCESS') successful_rounds,
            count(*) FILTER (WHERE status='PARTIAL') partial_rounds, count(*) FILTER (WHERE status='FAILED') failed_rounds,
            coalesce(sum(records_collected),0) records_collected,
            (SELECT count(DISTINCT o.process_id) FROM process_observations o JOIN scoped sr ON sr.id=o.round_id WHERE sr.source=r.source) unique_processes
            FROM scoped r GROUP BY r.source ORDER BY r.source'''), params).mappings()
        return tuple(_dto(SourceCoverageSummary, r) for r in rows)

    def source_coverage(self, period=TimeRange()):
        with self._snapshot() as session:
            return self._source_coverage(session, period)

    def dashboard_summary(self, scope, period=TimeRange()):
        with self._snapshot() as session:
            profile_id = self._profile(session, scope)
            params = {'profile_id': profile_id}
            cohort = time_predicate('b.first_seen_at', period, params, 'cohort')
            needs_review = queue_predicate(ReviewQueue.NEEDS_REVIEW)
            snapshot = session.execute(text(BASE + f'''SELECT count(*) processes_total,
                count(*) FILTER (WHERE operational_state='CANDIDATE') current_candidate,
                count(*) FILTER (WHERE operational_state='PENDING') current_pending,
                count(*) FILTER (WHERE operational_state='DISCARDED') current_discarded,
                count(*) FILTER (WHERE {needs_review}) needs_review,
                count(*) FILTER (WHERE human_decision='SELECTED') selected,
                count(*) FILTER (WHERE human_decision='PENDING') human_pending,
                count(*) FILTER (WHERE human_decision='DISCARDED') human_discarded,
                count(*) FILTER (WHERE human_review_status='STALE') stale_reviews,
                coalesce(sum(documents_count),0) documents_total,
                coalesce(sum(documents_with_artifact),0) documents_with_artifact,
                coalesce(sum(documents_with_text),0) documents_with_text
                FROM base b WHERE {cohort}'''), params).mappings().one()
            snapshot = _dto(CurrentSnapshot, snapshot)
            rounds_period = time_predicate('started_at', period, params, 'rounds')
            processes_period = time_predicate('created_at', period, params, 'processes')
            documents_period = time_predicate('first_seen_at', period, params, 'documents')
            screenings_period = time_predicate('evaluated_at', period, params, 'screenings')
            resolutions_period = time_predicate('resolved_at', period, params, 'resolutions')
            reviews_period = time_predicate('h.decided_at', period, params, 'reviews')
            activity = session.execute(text(f'''SELECT
                (SELECT coalesce(sum(records_collected),0) FROM collection_rounds WHERE {rounds_period}) records_collected,
                (SELECT count(*) FROM processes WHERE {processes_period}) processes_first_seen,
                (SELECT count(*) FROM process_documents WHERE {documents_period}) documents_discovered,
                (SELECT count(*) FROM document_screening_evaluations WHERE profile_id=:profile_id AND {screenings_period}) document_screenings_total,
                (SELECT count(*) FROM operational_resolutions WHERE profile_id=:profile_id AND {resolutions_period}) operational_resolutions_total,
                (SELECT count(*) FROM human_reviews h JOIN operational_resolutions r ON r.id=h.operational_resolution_id WHERE r.profile_id=:profile_id AND {reviews_period}) human_reviews_total,
                count(*) rounds_total, count(*) FILTER (WHERE status='SUCCESS') rounds_success,
                count(*) FILTER (WHERE status='PARTIAL') rounds_partial, count(*) FILTER (WHERE status='FAILED') rounds_failed
                FROM collection_rounds WHERE {rounds_period}'''), params).mappings().one()
            activity = _dto(PeriodActivity, activity)
            initial = session.execute(text(BASE + f''', initial AS (
                SELECT e.*, row_number() OVER (PARTITION BY process_id ORDER BY evaluated_at DESC,created_at DESC,engine_version DESC,id DESC) rn
                FROM screening_evaluations e WHERE profile_id=:profile_id)
                SELECT count(*) FILTER (WHERE i.state='CANDIDATE') candidate,
                count(*) FILTER (WHERE i.state='PENDING') pending,
                count(*) FILTER (WHERE i.state='DISCARDED') discarded,
                count(*) FILTER (WHERE b.has_document_screening) document_evaluated
                FROM base b LEFT JOIN initial i ON i.process_id=b.process_id AND i.rn=1 WHERE {cohort}'''), params).mappings().one()
            funnel = PilotFunnel(activity.records_collected, snapshot.processes_total, initial['candidate'], initial['pending'], initial['discarded'],
                initial['document_evaluated'], snapshot.current_candidate, snapshot.current_pending, snapshot.current_discarded,
                snapshot.selected,snapshot.human_pending,snapshot.human_discarded)
            return DashboardSummary(profile_id,period,snapshot,activity,funnel,self._source_coverage(session,period))

    def pilot_funnel(self, scope, period=TimeRange()):
        return self.dashboard_summary(scope,period).funnel
