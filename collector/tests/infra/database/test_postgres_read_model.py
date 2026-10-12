from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from collector.application import (
    EvaluateDocumentScreening, OperationalResolver, PersistCollection, PersistDocumentScreening,
    PersistOperationalResolution, PersistScreening, ScreeningEngine, usiar_v1,
)
from collector.application.human_review import (
    HumanReviewDecision as D, HumanReviewReason as HR, HumanReviewStatus as HS,
    RecordHumanReview, RecordHumanReviewCommand, ReviewerIdentity, ReviewQueue,
)
from collector.application.read_model import (
    AmbiguousProfileError, CollectionRoundNotFoundError, DashboardQueries, OpportunityFilters as F,
    OpportunityNotFoundError, OpportunitySort, Pagination, ProfileNotFoundError, ProfileScope,
    SortDirection, SortField, TimeRange,
)
from collector.domain import RoundStatus, ScreeningStatus
from collector.infra.database import (
    SqlAlchemyCollectionRepository, SqlAlchemyDocumentScreeningRepository,
    SqlAlchemyOperationalResolutionRepository, SqlAlchemyScreeningRepository,
)
from collector.infra.database.human_review_store import SqlAlchemyHumanReviewRepository
from collector.infra.database.read_model_store import SqlAlchemyReadModelStore
from tests.application.persistence.factories import collection_result, outcome, process
from tests.infra.database.test_postgres_resolution import _seed, CANDIDATE_TEXT

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


@pytest.fixture
def dataset(migrated_engine, db_session):
    factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    persist = PersistCollection(SqlAlchemyCollectionRepository(factory), clock=lambda: NOW)
    screening = PersistScreening(SqlAlchemyScreeningRepository(factory))
    profile = screening.persist_profile(usiar_v1())
    operational = PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factory), clock=lambda: NOW)
    human_repo = SqlAlchemyHumanReviewRepository(factory)
    review = RecordHumanReview(human_repo, clock=lambda: NOW)
    snapshots = [replace(process(f'READ-{i}', description=CANDIDATE_TEXT + f' {i}',
        estimated_value=Decimal(i)+Decimal('0.01'),last_captured_at=NOW+timedelta(seconds=i)),
        official_url=None if i == 0 else 'https://pncp.gov.br/app/editais/example',
        notice_number='EDITAL-1/2026' if i == 1 else None) for i in range(7)]
    persist.persist(collection_result(*snapshots,started_at=NOW,ended_at=NOW+timedelta(minutes=1)))
    resolutions = []
    with factory() as session:
        observations = dict(session.execute(text('SELECT process_id,id FROM process_observations')).all())
    for i, snapshot in enumerate(snapshots):
        initial = ScreeningEngine(clock=lambda: NOW).evaluate(profile, description=snapshot.description,
            process_id=snapshot.id,observation_id=observations[snapshot.id],profile_id=profile.id)
        screening.persist_evaluation(initial)
        state = ScreeningStatus.PENDING if i == 1 else ScreeningStatus.DISCARDED if i == 2 else ScreeningStatus.CANDIDATE
        resolution = replace(OperationalResolver().resolve(initial,None),state=state,resolved_at=NOW)
        operational.persist(resolution)
        resolutions.append(resolution)
        if i >= 3:
            decision, reason = {3:(D.SELECTED,HR.TECHNICAL_FIT),4:(D.PENDING,HR.NEEDS_DOCUMENT_REVIEW),
                5:(D.DISCARDED,HR.COMMERCIAL_DECISION),6:(D.SELECTED,HR.TECHNICAL_FIT)}[i]
            review.execute(RecordHumanReviewCommand(resolution.id,ReviewerIdentity('gabriel'),decision,reason,str(uuid4())))
        if i == 6:
            operational.persist(replace(resolution,id=uuid4(),resolution_fingerprint='new-fingerprint',resolved_at=NOW+timedelta(minutes=1)))
    store = SqlAlchemyReadModelStore(factory)
    return factory,store,DashboardQueries(store),ProfileScope(profile_id=profile.id),snapshots,resolutions,persist,human_repo


