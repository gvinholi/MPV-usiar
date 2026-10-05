"""Motor documental determinístico. Não altera a triagem inicial."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from collector.application.document_screening.coverage import measure_coverage
from collector.application.document_screening.decide import decide_document
from collector.application.document_screening.fingerprint import document_set_fingerprint
from collector.application.document_screening.matching import collect_page_evidence
from collector.application.document_screening.policy import DocumentScreeningPolicy
from collector.application.document_screening.reasons import DocumentReasonCode
from collector.application.document_screening.results import (
    DOCUMENT_ENGINE_VERSION,
    DocumentScreeningCorpus,
    DocumentScreeningEvaluation,
    DocumentScreeningEvidence,
)
from collector.application.screening.profile import ScreeningProfile
from collector.domain.timestamps import utc_now

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]

_REASON_TEXT = {
    DocumentReasonCode.DOCUMENT_RELEVANT_MAINTENANCE: (
        "Os documentos mostram manutenção relevante em contexto de climatização."
    ),
    DocumentReasonCode.DOCUMENT_RELEVANT_SANITIZATION: (
        "Os documentos mostram higienização relevante em contexto de climatização."
    ),
    DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_INSTALLATION: (
        "Há manutenção ou higienização relevante junto de instalação; "
        "escopo misto exige avaliação humana."
    ),
    DocumentReasonCode.DOCUMENT_MIXED_MAINTENANCE_SUPPLY: (
        "Há manutenção ou higienização relevante junto de aquisição ou peças; "
        "escopo misto exige avaliação humana."
    ),
    DocumentReasonCode.DOCUMENT_ISOLATED_INSTALLATION: (
        "Os documentos mostram instalação isolada em contexto de climatização, "
        "sem manutenção ou higienização relevante."
    ),
    DocumentReasonCode.DOCUMENT_ISOLATED_EQUIPMENT_PURCHASE: (
        "Os documentos mostram aquisição isolada de equipamento de climatização, "
        "sem manutenção ou higienização relevante."
    ),
    DocumentReasonCode.DOCUMENT_ISOLATED_PARTS_SUPPLY: (
        "Os documentos mostram fornecimento isolado de peças de climatização, "
        "sem manutenção ou higienização relevante."
    ),
    DocumentReasonCode.DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT: (
        "Há contexto de climatização, mas o serviço não é suficientemente "
        "claro ou próximo para decisão segura."
    ),
    DocumentReasonCode.DOCUMENT_NO_DECISIVE_EVIDENCE: (
        "Os documentos foram processados e não há evidência decisiva de "
        "aderência. Ausência de termo no texto extraído não prova irrelevância."
    ),
    DocumentReasonCode.DOCUMENT_INCOMPLETE_COVERAGE: (
        "Há sinal de exclusão isolada, mas a cobertura documental é incompleta "
        "(falha, formato não suportado ou fonte provavelmente escaneada)."
    ),
    DocumentReasonCode.DOCUMENT_NO_TEXT: (
        "Não há texto extraído para avaliar. Cobertura incompleta; "
        "ausência de texto não prova irrelevância."
    ),
}


class DocumentScreeningEngine:
    version = DOCUMENT_ENGINE_VERSION

    def __init__(
        self,
        *,
        policy: DocumentScreeningPolicy | None = None,
        clock: Clock = utc_now,
        new_id: IdFactory = uuid4,
    ) -> None:
        self._policy = policy or DocumentScreeningPolicy()
        self._clock = clock
        self._new_id = new_id

    def evaluate(
        self,
        profile: ScreeningProfile,
        corpus: DocumentScreeningCorpus,
        *,
        profile_id: UUID | None = None,
    ) -> DocumentScreeningEvaluation:
        coverage = measure_coverage(corpus.pages, corpus.sources)
        evidence: list[DocumentScreeningEvidence] = []
        for page in corpus.pages:
            evidence.extend(collect_page_evidence(page, profile, self._policy))
        state, reason = decide_document(evidence, coverage, self._policy)
        member_shas = tuple(source.source_sha256 for source in corpus.sources)
        if not member_shas:
            member_shas = tuple(sorted({page.source_sha256 for page in corpus.pages}))
        return DocumentScreeningEvaluation(
            id=self._new_id(),
            process_id=corpus.process_id,
            profile_code=profile.code,
            profile_version=profile.version,
            profile_id=profile_id or profile.id,
            state=state,
            reason_code=reason,
            reason_text=_reason_text(reason, evidence),
            evaluated_at=self._clock(),
            engine_version=self.version,
            document_set_fingerprint=document_set_fingerprint(
                profile, self.version, member_shas
            ),
            coverage=coverage,
            evidence=tuple(evidence),
        )


def _reason_text(
    reason: DocumentReasonCode, evidence: Sequence[DocumentScreeningEvidence]
) -> str:
    base = _REASON_TEXT[reason]
    if not evidence:
        return base
    terms = ", ".join(sorted({item.configured_term for item in evidence if not item.negated}))
    if not terms:
        return base
    return f"{base} Termos: {terms}."
