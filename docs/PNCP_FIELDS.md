# Campos PNCP para a aba UsiAr

Este documento registra somente correspondências comprovadas no contrato oficial e em
amostras reais do PNCP. A fonte técnica é o endpoint público
`GET /api/consulta/v1/contratacoes/publicacao`; as definições semânticas vêm do
[Manual de Integração](https://pncp.gov.br/manual/pt-br/latest/singlehtml/) e o schema
vigente pode ser consultado no
[OpenAPI do PNCP](https://pncp.gov.br/pncp-consulta/v3/api-docs).

| Coluna UsiAr | Campo seguro | Origem | Limitação |
| --- | --- | --- | --- |
| ID RHS | indisponível | — | Não é fornecido pelo PNCP e não é inventado. |
| DATA | `publication_at` | `dataPublicacaoPncp` | Data/hora oficial da publicação. |
| Hr | `publication_at` | `dataPublicacaoPncp` | É a parte de hora do mesmo timestamp; não há campo separado. |
| ORGÃO | `organization_name` | `orgaoEntidade.razaoSocial` | Nullable conforme o payload. |
| CIDADE | `municipality_name` | `unidadeOrgao.municipioNome` | Indica a unidade informada; não comprova o local de execução. |
| TIPO | `modality` | `modalidadeNome` | Modalidade oficial da contratação. |
| SITE | `official_url` | `linkSistemaOrigem` | Só é exposto se for HTTP(S) público e não contiver credenciais/parâmetros sensíveis. |
| N EDITAL | `notice_number` | indisponível no contrato atual | Permanece `null`; `numeroCompra`, `numeroControlePNCP` e `processo` não são substitutos automáticos. |
| TIPO DO SERVIÇO | descrição/triagem existentes | `objetoCompra` + USIAR/v2 | O PNCP não fornece a categoria comercial da UsiAr como campo estruturado; a tela usa estado, motivo e evidências auditáveis sem inventar categoria. |
| VALOR MENSAL | indisponível | — | Não é derivado do valor total. |
| VALOR ESTIMADO | `estimated_value` | `valorTotalEstimado` | Decimal oficial; nullable. |
| OBSERVAÇÃO | indisponível como campo PNCP único | — | Não é fabricada a partir de informações complementares. |

## Evidência controlada

Em 10/10/2025, modalidade 6 e UF SP, a contratação
`02366047000107-1-000066/2025` retornou `numeroCompra="90008"`,
`processo="69/2025"`, `tipoInstrumentoConvocatorioNome="Edital"` e um
`linkSistemaOrigem` público do Compras.gov.br. O payload não continha
`numeroEdital`. O link exige os parâmetros não sensíveis `destino` e `compra`, razão
pela qual queries seguras são preservadas.

Os snapshots são append-only. Uma observação posterior com valor ausente não altera o
valor válido de uma observação histórica. Registros anteriores à migration 0010
continuam compatíveis e recebem `notice_number=null`.