def test_summary_funnel_and_current_states(dataset):
    _,store,query,scope,processes,resolutions,_,_ = dataset
    summary = query.dashboard_summary(scope)
    s = summary.current_snapshot
    assert (s.processes_total,s.current_candidate,s.current_pending,s.current_discarded) == (7,5,1,1)
    assert (s.needs_review,s.selected,s.human_pending,s.human_discarded,s.stale_reviews) == (3,1,1,1,1)
    assert summary.period_activity.records_collected == 7
    assert summary.period_activity.operational_resolutions_total == 8
    assert summary.period_activity.human_reviews_total == 4
    assert summary.funnel.initial_candidate == 7
    assert query.pilot_funnel(scope) == summary.funnel
    stale = query.get_opportunity(processes[6].id,scope)
    assert stale.opportunity.human_review_status == HS.STALE
    assert stale.current_human_review is None
    assert stale.latest_historical_review.decision == D.SELECTED
    assert stale.opportunity.operational_resolution_id != resolutions[6].id
    assert query.list_opportunities(scope,F(human_decision=D.SELECTED)).total_items == 1


@pytest.mark.parametrize('filters,expected', [
    (F(operational_state='CANDIDATE'),5),(F(operational_state='PENDING'),1),
    (F(operational_state='DISCARDED'),1),(F(human_review_status=HS.STALE),1),
    (F(human_decision=D.PENDING),1),(F(human_decision=D.DISCARDED),1),
    (F(source='PNCP'),7),(F(source='RHS'),0),(F(uf='sp'),7),(F(uf='RJ'),0),
    (F(municipality='Campinas'),7),(F(modality='Pregão Eletrônico'),7),
    (F(has_documents=False),7),(F(has_documents=True),0),(F(has_text=True),0),
    (F(has_document_screening=True),0),(F(search=' 3'),1),(F(search="%' OR true --"),0),
    (F(captured=TimeRange(NOW,NOW+timedelta(seconds=2))),2),
    (F(publication=TimeRange(NOW,None)),0),(F(proposal_deadline=TimeRange(NOW,None)),7),
])
def test_filters(dataset,filters,expected):
    _,_,query,scope,*_ = dataset
    assert query.list_opportunities(scope,filters).total_items == expected


def test_pagination_sort_decimal_timezone_nullability(dataset):
    _,_,query,scope,snapshots,*_ = dataset
    first = query.list_opportunities(scope,pagination=Pagination(1,3))
    second = query.list_opportunities(scope,pagination=Pagination(2,3))
    assert first.total_items == 7 and first.total_pages == 3
    assert len({p.process_id for p in first.items+second.items}) == 6
    assert first.items[0].process_id == snapshots[-1].id
    assert query.list_opportunities(scope,pagination=Pagination(99,3)).items == ()
    ordered = query.list_opportunities(scope,sort=OpportunitySort(SortField.ESTIMATED_VALUE,SortDirection.ASC))
    item = ordered.items[0]
    assert item.estimated_value == Decimal('0.01') and isinstance(item.estimated_value,Decimal)
    assert item.latest_capture_at.utcoffset() is not None
    assert item.official_url is None
    assert item.notice_number is None
    assert item.human_decision is None
    assert item.documents_count == 0


def test_review_queue_parity(dataset):
    _,_,query,scope,_,_,_,human_repo = dataset
    for queue in ReviewQueue:
        old = {x.process_id for x in human_repo.list_queue(queue)}
        new = {x.opportunity.process_id for x in query.review_queue(scope,queue).items}
        assert old == new
    assert query.review_queue(scope,filters=F(include_operational_discarded=True)).total_items == 4


def test_detail_lookup_not_found_and_no_large_list_text(dataset):
    factory,store,query,scope,snapshots,*_ = dataset
    detail = query.get_opportunity_by_source_identity('PNCP','READ-0',scope)
    assert detail.opportunity.process_id == snapshots[0].id
    assert detail.initial_screening.evidence
    assert detail.initial_screening.evidence[0].field == 'description'
    assert detail.operational_resolution.initial_evaluation_id == detail.initial_screening.evaluation_id
    assert detail.latest_observation.captured_at == NOW
    assert detail.document_screening is None
    with pytest.raises(OpportunityNotFoundError): query.get_opportunity(uuid4(),scope)
    with pytest.raises(OpportunityNotFoundError): query.get_opportunity_by_source_identity('PNCP','missing',scope)
    with pytest.raises(OpportunityNotFoundError): query.documents(uuid4())
    with pytest.raises(CollectionRoundNotFoundError): query.collection_round_detail(uuid4())
    with factory.begin() as s:
        s.execute(text('UPDATE process_observations SET description=:description WHERE process_id=:id'),
                  {'description':'á'*5000,'id':snapshots[0].id})
    item = query.list_opportunities(scope,F(search='á')).items[0]
    assert item.description_preview == 'á'*300
    assert len(query.get_opportunity(snapshots[0].id,scope).description) == 5000


