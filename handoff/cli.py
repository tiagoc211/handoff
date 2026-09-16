"""Local CLI: JSON on stdout, errors on stderr."""

import argparse
import hashlib
import json
import sqlite3
import sys
from importlib.resources import files
from pathlib import Path

from . import dashboard
from .storage import Store


def json_file(path):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("O ficheiro deve conter um objeto JSON")
    return value


def main():
    parser = argparse.ArgumentParser(description="Handoff local. Sem subcomando, abre o dashboard.")
    parser.add_argument("--db", help="Base alternativa (padrão: ~/.handoff/handoff.db)")
    parser.add_argument("--once", action="store_true", help="Mostrar o dashboard e sair")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("guide", help="Instruções de uso para agentes")
    commands.add_parser("list", help="Listar threads em JSON")
    start = commands.add_parser("start", help="Criar uma thread")
    start.add_argument("title")
    start.add_argument("--objective", required=True)
    start.add_argument("--criterion", action="append", default=[])
    start.add_argument("--constraint", action="append", default=[])
    record = commands.add_parser("record", help="Registar progresso ou decisões")
    record.add_argument("thread_id")
    record.add_argument("summary")
    record.add_argument("--type", default="progress",
                        choices=["progress", "decision", "validation", "blocker", "correction"])
    record.add_argument("--evidence", action="append", default=[])
    update = commands.add_parser("update", help="Corrigir a thread e guardar um evento atomicamente")
    update.add_argument("thread_id")
    update.add_argument("--summary", required=True)
    update.add_argument("--file", required=True, help="Campos a alterar em JSON; - lê stdin")
    checkpoint = commands.add_parser("checkpoint", help="Guardar um checkpoint completo")
    checkpoint.add_argument("thread_id")
    checkpoint.add_argument("--file", required=True, help="Checkpoint em JSON; - lê stdin. Ver handoff guide")
    resume = commands.add_parser("resume", help="Obter contexto para continuar")
    resume.add_argument("thread_id")
    artifact = commands.add_parser("artifact", help="Registar um ficheiro de evidência")
    artifact.add_argument("thread_id")
    artifact.add_argument("path")
    artifact.add_argument("--media-type", default="text/plain")
    read = commands.add_parser("read", help="Consultar um registo ou evidência")
    read.add_argument("kind", choices=["thread", "checkpoint", "event", "artifact"])
    read.add_argument("id")
    read.add_argument("--content", action="store_true", help="Incluir texto do artefacto, verificando o hash")
    read.add_argument("--offset", type=int, default=0)
    read.add_argument("--limit", type=int, default=4000)
    args = parser.parse_args()
    if args.once and args.command:
        parser.error("--once só se aplica ao dashboard")
    try:
        if args.command is None:
            dashboard.main((["--db", args.db] if args.db else []) + (["--once"] if args.once else []))
            return
        if args.command == "guide":
            print(files("handoff").joinpath("agent-workflow.md").read_text(encoding="utf-8"))
            return
        with Store(args.db) as store:
            if args.command == "start":
                result = store.create_thread(args.title, args.objective, args.criterion, args.constraint)
            elif args.command == "list":
                result = store.list_threads()
            elif args.command == "record":
                result = store.record(args.thread_id, args.type, args.summary, args.evidence)
            elif args.command == "update":
                changes = json_file(args.file)
                for key, value in changes.items():
                    expected = list if key in {"constraints", "acceptance_criteria"} else str
                    if not isinstance(value, expected) or (expected is list and any(not isinstance(v, str) for v in value)):
                        raise ValueError(f"Campo inválido: {key}")
                result = store.update_thread(args.thread_id, summary=args.summary, **changes)
            elif args.command == "checkpoint":
                data = json_file(args.file)
                for key in ("completed", "in_progress", "pending", "decisions", "failed_approaches", "open_questions"):
                    if key in data and (not isinstance(data[key], list) or any(not isinstance(v, str) for v in data[key])):
                        raise ValueError(f"{key} deve ser uma lista de texto")
                for key in ("interruption_point", "next_action"):
                    if not isinstance(data.get(key), str):
                        raise ValueError(f"{key} deve ser texto")
                if data.get("workspace") is not None and not isinstance(data["workspace"], dict):
                    raise ValueError("workspace deve ser um objeto")
                if "validations" in data and (not isinstance(data["validations"], list) or any(not isinstance(v, dict) for v in data["validations"])):
                    raise ValueError("validations deve ser uma lista de objetos")
                result = store.checkpoint(args.thread_id, **data)
            elif args.command == "resume":
                result = store.resume(args.thread_id)
            elif args.command == "artifact":
                result = store.add_artifact(args.thread_id, args.path, args.media_type)
            else:
                if args.offset < 0 or not 1 <= args.limit <= 16000:
                    raise ValueError("offset >= 0 e limit entre 1 e 16000")
                if args.content and args.kind != "artifact":
                    raise ValueError("--content requer um artefacto")
                result = getattr(store, f"get_{args.kind}")(args.id)
                if args.content:
                    content = Path(result["location"]).read_bytes()
                    if hashlib.sha256(content).hexdigest() != result["sha256"]:
                        raise ValueError("Artefacto alterado desde o registo; regista a nova versão")
                    text = content.decode("utf-8")
                    end = args.offset + args.limit
                    result.update(content=text[args.offset:end], next_offset=end if end < len(text) else None)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    except KeyError as exc:
        parser.exit(1, f"Registo não encontrado: {exc}\n")
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"Erro: {exc}\n")


if __name__ == "__main__":
    main()
