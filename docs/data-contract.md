# Contrato de dados

O handoff guarda o estado de uma tarefa para outro agente continuar sem ler toda a conversa.

## Estruturas

| Estrutura | Campos |
| --- | --- |
| Thread | `id`, `title`, `objective`, `acceptance_criteria`, `constraints`, `status` (`active`, `blocked` ou `completed`) |
| Checkpoint | `id`, `thread_id`, `schema_version`, `covers_through_event`, `completed`, `in_progress`, `pending`, `decisions`, `failed_approaches`, `interruption_point`, `next_action`, `workspace`, `validations`, `open_questions` |
| Evento | `id`, `thread_id`, `sequence`, `type`, `summary`, `evidence_refs`, `created_at` |
| Artefacto | `id`, `thread_id`, `media_type`, `location`, `sha256` |

- As listas usam texto curto. `decisions` e `failed_approaches` incluem o motivo.
- `workspace` é opcional: identifica o projeto, a versão base e uma referência às alterações locais, se existirem.
- Cada validação indica a verificação, o resultado, o estado testado e a referência à evidência.
- Os tipos de evento são `progress`, `decision`, `validation`, `blocker` e `correction`.

## Regras de retoma

1. O serviço gera IDs, datas e sequências de eventos por thread. A versão inicial do contrato é `1`.
2. Cada checkpoint consolida o estado de trabalho até `covers_through_event`; checkpoints e eventos anteriores são preservados.
3. `resume` devolve o objetivo, os critérios e as restrições atuais, o último checkpoint e os eventos posteriores. Sem checkpoint, devolve os eventos existentes.
4. Correções ao objetivo, critérios ou restrições atualizam a thread e ficam registadas como eventos.
5. Trabalho implementado não implica trabalho validado. Incertezas e bloqueios são explícitos; uma tarefa por terminar tem uma próxima ação ou um bloqueio.
6. Logs, patches e outros conteúdos extensos ficam em artefactos, consultados por referência. O agente confirma que o estado do projeto corresponde ao registado antes de confiar nas validações.

## Exemplo do conteúdo de retoma

```text
Objetivo: rejeitar sessões expiradas sem alterar a API pública.
Critério de conclusão: sessões expiradas são rejeitadas e as válidas continuam a funcionar.
Restrição: usar o ambiente Conda dev.
Concluído: identificada a comparação incorreta de datas.
Em curso: correção guardada em src/auth.py; ainda sem testes.
Decisão: normalizar datas para UTC para evitar comparações incompatíveis.
Estado: commit abc123 com alterações locais guardadas no artefacto patch_1.
Validações: nenhuma sobre as alterações atuais.
Interrupção: imediatamente após guardar a correção.
Próxima ação: adicionar o teste de regressão e executar os testes de autenticação.
```