def test_rounds_zero_success_failed_partial_and_coverage(dataset):
    _,_,query,_,_,_,persist,_ = dataset
    for status in (RoundStatus.SUCCESS,RoundStatus.PARTIAL,RoundStatus.FAILED):
        persist.persist(collection_result(status=status,started_at=NOW,ended_at=NOW+timedelta(minutes=1),
            outcomes=(outcome(complete=status==RoundStatus.SUCCESS,records_received=0,processes_mapped=0,
                failed_page=None if status==RoundStatus.SUCCESS else 1,
                failure_reason=None if status==RoundStatus.SUCCESS else 'https://secret.internal/?token=PRIVATE'),)))
    rounds = query.collection_rounds()
    assert rounds.total_items == 4
    zero = [query.collection_round_detail(r.round_id) for r in rounds.items if r.records_collected==0]
    assert {r.round.status for r in zero} == {'SUCCESS','PARTIAL','FAILED'}
    assert {r.errors for r in zero} == {0,1}
    assert 'PRIVATE' not in repr(zero)
    coverage = query.source_coverage()[0]
    assert (coverage.source,coverage.rounds,coverage.successful_rounds,coverage.partial_rounds,coverage.failed_rounds) == ('PNCP',4,2,1,1)
    assert coverage.unique_processes == 7
    assert coverage.records_collected == 7


def test_temporal_snapshot_and_activity(dataset):
    factory,_,query,scope,snapshots,resolutions,persist,_ = dataset
    period = TimeRange(NOW,NOW+timedelta(seconds=1))
    before = query.dashboard_summary(scope,period)
    assert before.current_snapshot.processes_total == 7
    assert before.period_activity.operational_resolutions_total == 7
    assert before.period_activity.human_reviews_total == 4
    # One cohort member was first persisted before the period; current snapshot
    # must exclude it, but its resolution/review activity remains time-scoped.
    with factory.begin() as s:
        s.execute(text('UPDATE processes SET created_at=:old WHERE id=:id'),{'old':NOW-timedelta(days=1),'id':snapshots[3].id})
    after = query.dashboard_summary(scope,period)
    assert after.current_snapshot.processes_total == 6 and after.current_snapshot.selected == 0
    assert after.period_activity.human_reviews_total == 4
    assert after.funnel.unique_processes == 6
    empty = query.dashboard_summary(scope,TimeRange(NOW+timedelta(days=3),NOW+timedelta(days=4)))
    assert empty.current_snapshot.processes_total == 0
    assert empty.period_activity.rounds_total == 0
    assert empty.funnel.records_collected == 0
    assert empty.source_coverage == ()
    # Exclusive upper boundary excludes rows exactly at NOW.
    assert query.dashboard_summary(scope,TimeRange(NOW-timedelta(seconds=1),NOW)).period_activity.human_reviews_total == 0


def test_profile_isolation(dataset):
    factory,_,query,scope,snapshots,*_ = dataset
    profile = PersistScreening(SqlAlchemyScreeningRepository(factory)).persist_profile(replace(usiar_v1(),id=uuid4(),code='SECOND'))
    other = ProfileScope(profile_code='SECOND')
    result = query.dashboard_summary(other)
    assert result.current_snapshot.processes_total == 7
    assert result.current_snapshot.current_candidate == 0
    assert result.period_activity.human_reviews_total == 0
    assert query.get_opportunity(snapshots[3].id,other).current_human_review is None
    assert query.document_evidence(snapshots[0].id,other).total_items == 0
    screening = PersistScreening(SqlAlchemyScreeningRepository(factory))
    with factory() as session:
        observation = session.scalar(text('SELECT id FROM process_observations WHERE process_id=:id'),{'id':snapshots[3].id})
    initial = ScreeningEngine().evaluate(profile,description='Compra de peças para ar condicionado.',
        process_id=snapshots[3].id,observation_id=observation,profile_id=profile.id)
    screening.persist_evaluation(initial)
    resolution = OperationalResolver().resolve(initial,None)
    PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factory)).persist(resolution)
    RecordHumanReview(SqlAlchemyHumanReviewRepository(factory)).execute(RecordHumanReviewCommand(
        resolution.id,ReviewerIdentity('celso'),D.DISCARDED,HR.COMMERCIAL_DECISION,str(uuid4())))
    assert query.get_opportunity(snapshots[3].id,other).current_human_review.decision == D.DISCARDED
    assert query.get_opportunity(snapshots[3].id,scope).current_human_review.decision == D.SELECTED
    assert query.dashboard_summary(other).current_snapshot.human_discarded == 1
    PersistScreening(SqlAlchemyScreeningRepository(factory)).persist_profile(replace(usiar_v1(),id=uuid4(),version='another'))
    with pytest.raises(AmbiguousProfileError): query.list_opportunities(ProfileScope(profile_code=usiar_v1().code))
    with pytest.raises(ProfileNotFoundError): query.list_opportunities(ProfileScope(profile_id=uuid4()))
    assert query.list_opportunities(scope).total_items == 7


