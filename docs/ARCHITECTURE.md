# Contrato arquitetural — Automação de Licitações (Usinaria)

Este documento é o contrato oficial do projeto. Não altere a arquitetura, tecnologias ou regras de negócio sem antes explicar o motivo e solicitar aprovação.

O desenvolvimento será feito de forma incremental, através de commits Git independentes. Cada commit deve possuir escopo pequeno, testável e claramente definido.

---

## 1. Objetivo do projeto

Construir um sistema automatizado capaz de coletar oportunidades de licitação, inicialmente utilizando o PNCP como fonte principal, aplicar regras configuráveis de triagem para o perfil USIAR e registrar de maneira auditável:

* o que foi coletado;
* o que foi considerado processo único;
* o que foi considerado candidato;
* o que foi selecionado;
* o que foi descartado;
* o motivo do descarte;
* o que ficou pendente;
* quais documentos foram encontrados;
* quais documentos não puderam ser acessados;
* em qual rodada cada informação foi detectada;
* quais fontes contribuíram para a descoberta.

O primeiro piloto terá duração de 15 dias, com 3 rodadas diárias.

O objetivo do piloto NÃO é automatizar participação em pregões, envio de propostas, lances ou comunicação automática com clientes.

---

## 2. Perfil inicial

O primeiro perfil será:

USIAR

Regras atuais de negócio:

### Interesse principal

* manutenção preventiva;
* manutenção corretiva;
* higienização.

Não existe restrição inicial de equipamento.

### Avaliação

Manutenção acompanhada de instalação deve entrar para avaliação humana.

### Não selecionar automaticamente

* instalação isolada;
* compra de aparelhos;
* fornecimento isolado de peças.

### NÃO usar como critério automático de descarte

* valor;
* distância;
* modalidade;
* exigência de equipe;
* capacidade técnica;
* prazo.

Esses dados devem ser apresentados para decisão humana.

As regras devem ser configuráveis e não podem ficar espalhadas pelo código.

---

## 3. Arquitetura

Arquitetura inicial:

```text
Google Cloud
|
+-- Cloud Scheduler
|
+-- Cloud Run Jobs
|       |
|       +-- Python Collector
|
+-- Cloud Storage
|
+-- Secret Manager
|
+-- IAM
|
+-- PostgreSQL
|
+-- Dashboard Next.js
```

A definição final entre Cloud SQL PostgreSQL e uma solução PostgreSQL gerenciada externa ainda deverá ser confirmada antes da implantação definitiva.

Não acople o código do domínio a um fornecedor de banco.

---

## 4. Tecnologias

### Coletor

Python 3.13+

Preferências:

* httpx;
* Pydantic;
* pytest;
* tenacity quando necessário;
* logging da biblioteca padrão;
* openpyxl para exportações Excel posteriormente.

### Frontend

Next.js
TypeScript
Tailwind CSS

### Banco

PostgreSQL

### Infraestrutura

Google Cloud:

* Cloud Run Jobs;
* Cloud Scheduler;
* Cloud Storage;
* Secret Manager;
* IAM.

### Versionamento

Git + GitHub.

---

## 5. PNCP

O PNCP é a fonte principal de coleta.

O sistema deverá trabalhar com a API oficial do PNCP e não depender de scraping da interface web quando houver endpoint oficial disponível.

O coletor deverá ser preparado para:

* consulta por período;
* modalidade;
* estado/localização quando suportado;
* paginação completa;
* retry;
* backoff;
* retomada;
* controle de páginas processadas;
* registro de falhas;
* deduplicação;
* revisita de publicações anteriores.

Não assumir que uma falha de consulta significa zero oportunidades.

Uma rodada parcial deve ser explicitamente marcada como parcial/falha.

---

## 6. Rodadas

Cada execução do coletor deve possuir um identificador único.

Exemplo conceitual:

```text
2026-09-25-01
2026-09-25-02
2026-09-25-03
```

Cada rodada deverá permitir registrar:

* início;
* fim;
* status;
* fonte;
* período consultado;
* páginas esperadas;
* páginas processadas;
* páginas com erro;
* quantidade de registros obtidos;
* quantidade de processos únicos;
* quantidade de candidatos;
* quantidade de descartados;
* quantidade de pendentes;
* quantidade de documentos encontrados;
* erros;
* informações de execução.

---

## 7. Raw data e evidências

As respostas brutas das fontes devem poder ser armazenadas para auditoria.

Documentos, editais, anexos e versões também deverão poder ser armazenados.

O banco deve guardar metadados e referências aos arquivos.

Não colocar grandes arquivos binários diretamente no PostgreSQL.

Arquivos devem ser tratados como objetos de armazenamento.

---

## 8. Processo único

Não usar o título ou o número visível do edital como identificador principal.

Usar os identificadores oficiais fornecidos pela fonte, especialmente os identificadores do PNCP.

O modelo deve permitir:

* deduplicação;
* atualização;
* múltiplas fontes;
* múltiplas detecções;
* múltiplos documentos;
* versões.

Possíveis duplicidades devem poder ser marcadas para conferência humana.

---

## 9. Triagem

O sistema deve separar claramente:

```text
PUBLICAÇÃO BRUTA
|
v
PROCESSO ÚNICO
|
v
CANDIDATO
|
+----> DESCARTADO + MOTIVO
|
+----> PENDENTE + MOTIVO
|
v
SELECIONADO
|
v
CONFIRMADO COM EVIDÊNCIA
```

Uma licitação não deve ser considerada confirmada apenas porque uma palavra-chave apareceu no título.

Sempre que a classificação exigir confirmação documental, registrar a evidência correspondente.

---

## 10. Perfis de busca

Não implementar as palavras da USIAR diretamente em condicionais espalhadas pelo sistema.

Criar uma estrutura de perfil configurável.

Exemplo conceitual:

```text
USIAR
|
+-- termos de inclusão
+-- termos condicionais
+-- termos de exclusão
+-- regras
+-- critérios de confirmação
```

O sistema deverá futuramente permitir outros perfis sem duplicação do código.

---

## 11. Fontes

### Principal

PNCP.

### Referência/benchmark

RHS, respeitando acesso, contrato e condições de uso.

### Possíveis fontes complementares

* BLL;
* BNC;
* Licitações-e;
* diários;
* portais oficiais de órgãos.

Não implementar integrações com fontes complementares sem que o acesso e as condições de uso estejam definidos.

Nenhuma fonte complementar deve ser necessária para o funcionamento básico do coletor PNCP.

---

## 12. Documentos

Uma contratação pode possuir múltiplos documentos.

Não criar somente um campo "url_edital" no modelo definitivo.

Criar uma relação de documentos.

Exemplos:

* edital;
* termo de referência;
* anexos;
* planilhas;
* documentos complementares.

Guardar:

* título;
* tipo;
* URL;
* identificador da fonte;
* data;
* versão quando disponível;
* localização no armazenamento quando aplicável.

---

## 13. Planilha

A planilha é uma interface operacional/saída, não a fonte primária de verdade do sistema.

O banco deve ser a fonte de verdade.

O sistema deverá posteriormente permitir exportar os processos selecionados para a planilha mestre escolhida pela Usinaria.

Preservar, quando aplicável:

* estrutura;
* fórmulas;
* hyperlinks;
* histórico;
* campos de revisão humana.

A integração definitiva com Google Sheets ou Excel ainda deve ser confirmada.

---

## 14. Dashboard

O dashboard deverá permitir visualizar pelo menos:

* processos;
* candidatos;
* selecionados;
* descartados;
* pendentes;
* motivo do descarte;
* evidências;
* documentos;
* rodada de detecção;
* fonte;
* data de publicação;
* data de detecção;
* situação da coleta.

Deve existir diferenciação visual entre:

* execução concluída;
* execução parcial;
* execução com falha.

Nunca apresentar uma rodada que falhou como "zero oportunidades".

---

## 15. IA

NÃO implementar IA para análise semântica de editais no MVP inicial.

A integração com OpenAI será considerada em etapa posterior.

