from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from .config import DEFAULT_CONFIG, load_config
from .database import Database
from .exporter import build_plan, execute_plan
from .reports import summary, write_all, write_gallery
from .scanner import scan

DEFAULT_DB = Path("fototriage.sqlite3")


def _progress(index: int, total: int, path: Path) -> None:
    short = path.name[:55]
    print(f"\r[{index:>5}/{total:<5}] {short:<55}", end="", flush=True)
    if index == total:
        print()


def _load_items(db_path: str):
    db = Database(db_path)
    try:
        run_id = db.latest_run_id()
        return db, run_id, db.load_images(run_id), db.run_info(run_id)
    except Exception:
        db.close()
        raise


def command_scan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_id, items, warnings = scan(
        args.source, args.db, config, args.profile, args.model, _progress
    )
    stats = summary(items)
    print(json.dumps({"run_id": run_id, **stats}, indent=2, ensure_ascii=False))
    for warning in warnings:
        print(f"ADVERTENCIA: {warning}", file=sys.stderr)
    if args.report:
        output = Path(args.report).expanduser().resolve()
        paths = write_all(items, output, {"id": run_id, "source": str(Path(args.source).resolve())})
        print("Reportes: " + ", ".join(str(path) for path in paths))
    return 0


def command_report(args: argparse.Namespace) -> int:
    db, run_id, items, info = _load_items(args.db)
    try:
        output = Path(args.output).expanduser().resolve()
        paths = write_all(items, output, info)
        print(json.dumps(summary(items), indent=2, ensure_ascii=False))
        print("Archivos: " + ", ".join(str(path) for path in paths))
    finally:
        db.close()
    return 0


def command_gallery(args: argparse.Namespace) -> int:
    db, _, items, _ = _load_items(args.db)
    try:
        target = Path(args.output).expanduser().resolve()
        write_gallery(items, target)
        print(target)
        if args.open:
            webbrowser.open(target.as_uri())
    finally:
        db.close()
    return 0


def command_explain(args: argparse.Namespace) -> int:
    db, _, items, _ = _load_items(args.db)
    try:
        wanted = Path(args.image).expanduser().resolve()
        match = next((item for item in items if Path(item.path) == wanted), None)
        if match is None:
            print(f"No se encontro en la ultima ejecucion: {wanted}", file=sys.stderr)
            return 2
        print(json.dumps(match.to_dict(), indent=2, ensure_ascii=False))
    finally:
        db.close()
    return 0


def command_export(args: argparse.Namespace) -> int:
    db, _, items, _ = _load_items(args.db)
    try:
        decisions = set(args.decision)
        output = Path(args.output).expanduser().resolve()
        plan = build_plan(items, output, decisions, args.mode)
        print(f"Plan: {len(plan)} archivo(s), operacion={args.mode}, destino={output}")
        for action in plan[:20]:
            print(f"  {action.operation}: {action.source} -> {action.destination}")
        if len(plan) > 20:
            print(f"  ... y {len(plan) - 20} acciones adicionales")
        if not args.apply:
            print("Simulacion solamente. Agregue --apply para ejecutar.")
            return 0
        completed, errors = execute_plan(plan)
        print(f"Completadas: {completed}; errores: {len(errors)}")
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1 if errors else 0
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fototriage", description="Clasificacion fotografica local, segura y explicable"
    )
    parser.add_argument("--version", action="version", version="FotoTriage 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="Analizar recursivamente una carpeta")
    scan_parser.add_argument("source")
    scan_parser.add_argument("--db", default=str(DEFAULT_DB))
    scan_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    scan_parser.add_argument("--profile", choices=["fast", "balanced", "deep"], default="fast")
    scan_parser.add_argument("--model", default="yolo11n.pt")
    scan_parser.add_argument("--report", metavar="DIRECTORIO", help="Generar reportes al finalizar")
    scan_parser.set_defaults(handler=command_scan)

    report_parser = sub.add_parser(
        "report", help="Generar CSV, JSON y galeria de la ultima ejecucion"
    )
    report_parser.add_argument("--db", default=str(DEFAULT_DB))
    report_parser.add_argument("--output", default="reportes")
    report_parser.set_defaults(handler=command_report)

    gallery_parser = sub.add_parser("gallery", help="Generar una galeria HTML")
    gallery_parser.add_argument("--db", default=str(DEFAULT_DB))
    gallery_parser.add_argument("--output", default="reportes/galeria.html")
    gallery_parser.add_argument("--open", action="store_true")
    gallery_parser.set_defaults(handler=command_gallery)

    explain_parser = sub.add_parser("explain", help="Explicar el score de una imagen")
    explain_parser.add_argument("image")
    explain_parser.add_argument("--db", default=str(DEFAULT_DB))
    explain_parser.set_defaults(handler=command_explain)

    export_parser = sub.add_parser("export", help="Copiar o mover imagenes clasificadas")
    export_parser.add_argument("--db", default=str(DEFAULT_DB))
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument(
        "--decision",
        action="append",
        choices=["important", "useful", "review", "trash_candidate", "corrupt"],
        default=[],
    )
    export_parser.add_argument("--mode", choices=["copy", "move"], default="copy")
    export_parser.add_argument(
        "--apply", action="store_true", help="Ejecutar; sin esta opcion solo simula"
    )
    export_parser.set_defaults(handler=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export" and not args.decision:
        args.decision = ["important", "useful", "review", "trash_candidate", "corrupt"]
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("\nOperacion cancelada.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
