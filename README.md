# Handoff

Estado persistente de tarefas para passagem entre agentes. Contrato em
[docs/data-contract.md](docs/data-contract.md).

## Desenvolvimento

Usar o ambiente Conda `dev`. O armazenamento usa apenas a biblioteca padrão do Python.

```sh
conda run -n dev python -m unittest discover -s tests -v
```

```python
from handoff import Store

with Store("handoff.db") as store:
    thread = store.create_thread("Corrigir sessões", "Rejeitar sessões expiradas")
    event = store.record(thread["id"], "progress", "Identificada a causa")
    store.checkpoint(
        thread["id"],
        covers_through_event=event["sequence"],
        interruption_point="Investigação terminada; código ainda não alterado",
        next_action="Corrigir a comparação de datas",
    )
    context = store.resume(thread["id"])
```

A base de dados é criada ao abrir `Store`. As correções da thread e os respetivos
eventos são gravados na mesma transação. `resume` lê um estado consistente.

Os artefactos são referências a ficheiros locais: o armazenamento calcula o hash,
mas não copia os ficheiros. É necessário mantê-los disponíveis e verificar o hash
antes de confiar no conteúdo. A integração MCP será acrescentada na próxima etapa.
