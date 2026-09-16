# Handoff

Estado persistente de tarefas para passagem entre agentes. Contrato em
[docs/data-contract.md](docs/data-contract.md).

As [instruções para os agentes](handoff/agent-workflow.md) são enviadas na
inicialização MCP. O cliente precisa de as disponibilizar ao modelo; caso não o
faça, incluir esse documento nas instruções do agente.

## Desenvolvimento

Usar o ambiente Conda `dev`. O armazenamento usa apenas a biblioteca padrão do Python.
O servidor usa o [SDK Python oficial do MCP](https://py.sdk.modelcontextprotocol.io/v1/), na linha 1.x.

```sh
conda run -n dev python -m pip install -e .
conda run -n dev python -m unittest discover -s tests -v
```

## Servidor MCP

O cliente inicia o servidor por stdio. Exemplo de configuração para clientes com
`mcpServers` (substituir o caminho da base de dados por um caminho absoluto real):

```json
{
  "mcpServers": {
    "handoff": {
      "command": "conda",
      "args": ["run", "--no-capture-output", "-n", "dev", "python", "-m", "handoff.server", "--db", "/caminho/absoluto/handoff.db"]
    }
  }
}
```

O diretório da base de dados deve existir. Usar o mesmo caminho entre sessões.
Se o cliente não encontrar `conda`, usar o caminho absoluto do executável.
`--no-capture-output` permite a comunicação stdio sem buffering do Conda.

| Ferramenta | Uso |
| --- | --- |
| `start` | Criar a thread e guardar o ID devolvido. |
| `record` | Registar eventos; `correction` com `changes` atualiza a thread. |
| `checkpoint` | Consolidar o trabalho, indicando a última sequência incorporada (`0` sem eventos). |
| `resume` | Obter a thread atual, o último checkpoint e os eventos posteriores. |
| `read` | Consultar um registo por tipo e ID. |

Para guardar evidência, usar `record` com `event_type="artifact"` e `artifact_path`
absoluto; depois incluir o ID devolvido em `evidence_refs` de um evento.
`read` devolve metadados por defeito. Para texto UTF-8, `include_content=true`
verifica o hash e devolve até `limit` caracteres (4000 por defeito, máximo 16000).
Continuar com `offset=next_offset` enquanto este não for nulo.

Os testes MCP iniciam processos reais, verificam as cinco ferramentas e retomam
uma thread num novo processo. Não é necessário um modelo ou uma chave de API.

Para validar uma passagem real: numa sessão, pedir ao agente uma tarefa pequena
e interrompê-la após um checkpoint. Numa nova sessão com acesso ao mesmo projeto
e base de dados, dizer apenas «Continua a thread <id> do handoff». Verificar se
o agente identifica a próxima ação, respeita as restrições e conclui a tarefa
sem pedir a explicação anterior. Este exercício com modelos é distinto dos testes
automatizados de transporte e persistência.

## Uso do armazenamento em Python

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
antes de confiar no conteúdo. A leitura de conteúdo pelo MCP faz essa verificação.
