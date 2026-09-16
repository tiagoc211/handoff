"""Small, read-only terminal view of the handoff database."""

import argparse
import json
import shutil
import sqlite3
import sys
import textwrap
from pathlib import Path

from .storage import Store, default_database


STATUS = {"active": "Em curso", "blocked": "Bloqueada", "completed": "Concluída"}


def clean(value):
    # Stored text must not execute terminal control sequences.
    return " ".join("".join(c if c.isprintable() else " " for c in str(value)).split())


def overview(threads, width):
    counts = " | ".join(
        f"{label}: {sum(t['status'] == status for t in threads)}"
        for status, label in STATUS.items()
    )
    lines = ["HANDOFF", counts, "─" * width]
    if not threads:
        lines.append("Ainda não existem threads. Cria uma através do MCP.")
    for number, thread in enumerate(threads, 1):
        label = f"{number:>3}  {STATUS[thread['status']]:<10}  {clean(thread['title'])}"
        lines.append(textwrap.shorten(label, width=width, placeholder="…"))
        lines.append(f"     {thread['id']}")
    return "\n".join(lines)


def detail(context, width):
    thread, checkpoint = context["thread"], context["checkpoint"]
    lines = [clean(thread["title"]), f"{STATUS[thread['status']]} | {thread['id']}"]

    def section(label, values):
        if not values:
            return
        lines.extend(["", label])
        for value in values:
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            lines.extend(textwrap.wrap(clean(value), width=width, initial_indent="  ",
                                       subsequent_indent="  "))

    section("Objetivo", [thread["objective"]])
    section("Critérios de conclusão", thread["acceptance_criteria"])
    section("Restrições", thread["constraints"])
    if checkpoint:
        for key, label in (
            ("completed", "Concluído"), ("in_progress", "Em curso"),
            ("pending", "Pendente"), ("decisions", "Decisões"),
            ("failed_approaches", "Tentativas falhadas"), ("validations", "Validações"),
            ("open_questions", "Questões / bloqueios"),
        ):
            section(label, checkpoint[key])
        section("Ponto de interrupção", [checkpoint["interruption_point"]])
        section("Próxima ação (checkpoint)", [checkpoint["next_action"]])
        section("Projeto / versão", [checkpoint["workspace"]] if checkpoint["workspace"] else [])
    else:
        lines.extend(["", "Sem checkpoint guardado."])
    section("Eventos posteriores — podem atualizar o checkpoint", [
        f"#{e['sequence']} [{e['type']}] {e['summary']}" for e in context["events"]
    ])
    section("Para continuar com outro agente", [f"Continua a thread {thread['id']} do handoff."])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Dashboard de terminal do Handoff")
    parser.add_argument("--db", help="Base de dados alternativa (padrão: ~/.handoff/handoff.db)")
    parser.add_argument("--once", action="store_true", help="Mostrar a lista e sair")
    args = parser.parse_args()
    path = Path(args.db).resolve() if args.db else default_database()
    if args.db and not path.is_file():
        parser.error(f"Base de dados não encontrada: {path}. Usa o caminho configurado no MCP.")
    try:
        with Store(path) as store:
            interactive = sys.stdin.isatty() and sys.stdout.isatty() and not args.once
            message = ""
            while True:
                width = max(40, min(shutil.get_terminal_size().columns, 100))
                threads = store.list_threads()
                if interactive:
                    print("\033[2J\033[H", end="")
                print(overview(threads, width))
                print(f"\nBase de dados: {clean(path)}")
                if not interactive:
                    return
                if message:
                    print(message)
                choice = input("\nNúmero: abrir | Enter: atualizar | q: sair > ").strip()
                message = ""
                if choice.lower() == "q":
                    return
                if not choice:
                    continue
                if not choice.isdecimal() or not 1 <= int(choice) <= len(threads):
                    message = "Escolhe um número da lista."
                    continue
                print("\033[2J\033[H", end="")
                print(detail(store.resume(threads[int(choice) - 1]["id"]), width))
                input("\nEnter: voltar à lista > ")
    except (EOFError, KeyboardInterrupt):
        print()
    except sqlite3.Error as exc:
        parser.exit(1, f"Não foi possível ler a base de dados: {exc}\n")


if __name__ == "__main__":
    main()
