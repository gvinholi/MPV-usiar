# Automação de Licitações — Usinaria

Sistema de coleta e triagem auditável de oportunidades de licitação. O piloto inicial usa o PNCP como fonte principal e o perfil configurável USIAR.

O contrato oficial do projeto está em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Não altere arquitetura, tecnologias ou regras de negócio sem aprovação.

## Objetivo do piloto

Coletar oportunidades, aplicar triagem configurável e registrar de forma auditável o que foi coletado, unificado, candidato, selecionado, descartado (com motivo), pendente e quais documentos foram ou não acessados — em qual rodada e por quais fontes.

Duração prevista: 15 dias, 3 rodadas diárias.

## O que este sistema não faz

O piloto **não** automatiza:

* participação em pregões;
* envio de propostas;
* lances;
* comunicação automática com clientes;
* decisão automática por valor, distância ou prazo;
* classificação por IA.

## Estrutura

```text
docs/ARCHITECTURE.md    Contrato arquitetural
collector/              Coletor Python (domínio, aplicação, infra)
```

O dashboard Next.js e a infraestrutura Google Cloud entram em commits posteriores.

## Coletor

Requer Python 3.13+.

```powershell
cd collector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

## Camadas do coletor

* `collector.domain` — conceitos e regras de negócio; sem I/O e sem fornecedor.
* `collector.application` — orquestração de casos de uso; depende do domínio, não de adaptadores concretos.
* `collector.infra` — adaptadores (PNCP, armazenamento, banco). Vazio neste estágio.

## Segurança

Credenciais não devem ser commitadas. Use `.env` apenas em desenvolvimento local. Em produção, use Secret Manager.
