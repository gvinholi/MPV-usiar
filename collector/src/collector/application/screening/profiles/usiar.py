"""Configuração USIAR v1. Termos ficam aqui, não no motor."""

from uuid import UUID, uuid5

from collector.application.screening.profile import ScreeningProfile

USIAR_NAMESPACE = UUID("6b1d2c3a-4e5f-6789-abcd-0123456789ab")
USIAR_V1_ID = uuid5(USIAR_NAMESPACE, "USIAR/v1")
USIAR_V2_ID = uuid5(USIAR_NAMESPACE, "USIAR/v2")

CONTEXT_TERMS = (
    "ar condicionado",
    "ar-condicionado",
    "climatização",
    "sistema de climatização",
    "hvac",
    "aparelhos de climatização",
    "equipamentos de climatização",
    "condicionador de ar",
    "condicionadores de ar",
    "split",
    "chiller",
    "chillers",
    "vrf",
    "vrv",
    "fan coil",
    "fancoil",
    "central de ar",
    "sistema de refrigeração",
    "aparelhos de ar condicionado",
    "equipamentos de ar condicionado",
)

MAINTENANCE_TERMS = (
    "manutenção preventiva",
    "manutenção corretiva",
    "manutenção preventiva e corretiva",
    "manutenção",
    "serviços de manutenção",
    "serviços continuados de manutenção",
)

SANITIZATION_TERMS = (
    "higienização",
    "higienização de aparelhos",
    "limpeza técnica",
    "limpeza de aparelhos",
)

INSTALLATION_TERMS = (
    "instalação",
    "instalações",
    "instalação de aparelhos",
)

PURCHASE_TERMS = (
    "aquisição",
    "compra",
    "fornecimento",
    "fornecimento de equipamentos",
    "aquisição de aparelhos",
)

PARTS_TERMS = (
    "peças",
    "componentes",
    "peças de reposição",
    "fornecimento de peças",
    "aquisição de peças",
    "fornecimento de componentes",
)


def usiar_v1() -> ScreeningProfile:
    return ScreeningProfile(
        id=USIAR_V1_ID,
        code="USIAR",
        name="Usinaria — manutenção e higienização de climatização",
        version="v1",
        context_terms=CONTEXT_TERMS,
        maintenance_terms=MAINTENANCE_TERMS,
        sanitization_terms=SANITIZATION_TERMS,
        installation_terms=INSTALLATION_TERMS,
        purchase_terms=PURCHASE_TERMS,
        parts_terms=PARTS_TERMS,
        active=True,
    )


V2_CONTEXT_TERMS = (
    "ar condicionado",
    "ar-condicionado",
    "climatização",
    "sistema de climatização",
    "sistemas de climatização",
    "equipamento de climatização",
    "equipamentos de climatização",
    "condicionador de ar",
    "condicionadores de ar",
    "aparelho de ar condicionado",
    "aparelhos de ar condicionado",
    "equipamento de ar condicionado",
    "equipamentos de ar condicionado",
    "aparelho split",
    "aparelhos split",
    "sistema split",
    "sistemas split",
    "multi split",
    "multi-split",
    "multisplit",
    "vrf",
    "vrv",
    "evaporadora",
    "evaporadoras",
    "condensadora",
    "condensadoras",
    "chiller",
    "chillers",
    "sistema central de climatização",
    "sistemas centrais de climatização",
    "ar condicionado central",
    "ar-condicionado central",
    "central de ar",
    "sistema hvac",
    "sistemas hvac",
    "duto de ar condicionado",
    "dutos de ar condicionado",
    "duto de climatização",
    "dutos de climatização",
    "pmoc",
    "plano de manutenção operação e controle",
)

V2_AMBIGUOUS_CONTEXT_TERMS = (
    "hvac",
    "refrigeração",
    "sistema de refrigeração",
    "sistemas de refrigeração",
    "equipamento de refrigeração",
    "equipamentos de refrigeração",
)

V2_EXCLUDED_CONTEXT_TERMS = (
    "ar condicionado veicular",
    "ar-condicionado veicular",
    "climatização veicular",
)

V2_MAINTENANCE_TERMS = (
    "manutenção",
    "manutenção preventiva",
    "manutenção corretiva",
    "manutenção preventiva e corretiva",
    "manutenção corretiva e preventiva",
    "serviço de manutenção",
    "serviços de manutenção",
    "pmoc",
    "plano de manutenção operação e controle",
)

V2_SANITIZATION_TERMS = (
    "higienização",
    "limpeza",
    "desinfecção",
    "limpeza e higienização",
    "limpeza e desinfecção",
    "limpeza de duto",
    "limpeza de dutos",
)

V2_INSTALLATION_TERMS = (
    "instalação",
    "instalações",
    "instalação de aparelho",
    "instalação de aparelhos",
    "desinstalação",
    "reinstalação",
)

V2_PURCHASE_TERMS = (
    "aquisição",
    "compra",
    "fornecimento",
    "fornecimento de equipamento",
    "fornecimento de equipamentos",
    "aquisição de aparelho",
    "aquisição de aparelhos",
)

V2_PARTS_TERMS = (
    "peça",
    "peças",
    "componente",
    "componentes",
    "peça de reposição",
    "peças de reposição",
    "fornecimento de peças",
    "fornecimento de componentes",
)


def usiar_v2() -> ScreeningProfile:
    return ScreeningProfile(
        id=USIAR_V2_ID,
        code="USIAR",
        name="UsiAr — triagem contextual de climatização",
        version="v2",
        context_terms=V2_CONTEXT_TERMS,
        ambiguous_context_terms=V2_AMBIGUOUS_CONTEXT_TERMS,
        excluded_context_terms=V2_EXCLUDED_CONTEXT_TERMS,
        maintenance_terms=V2_MAINTENANCE_TERMS,
        sanitization_terms=V2_SANITIZATION_TERMS,
        installation_terms=V2_INSTALLATION_TERMS,
        purchase_terms=V2_PURCHASE_TERMS,
        parts_terms=V2_PARTS_TERMS,
        association_window_tokens=1,
        active=True,
    )