O sistema deve, entretanto, ser projetado para que uma etapa posterior de análise de documentos possa ser adicionada sem reescrever o coletor.

---

## 16. Não fazer no MVP

Não implementar:

* automação de lances;
* participação automática em pregões;
* envio automático de propostas;
* envio automático para clientes;
* decisão automática baseada em valor;
* decisão automática baseada em distância;
* decisão automática baseada em prazo;
* dependência da RHS;
* IA obrigatória para classificação.

---

## 17. Testabilidade

Todo componente importante deverá possuir testes.

Priorizar testes para:

* paginação;
* retry;
* retomada;
* deduplicação;
* normalização;
* regras de triagem;
* classificação;
* documentos;
* falhas;
* rodadas.

O coletor não deve depender da API real do PNCP para executar os testes unitários.

Utilizar mocks/fixtures.

---

## 18. Observabilidade

Toda execução importante deve gerar logs estruturados.

Registrar:

* rodada;
* fonte;
* etapa;
* status;
* erro;
* quantidade processada;
* tempo.

Não registrar secrets, tokens ou credenciais.

---

## 19. Segurança

Credenciais nunca devem ser commitadas.

Usar:

`.env` localmente durante desenvolvimento.

Secret Manager em produção.

Princípio do menor privilégio para contas de serviço.

Não utilizar credenciais pessoais.

---

## 20. Estratégia de commits

O desenvolvimento seguirá aproximadamente:

1. Fundação e contrato arquitetural
2. Infraestrutura inicial
3. Modelo de dados
4. Cliente PNCP
5. Paginação e retomada
6. Armazenamento RAW
7. Perfil USIAR
8. Normalização e deduplicação
9. Motor de triagem
10. Estados e decisões
11. Documentos PNCP
12. Evidências
13. Rodadas
14. Logs e cobertura
15. Dashboard
16. Filtros/revisão
17. Exportação
18. Automação 3x/dia
19. Monitoramento
20. Benchmark RHS
21. Relatório do piloto

Não implementar vários commits de uma vez.

Antes de cada commit:

1. explicar objetivo;
2. listar arquivos a alterar;
3. implementar;
4. executar testes;
5. verificar lint/typecheck quando aplicável;
6. mostrar resumo;
7. sugerir mensagem de commit.

Ao terminar cada etapa, parar e aguardar aprovação.

---

## 21. Regra principal para o Cursor

Não invente requisitos.

Não simplifique regras de negócio importantes.

Não introduza uma nova biblioteca ou serviço sem justificar.

Não misture infraestrutura, domínio e interface.

Não avance automaticamente para o próximo commit.

O objetivo é construir um sistema pequeno, auditável, testável e expansível.

---

## 22. Modelo de domínio da coleta

Decisões do modelo de domínio. Não substituem as seções anteriores.

* **Fonte:** `Enum` com `PNCP` e `RHS`. É suficiente neste estágio: o conjunto de fontes é fechado e novas fontes só entram como membros quando o acesso for aprovado. Não usar strings soltas como `"pncp"`. Não há membro genérico "outras".
* **Identidade do processo:** UUID interno do sistema e uma ou mais identidades oficiais (`fonte` + identificador oficial da fonte). Título e número visível do edital não são identidade. O mesmo UUID interno pode reunir identidades de fontes distintas; o algoritmo de deduplicação não faz parte deste modelo.
* **Timestamps:** timezone-aware. O domínio não assume `America/Sao_Paulo`. Conversão para exibição fica nas bordas.
* **Rodada:** `SUCCESS` com zero registros coletados é distinto de `FAILED` e de `PARTIAL`. O status declara o desfecho da execução; as métricas não são inferidas a partir do status.
* **Métricas:** representação de contadores; sem cálculo automático.
* **Triagem:** estados `RAW`, `UNIQUE`, `CANDIDATE`, `SELECTED`, `PENDING`, `DISCARDED`, `CONFIRMED`. Motivo de descarte ou pendência é um campo opcional. As regras USIAR não estão neste modelo.
