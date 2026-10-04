"""Configuração USIAR v1. Termos ficam aqui, não no motor."""

from uuid import UUID, uuid5

from collector.application.screening.profile import ScreeningProfile

USIAR_NAMESPACE = UUID("6b1d2c3a-4e5f-6789-abcd-0123456789ab")
USIAR_V1_ID = uuid5(USIAR_NAMESPACE, "USIAR/v1")

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
