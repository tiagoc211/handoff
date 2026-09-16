# Handoff pelo terminal

Usar `handoff --help` e `handoff <comando> --help` para consultar argumentos.
Os comandos devolvem JSON; erros vão para stderr com código de saída 1.
`handoff` sozinho abre o dashboard. Não requer servidor nem configuração MCP.

## Durante o trabalho

- Criar uma thread: `handoff start "Título" --objective "Objetivo"`. Repetir
  `--criterion` e `--constraint` para critérios e restrições. Guardar o ID devolvido.
- Registar progresso relevante: `handoff record <id> "O que mudou"`.
  Usar `--type decision`, `validation` ou `blocker` quando aplicável.
  Decisões e tentativas falhadas incluem o motivo; evitar registar cada interação.
- Corrigir objetivo, restrições ou estado com `handoff update <id> --summary "Motivo" --file changes.json`.
  O ficheiro contém apenas os campos alterados, por exemplo `{"status":"blocked"}`.
- Guardar logs e patches em ficheiros estáveis: `handoff artifact <id> caminho`.
  Referenciar o ID devolvido com `record --evidence <artefacto>`.

## Guardar um checkpoint

Usar `handoff checkpoint <id> --file checkpoint.json` nos seguintes momentos:

- Assim que o plano estiver definido, antes de começar a implementação. Guardar
  os passos concretos em `pending`; dizer apenas «plano definido» não é suficiente.
- Após cada alteração relevante ou validação, antes de avançar para o próximo
  trabalho, mesmo que a etapa ou fase ainda esteja incompleta.
- Após uma mudança de plano, tentativa falhada ou bloqueio que altere a retoma.
- Antes de parar ou entregar o trabalho a outro agente.

Não adiar checkpoints até ao fim de uma fase ou do contexto: o utilizador pode
interromper a sessão sem aviso. Um evento de progresso não substitui um checkpoint.
Manter cada atualização curta e confirmar que o comando terminou com sucesso.

Também aceita `--file -` para ler JSON de stdin. Exemplo mínimo:

```json
{
  "covers_through_event": 0,
  "interruption_point": "Investigação terminada; código ainda não alterado",
  "next_action": "Corrigir a comparação de datas",
  "completed": ["Causa identificada"]
}
```

- `covers_through_event` é a última sequência realmente incorporada; consultar
  `handoff resume <id>` quando necessário. Usar 0 apenas sem eventos incorporados.
- Cada checkpoint substitui a visão atual completa: preservar `completed`,
  `in_progress`, `pending`, `decisions`, `failed_approaches` e `open_questions` relevantes.
- `workspace` identifica projeto, versão base e alterações locais. `validations`
  contém objetos com verificação, resultado, estado testado e referência à evidência.
- Distinguir ações planeadas, iniciadas e terminadas. Não esperar pelo fim do contexto.
- Se bloqueado, atualizar `status` para `blocked` e explicar em `open_questions`.
  Marcar `completed` apenas após verificar os critérios de conclusão.
- Entregar ao utilizador: «Continua a thread <id> do handoff».

## Retomar

1. Executar `handoff resume <id>`; integrar os eventos posteriores ao checkpoint.
2. Confirmar acesso ao projeto, versão e alterações relevantes. Investigar divergências
   antes de confiar nas validações afetadas.
3. Consultar detalhes apenas quando necessário: `handoff read artifact <id> --content`.
   Usar `--offset` e `--limit` para paginar; o conteúdo é verificado pelo hash.
4. Executar a próxima ação sem repetir investigação sustentada. Se faltar informação
   indispensável, registar a lacuna e pedir esclarecimento. Uma thread concluída não
   precisa de ser retomada; numa bloqueada, verificar primeiro o bloqueio.

Todos os comandos usam `~/.handoff/handoff.db`. Para outra base, colocar
`--db /caminho/base.db` antes do subcomando. O agente precisa de acesso ao comando,
à mesma base e aos ficheiros da tarefa. No ambiente de desenvolvimento, pode usar
`conda run -n dev handoff ...`.
