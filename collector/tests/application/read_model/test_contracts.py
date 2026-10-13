import ast
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from collector.application.read_model import (
    DashboardQueries, OpportunityFilters, OpportunityNotFoundError, OpportunitySort,
    Page, Pagination, ProfileScope, SortDirection, SortField, TimeRange,
)
from collector.application.read_model.models import description_preview


@pytest.mark.parametrize('kwargs', [{'page': 0}, {'page': -1}, {'page': True}, {'page': 1.5},
    {'page_size': 0}, {'page_size': 101}, {'page_size': False}, {'page_size': '25'}])
def test_invalid_pagination(kwargs):
    with pytest.raises(ValueError):
        Pagination(**kwargs)


def test_pagination_and_immutable_dto():
    assert Pagination().page_size == 25
    assert Pagination(2, 100).offset == 100
    assert Page((), 4, 25, 51).total_pages == 3
    assert Page((), 1, 25, 0).total_pages == 0
    with pytest.raises(FrozenInstanceError):
        Pagination().page = 4


@pytest.mark.parametrize('kwargs', [dict(operational_state='SELECTED'), dict(human_decision='CANDIDATE'),
    dict(human_review_status='UNKNOWN'), dict(source='FAKE'), dict(uf='SAO'), dict(search=''),
    dict(search='x'*301), dict(has_text='true'), dict(has_documents=1), dict(captured='today'),
    dict(review_queue='UNKNOWN'), dict(include_operational_discarded=1),
    dict(operational_state=()), dict(operational_state=('CANDIDATE', 'SELECTED'))])
def test_invalid_filters(kwargs):
    with pytest.raises(ValueError):
        OpportunityFilters(**kwargs)


def test_allowed_filters():
    assert OpportunityFilters(uf='sp', search='100%').uf == 'SP'
    assert OpportunityFilters(human_decision='SELECTED').human_decision.value == 'SELECTED'
    states = OpportunityFilters(operational_state=('CANDIDATE', 'PENDING', 'CANDIDATE'))
    assert states.operational_state == ('CANDIDATE', 'PENDING')


@pytest.mark.parametrize('field', list(SortField))
@pytest.mark.parametrize('direction', list(SortDirection))
def test_sort_allowlist(field, direction):
    assert OpportunitySort(field.value, direction.value).field == field


@pytest.mark.parametrize('field,direction', [('id; DROP TABLE processes', 'DESC'), ('description','ASC'), ('estimated_value', 'DESC; DELETE')])
def test_invalid_sort(field, direction):
    with pytest.raises(ValueError):
        OpportunitySort(field,direction)


def test_preview_null_unicode_and_limit():
    original = 'á'*400
    assert description_preview(original) == 'á'*300
    assert len(original) == 400
    assert description_preview(None) is None
    assert description_preview('') == ''


def test_timezone_and_range():
    now = datetime.now(UTC)
    local = now.astimezone(timezone(timedelta(hours=-3)))
    assert TimeRange(local, now + timedelta(days=1)).from_datetime == now
    for period in ((datetime.now(), None), (now, now), (now, now-timedelta(seconds=1))):
        with pytest.raises(ValueError):
            TimeRange(*period)


def test_profile_scope():
    assert ProfileScope(profile_code='CUSTOM').profile_code == 'CUSTOM'
    for kwargs in ({}, {'profile_code': ''}, {'profile_id': 'id'}, {'profile_id': uuid4(), 'profile_code': 'USIAR'}):
        with pytest.raises(ValueError):
            ProfileScope(**kwargs)


def test_service_lookup_and_explicit_not_found():
    scope = ProfileScope(profile_id=uuid4())
    class Fake:
        def get_opportunity_by_source_identity(self, source, official_id, requested_scope):
            assert (source, official_id, requested_scope) == ('PNCP','known',scope)
            return 'detail'
        def get_opportunity(self, process_id, scope):
            raise OpportunityNotFoundError(str(process_id))
    service = DashboardQueries(Fake())
    assert service.get_opportunity_by_source_identity('PNCP','known',scope) == 'detail'
    with pytest.raises(OpportunityNotFoundError):
        service.get_opportunity(uuid4(),scope)
    with pytest.raises(ValueError):
        service.get_opportunity_by_source_identity('PNCP',' ',scope)


def test_read_only_architecture():
    import collector.application.read_model as module
    forbidden = ('collector.infra', 'sqlalchemy', 'httpx', 'fastapi', 'collector.application.collection',
                 'collector.application.acquisition', 'collector.application.extraction', 'collector.application.human_review.service')
    for path in Path(module.__file__).parent.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))):
            imports = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            assert not any(name.startswith(forbidden) for name in imports)
