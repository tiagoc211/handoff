# Passagem de trabalho

## Durante o trabalho

- Criar uma thread com `start` apenas para uma tarefa nova; guardar o ID. Para continuar uma existente, usar `resume`.
- Usar `record` após progresso relevante, decisões (com motivo), tentativas falhadas ou bloqueios. Evitar registar cada interação.
- Guardar correções do utilizador com `record`, `event_type="correction"` e `changes` nos campos afetados.
- Manter logs e patches em ficheiros estáveis, registados como artefactos. Referenciar os IDs em vez de copiar o conteúdo.

## Ao terminar uma etapa ou antes de parar

- Criar um `checkpoint` completo: concluído, em curso, pendente, decisões, tentativas falhadas, ponto exato de interrupção e próxima ação.
- Identificar o projeto, versão base e alterações locais em `workspace`. Distinguir ações planeadas, iniciadas e terminadas.
- Em `validations`, indicar comando/verificação, resultado, estado testado e evidência. Código implementado não significa código validado.
- `covers_through_event` é a última sequência efetivamente incorporada, não uma estimativa. Se necessário, consultar `resume`; usar `0` apenas sem eventos incorporados.
- Não esperar pelo esgotamento do contexto. Se bloqueado, atualizar o estado para `blocked` e explicar em `open_questions`. Marcar `completed` apenas após verificar os critérios de conclusão.
- Entregar o ID ao utilizador: «Continua a thread <id> do handoff».

## Ao retomar

- Chamar `resume` e integrar os eventos posteriores no checkpoint. Sem checkpoint, partir do objetivo e eventos disponíveis.
- Confirmar acesso ao projeto, versão e alterações relevantes. Investigar divergências antes de confiar nas validações afetadas.
- Usar `read` apenas para detalhes necessários; pedir conteúdo de artefactos explicitamente e por páginas.
- Executar a próxima ação sem repetir investigação já sustentada. Se faltar informação indispensável, registar a lacuna e pedir esclarecimento.
- Se a thread estiver concluída, informar o resultado. Se estiver bloqueada, verificar se o bloqueio foi resolvido antes de avançar.
