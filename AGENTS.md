# Instruções de desenvolvimento

- Usar o ambiente Conda `dev` para desenvolver, executar e testar o projeto.
- Ativar o ambiente com `conda activate dev`. Em comandos não interativos, usar `conda run -n dev <comando>`.
- Manter o código simples e pequeno, com apenas as abstrações e dependências necessárias.
- Preferir alterações focadas e evitar complexidade antecipada.

## Handoff

- Para acompanhar ou retomar tarefas com o handoff, começar por `conda run -n dev handoff guide`.
- Usar a CLI local. Para continuar uma thread: `conda run -n dev handoff resume <id>`.
- Ao usar o handoff, guardar um checkpoint com o plano antes de implementar e atualizá-lo após cada alteração relevante ou validação, mesmo com a fase incompleta. Não esperar pelo fim da fase ou da sessão.
