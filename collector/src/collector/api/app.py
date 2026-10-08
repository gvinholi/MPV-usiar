"""FastAPI composition root and read-only HTTP routes."""
import logging
from time import perf_counter
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from collector.application.human_review.models import HumanReviewDecision, HumanReviewStatus, ReviewQueue
from collector.application.read_model.errors import AmbiguousProfileError, CollectionRoundNotFoundError, OpportunityNotFoundError, ProfileNotFoundError
from collector.application.read_model.filters import OpportunityFilters, OpportunitySort, ProfileScope, SortDirection, SortField, TimeRange
from collector.application.read_model.pagination import Pagination
from collector.application.read_model.service import DashboardQueries
from collector.infra.database.read_model_store import SqlAlchemyReadModelStore
from collector.infra.database.session import create_session_factory
from .mapping import to_page, to_response
from .schemas import (CollectionRoundDetailResponse, CollectionRoundListItemResponse, DashboardReviewQueueItemResponse,
    DashboardSummaryResponse, DocumentEvidenceResponse, ErrorResponse, HealthResponse, OpportunityDetailResponse,
    OpportunityDocumentResponse, OpportunityListItemResponse, PageResponse, TimelineItemResponse)
from .settings import ApiSettings

log = logging.getLogger(__name__)
ERROR_RESPONSES = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}


def _scope(profile_id, profile_code): return ProfileScope(profile_id=profile_id, profile_code=profile_code)
def _range(start, end): return TimeRange(from_datetime=start, to_datetime=end)
def _error(status, code, message, details=None):
    body = {"code": code, "message": message}
    if details is not None: body["details"] = details
    return JSONResponse(content={"error": body}, status_code=status)