def test_read_only_database_and_consistent_snapshot(dataset):
    factory,store,_,_,snapshots,*_ = dataset
    with pytest.raises(DBAPIError):
        with store._snapshot() as s:
            s.execute(text('UPDATE processes SET updated_at=now()'))
    with store._snapshot() as s:
        assert s.scalar(text('SHOW transaction_isolation')) == 'repeatable read'
        assert s.scalar(text('SHOW transaction_read_only')) == 'on'
        before = s.scalar(text('SELECT count(*) FROM processes'))
        with factory.begin() as writer:
            writer.execute(text('INSERT INTO processes(id,created_at,updated_at) VALUES (:id,:now,:now)'),{'id':uuid4(),'now':NOW})
        assert s.scalar(text('SELECT count(*) FROM processes')) == before


def test_statement_count_constant_for_30_processes(dataset,migrated_engine):
    _,_,query,scope,_,_,persist,_ = dataset
    statements=[]
    def observe(connection,cursor,statement,parameters,context,executemany):
        statements.append(statement)
    event.listen(migrated_engine,'before_cursor_execute',observe)
    try:
        query.list_opportunities(scope,pagination=Pagination(1,100))
        small=len(statements)
        persist.persist(collection_result(*(process(f'PERF-{i}') for i in range(23))))
        statements.clear()
        page=query.list_opportunities(scope,pagination=Pagination(1,100))
        large=len(statements)
        assert page.total_items == 30
        assert large == small == 4  # SET READ ONLY, profile, count, page
        print(f'List SQL statements: 7 processes={small}; 30 processes={large}; SELECTs=3')
    finally:
        event.remove(migrated_engine,'before_cursor_execute',observe)


def test_rich_documents_evidence_timeline(migrated_engine,db_session,persist_service,tmp_path):
    factory=sessionmaker(bind=migrated_engine,autoflush=False,expire_on_commit=False)
    snapshot=_seed(factory,persist_service,tmp_path,official_id='READ-RICH',sequential=3341,
        description=CANDIDATE_TEXT,page_text=CANDIDATE_TEXT)
    screening=PersistScreening(SqlAlchemyScreeningRepository(factory))
    profile=screening.persist_profile(usiar_v1())
    observation=db_session.execute(text('SELECT id FROM process_observations')).scalar_one()
    initial=ScreeningEngine().evaluate(profile,description=snapshot.description,process_id=snapshot.id,observation_id=observation,profile_id=profile.id)
    screening.persist_evaluation(initial)
    doc=EvaluateDocumentScreening(SqlAlchemyDocumentScreeningRepository(factory)).evaluate_process(snapshot.id,profile)
    PersistDocumentScreening(SqlAlchemyDocumentScreeningRepository(factory),SqlAlchemyScreeningRepository(factory)).persist_evaluation(doc)
    resolution=OperationalResolver().resolve(initial,doc)
    PersistOperationalResolution(SqlAlchemyOperationalResolutionRepository(factory)).persist(resolution)
    RecordHumanReview(SqlAlchemyHumanReviewRepository(factory)).execute(RecordHumanReviewCommand(
        resolution.id,ReviewerIdentity('gabriel'),D.SELECTED,HR.TECHNICAL_FIT,str(uuid4())))
    query=DashboardQueries(SqlAlchemyReadModelStore(factory))
    scope=ProfileScope(profile_id=profile.id)
    detail=query.get_opportunity(snapshot.id,scope)
    assert detail.document_screening.coverage.pages == 1
    assert detail.counters.pages == detail.counters.pages_with_text == 1
    assert detail.counters.artifacts == detail.counters.extracted_sources == 1
    assert detail.operational_resolution.divergence_kind is not None
    assert detail.current_human_review.decision == D.SELECTED
    documents=query.documents(snapshot.id)
    assert documents.total_items==1
    item=documents.items[0]
    assert item.has_artifact and item.artifact_sha256
    assert item.text_status=='DIGITAL_TEXT' and item.extracted_pages==1
    assert item.likely_scanned is False
    assert item.extractions[0].extractor_name
    evidence=query.document_evidence(snapshot.id,scope)
    assert evidence.total_items>0
    assert evidence.items[0].page_number==1 and evidence.items[0].context_snippet
    assert not hasattr(evidence.items[0],'text')
    timeline=query.timeline(snapshot.id,scope)
    assert {e.event_type for e in timeline.items} == {'PROCESS_FIRST_SEEN','PROCESS_CAPTURED','INITIAL_SCREENED',
        'DOCUMENT_DISCOVERED','DOCUMENT_ACQUIRED','TEXT_EXTRACTED','DOCUMENT_SCREENED','OPERATIONAL_RESOLVED','HUMAN_REVIEWED'}
    assert list(e.occurred_at for e in timeline.items)==sorted(e.occurred_at for e in timeline.items)
    assert query.timeline(snapshot.id,scope,Pagination(2,3)).total_pages == 3
    s=query.dashboard_summary(scope).current_snapshot
    assert s.documents_total==s.documents_with_artifact==s.documents_with_text==1
    assert query.list_opportunities(scope,F(has_text=True,has_document_screening=True,has_documents=True)).total_items==1


