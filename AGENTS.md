# Instruções de desenvolvimento

- Usar o ambiente Conda `dev` para desenvolver, executar e testar o projeto.
- Ativar o ambiente com `conda activate dev`. Em comandos não interativos, usar `conda run -n dev <comando>`.
- Manter o código simples e pequeno, com apenas as abstrações e dependências necessárias.
- Preferir alterações focadas e evitar complexidade antecipada.

## Handoff

- Para acompanhar ou retomar tarefas com o handoff, começar por `conda run -n dev handoff guide`.
- Usar a CLI local. Para continuar uma thread: `conda run -n dev handoff resume <id>`.