def create_app(*, queries=None, session_factory=None, settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_environment()
    if queries is None:
        if session_factory is None and not settings.database_url:
            raise RuntimeError("DATABASE_URL não configurada")
        session_factory = session_factory or create_session_factory(settings.database_url)
        queries = DashboardQueries(SqlAlchemyReadModelStore(session_factory))
    app = FastAPI(title="Collector Read API", version="1.0.0")
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                           allow_methods=["GET"], allow_headers=[settings.request_id_header])
    app.state.dashboard_queries = queries
    app.state.session_factory = session_factory

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get(settings.request_id_header, "")
        valid = supplied and len(supplied) <= 128 and all(c.isalnum() or c in "._:-" for c in supplied)
        request_id = supplied if valid else str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            log.error("unhandled HTTP error type=%s", type(exc).__name__)
            response = _error(500, "INTERNAL_ERROR", "Erro interno.")
        response.headers[settings.request_id_header] = request_id
        log.info("http request_id=%s method=%s path=%s status=%s duration_ms=%.2f", request_id,
                 request.method, request.url.path, response.status_code, (perf_counter() - started) * 1000)
        return response

    @app.exception_handler(RequestValidationError)
    def request_validation(_request, exc):
        details = [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "Parâmetros inválidos.", details)

    @app.exception_handler(ValueError)
    def value_validation(_request, exc):
        return _error(422, "VALIDATION_ERROR", "Parâmetros inválidos.", [{"field": "query", "message": str(exc)}])

    @app.exception_handler(OpportunityNotFoundError)
    def opportunity_not_found(_request, _exc): return _error(404, "OPPORTUNITY_NOT_FOUND", "Oportunidade não encontrada.")
    @app.exception_handler(CollectionRoundNotFoundError)
    def round_not_found(_request, _exc): return _error(404, "COLLECTION_ROUND_NOT_FOUND", "Rodada não encontrada.")
    @app.exception_handler(ProfileNotFoundError)
    def profile_not_found(_request, _exc): return _error(404, "PROFILE_NOT_FOUND", "Perfil não encontrado.")
    @app.exception_handler(AmbiguousProfileError)
    def ambiguous(_request, _exc): return _error(409, "AMBIGUOUS_PROFILE", "Perfil ambíguo; informe profile_id.")
    @app.exception_handler(Exception)
    def internal(_request, exc):
        log.error("unhandled HTTP error type=%s", type(exc).__name__)
        return _error(500, "INTERNAL_ERROR", "Erro interno.")

    @app.get("/health", response_model=HealthResponse)
    def health(): return HealthResponse(status="ok")

    @app.get("/ready", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
    def ready():
        try:
            if app.state.session_factory is None: raise RuntimeError("readiness dependency unavailable")
            with app.state.session_factory() as session: session.execute(text("SELECT 1"))
        except Exception: return _error(503, "NOT_READY", "Aplicação indisponível.")
        return HealthResponse(status="ready")

    @app.get("/api/v1/dashboard/summary", response_model=DashboardSummaryResponse, responses=ERROR_RESPONSES)
    def summary(profile_id: UUID | None = None, profile_code: str | None = None,
                from_datetime: datetime | None = None, to_datetime: datetime | None = None):
        dto = queries.dashboard_summary(_scope(profile_id, profile_code), _range(from_datetime, to_datetime))
        return to_response(dto, DashboardSummaryResponse)

    @app.get("/api/v1/opportunities", response_model=PageResponse[OpportunityListItemResponse], responses=ERROR_RESPONSES)
    def opportunities(profile_id: UUID | None = None, profile_code: str | None = None,
                      page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                      sort: SortField = SortField.LATEST_CAPTURE_AT, direction: SortDirection = SortDirection.DESC,
                      operational_state: str | None = None, human_review_status: HumanReviewStatus | None = None,
                      human_decision: HumanReviewDecision | None = None, source: str | None = None, uf: str | None = None,
                      municipality: str | None = None, modality: str | None = None,
                      publication_from: datetime | None = None, publication_to: datetime | None = None,
                      proposal_deadline_from: datetime | None = None, proposal_deadline_to: datetime | None = None,
                      captured_from: datetime | None = None, captured_to: datetime | None = None,
                      has_documents: bool | None = None, has_text: bool | None = None,
                      has_document_screening: bool | None = None, search: str | None = None,
                      review_queue: ReviewQueue | None = None):
        filters = OpportunityFilters(operational_state=operational_state, human_review_status=human_review_status,
            human_decision=human_decision, source=source, uf=uf, municipality=municipality, modality=modality,
            publication=_range(publication_from, publication_to), proposal_deadline=_range(proposal_deadline_from, proposal_deadline_to),
            captured=_range(captured_from, captured_to), has_documents=has_documents, has_text=has_text,
            has_document_screening=has_document_screening, search=search, review_queue=review_queue)
        dto = queries.list_opportunities(_scope(profile_id, profile_code), filters, Pagination(page, page_size), OpportunitySort(sort, direction))
        return to_page(dto, OpportunityListItemResponse)

    @app.get("/api/v1/opportunities/by-source", response_model=OpportunityDetailResponse, responses=ERROR_RESPONSES)
    def by_source(source: str, official_id: str, profile_id: UUID | None = None, profile_code: str | None = None):
        return to_response(queries.get_opportunity_by_source_identity(source, official_id, _scope(profile_id, profile_code)), OpportunityDetailResponse)

    @app.get("/api/v1/opportunities/{process_id}", response_model=OpportunityDetailResponse, responses=ERROR_RESPONSES)
    def detail(process_id: UUID, profile_id: UUID | None = None, profile_code: str | None = None):
        return to_response(queries.get_opportunity(process_id, _scope(profile_id, profile_code)), OpportunityDetailResponse)

    @app.get("/api/v1/opportunities/{process_id}/documents", response_model=PageResponse[OpportunityDocumentResponse], responses=ERROR_RESPONSES)
    def documents(process_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        return to_page(queries.documents(process_id, Pagination(page, page_size)), OpportunityDocumentResponse)

    @app.get("/api/v1/opportunities/{process_id}/document-evidence", response_model=PageResponse[DocumentEvidenceResponse], responses=ERROR_RESPONSES)
    def evidence(process_id: UUID, profile_id: UUID | None = None, profile_code: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        return to_page(queries.document_evidence(process_id, _scope(profile_id, profile_code), Pagination(page, page_size)), DocumentEvidenceResponse)

    @app.get("/api/v1/opportunities/{process_id}/timeline", response_model=PageResponse[TimelineItemResponse], responses=ERROR_RESPONSES)
    def timeline(process_id: UUID, profile_id: UUID | None = None, profile_code: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        return to_page(queries.timeline(process_id, _scope(profile_id, profile_code), Pagination(page, page_size)), TimelineItemResponse)

    @app.get("/api/v1/review-queue", response_model=PageResponse[DashboardReviewQueueItemResponse], responses=ERROR_RESPONSES)
    def review_queue(profile_id: UUID | None = None, profile_code: str | None = None,
                     queue: ReviewQueue = ReviewQueue.NEEDS_REVIEW, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                     sort: SortField = SortField.LATEST_CAPTURE_AT, direction: SortDirection = SortDirection.DESC):
        dto = queries.review_queue(_scope(profile_id, profile_code), queue, pagination=Pagination(page, page_size), sort=OpportunitySort(sort, direction))
        return to_page(dto, DashboardReviewQueueItemResponse)

    @app.get("/api/v1/collection-rounds", response_model=PageResponse[CollectionRoundListItemResponse], responses=ERROR_RESPONSES)
    def rounds(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), source: str | None = None,
               from_datetime: datetime | None = None, to_datetime: datetime | None = None):
        return to_page(queries.collection_rounds(_range(from_datetime, to_datetime), Pagination(page, page_size), source), CollectionRoundListItemResponse)

    @app.get("/api/v1/collection-rounds/{round_id}", response_model=CollectionRoundDetailResponse, responses=ERROR_RESPONSES)
    def round_detail(round_id: UUID): return to_response(queries.collection_round_detail(round_id), CollectionRoundDetailResponse)
    return app