def test_historical_selected_is_not_current_and_timeline_preserves_it(dataset):
    _,_,query,scope,snapshots,resolutions,_,human_repo=dataset
    RecordHumanReview(human_repo,clock=lambda:NOW+timedelta(seconds=1)).execute(RecordHumanReviewCommand(
        resolutions[3].id,ReviewerIdentity('celso'),D.DISCARDED,HR.COMMERCIAL_DECISION,str(uuid4())))
    assert query.list_opportunities(scope,F(human_decision=D.SELECTED)).total_items==0
    assert query.list_opportunities(scope,F(human_decision=D.DISCARDED)).total_items==2
    events=query.timeline(snapshots[3].id,scope).items
    reviews=[e for e in events if e.event_type=='HUMAN_REVIEWED']
    assert len(reviews)==2 and reviews[0].summary.startswith('SELECTED')
    assert reviews[1].summary.startswith('DISCARDED')


@pytest.mark.parametrize('field',list(SortField))
@pytest.mark.parametrize('direction',list(SortDirection))
def test_all_sorts_deterministic(dataset,field,direction):
    _,_,query,scope,*_=dataset
    ordering=OpportunitySort(field,direction)
    first=query.list_opportunities(scope,sort=ordering)
    second=query.list_opportunities(scope,sort=ordering)
    assert first==second
    values=[getattr(x,field.value) for x in first.items if getattr(x,field.value) is not None]
    assert values==sorted(values,reverse=direction==SortDirection.DESC)


def test_missing_values_and_unsafe_urls_are_not_fabricated(dataset):
    factory,_,query,scope,snapshots,*_=dataset
    with factory.begin() as s:
        s.execute(text('''UPDATE process_observations SET estimated_value=NULL,closes_at=NULL,captured_at=NULL,
            official_url='http://127.0.0.1/storage?token=private' WHERE process_id=:id'''),{'id':snapshots[0].id})
    detail=query.get_opportunity(snapshots[0].id,scope)
    assert detail.opportunity.estimated_value is None
    assert detail.opportunity.proposal_deadline_at is None
    assert detail.opportunity.latest_capture_at is None
    assert detail.opportunity.official_url is None
    captured=next(e for e in query.timeline(snapshots[0].id,scope).items if e.event_type=='PROCESS_CAPTURED')
    assert captured.metadata==(('timestamp_field','process_observations.created_at'),)


