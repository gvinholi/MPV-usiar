"""Identidade oficial de documento PNCP observada no contrato real.

sequencialDocumento é único na contratação, não globalmente.
A chave estável é cnpj + ano + sequencial da compra + sequencialDocumento.
"""


def build_pncp_document_official_id(
    *,
    cnpj: str,
    year: int,
    sequential: int,
    document_sequence: int,
) -> str:
    digits = "".join(character for character in cnpj if character.isdigit())
    if len(digits) != 14:
        raise ValueError("cnpj deve ter 14 dígitos")
    if year < 1 or sequential < 1 or document_sequence < 1:
        raise ValueError("identificadores da compra e do documento devem ser >= 1")
    return f"{digits}/{year}/{sequential}/{document_sequence}"