def test_zip_and_unacquired_document(migrated_engine,db_session,persist_service,tmp_path):
    from collector.application import (AcquireDocumentArtifact,ExtractArtifactText,PersistDocumentAcquisition,
        PersistDocumentCatalog,PersistTextExtraction)
    from collector.infra.database import (SqlAlchemyDocumentAcquisitionRepository,
        SqlAlchemyDocumentCatalogRepository,SqlAlchemyTextExtractionRepository)
    from collector.infra.acquisition import LocalArtifactStorage
    from collector.infra.extraction import PypdfTextExtractor
    from tests.application.acquisition.fakes import FakeDownloader
    from tests.application.acquisition.zip_fixtures import zip_bytes
    from tests.application.extraction.pdf_fixtures import ONE_PAGE_PDF
    from tests.infra.database.test_postgres_text import _catalog_document
    from tests.infra.pncp.document_fixtures import observed_document
    factory=sessionmaker(bind=migrated_engine,autoflush=False,expire_on_commit=False)
    snapshot=process('READ-ZIP')
    persist_service.persist(collection_result(snapshot))
    catalog=PersistDocumentCatalog(SqlAlchemyDocumentCatalogRepository(factory))
    document=_catalog_document(catalog,snapshot.id,observed_document())
    _catalog_document(catalog,snapshot.id,observed_document(sequential=123))
    storage=LocalArtifactStorage(tmp_path)
    acquired=AcquireDocumentArtifact(FakeDownloader(zip_bytes(('edital.pdf',ONE_PAGE_PDF),('notas.txt',b'notes'))),storage).acquire(document)
    PersistDocumentAcquisition(SqlAlchemyDocumentAcquisitionRepository(factory)).persist(acquired)
    PersistTextExtraction(SqlAlchemyTextExtractionRepository(factory)).persist(
        ExtractArtifactText(storage,PypdfTextExtractor()).extract(acquired.artifact))
    query=DashboardQueries(SqlAlchemyReadModelStore(factory))
    items=query.documents(snapshot.id).items
    zip_item=next(x for x in items if x.has_artifact)
    missing=next(x for x in items if not x.has_artifact)
    assert zip_item.detected_type=='ZIP'
    member=next(x for x in zip_item.members if x.path=='edital.pdf')
    assert member.safe and member.extracted and member.pages==1 and member.sha256
    skipped=next(x for x in zip_item.members if x.path=='notas.txt')
    assert skipped.extracted is False
    assert skipped.pages == 0 and skipped.text_status == 'UNSUPPORTED'
    assert missing.acquisition_status is missing.text_status is missing.extracted_pages is missing.likely_scanned is None
    assert missing.artifact_sha256 is None and missing.extractions==()
    assert 'storage_key' not in repr(items)


def test_latest_observation_and_distinct_source_coverage(dataset):
    _,_,query,scope,snapshots,_,persist,_=dataset
    newer=replace(snapshots[0],description='latest description',last_captured_at=NOW+timedelta(days=1))
    persist.persist(collection_result(newer,started_at=NOW+timedelta(days=1),ended_at=NOW+timedelta(days=1,minutes=1)))
    detail=query.get_opportunity(snapshots[0].id,scope)
    assert detail.description=='latest description'
    assert detail.opportunity.latest_capture_at==NOW+timedelta(days=1)
    assert query.source_coverage()[0].unique_processes==7
    assert query.source_coverage()[0].records_collected==8
    assert query.list_opportunities(scope).total_items==7


def test_official_fields_are_read_from_persisted_snapshot(dataset):
    _,_,query,scope,snapshots,*_=dataset
    item=query.get_opportunity(snapshots[1].id,scope).opportunity
    assert item.notice_number=='EDITAL-1/2026'
    assert item.official_url=='https://pncp.gov.br/app/editais/example'


def test_all_queries_preserve_persisted_rows(dataset):
    factory,_,query,scope,snapshots,*_=dataset
    from sqlalchemy import inspect
    def contents():
        with factory() as s:
            names=inspect(s.connection()).get_table_names()
            return {name: sorted(s.execute(text('SELECT row_to_json(t)::text FROM '+
                    s.bind.dialect.identifier_preparer.quote(name)+' t')).scalars()) for name in names}
    before=contents()
    query.dashboard_summary(scope)
    query.list_opportunities(scope)
    query.get_opportunity(snapshots[3].id,scope)
    query.documents(snapshots[0].id)
    query.document_evidence(snapshots[0].id,scope)
    query.timeline(snapshots[3].id,scope)
    query.review_queue(scope)
    rounds=query.collection_rounds()
    query.collection_round_detail(rounds.items[0].round_id)
    query.source_coverage()
    assert contents()==before
