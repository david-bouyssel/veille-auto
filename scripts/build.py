#!/usr/bin/env python3
"""Valide les éditions de data/editions/ et génère le site statique dans docs/.

- docs/index.html : la dernière édition, avec les archives.
- docs/editions/AAAA-MM-JJ.html : une page par édition.

Usage : python scripts/build.py [--check]   (--check : valide sans rien écrire)
Code de sortie 1 si une édition est invalide ; les erreurs sont listées.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
MODS = ROOT / "config" / "mods.json"
EDITIONS = ROOT / "data" / "editions"
TEMPLATE = ROOT / "templates" / "page.html"
DOCS = ROOT / "docs"
VENDOR = ROOT / "vendor"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOD_FORMATS = {"MOD", "XM", "IT", "S3M"}
# Version affichée en bas de page : MAJEUR.MINEUR.N, N = commits depuis BASE_COMMITS.
# N n'a pas de plafond (0.0.9 puis 0.0.10). MAJEUR et MINEUR ne changent qu'à la demande
# de l'auteur ; à ce moment-là, remettre BASE_COMMITS au nombre de commits courant.
# Indépendant des tags.
VERSION_MAJEUR = 0
VERSION_MINEUR = 0
BASE_COMMITS = 22

REQUIRED = ("rubrique", "source", "titre", "resume", "pourquoi", "url")


def version() -> str:
    """Numéro de version déduit du nombre de commits (historique complet requis)."""
    try:
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        return f"{VERSION_MAJEUR}.{VERSION_MINEUR}.{max(int(out) - BASE_COMMITS, 0)}"
    except (OSError, subprocess.CalledProcessError, ValueError):
        return f"{VERSION_MAJEUR}.{VERSION_MINEUR}.0"


def check_item(item: object, where: str, rubriques: set[str]) -> list[str]:
    if not isinstance(item, dict):
        return [f"{where} : doit être un objet"]
    errs = []
    for key in REQUIRED:
        val = item.get(key)
        if not isinstance(val, str) or not val.strip():
            errs.append(f"{where} : champ « {key} » manquant ou vide")
    if item.get("rubrique") and item["rubrique"] not in rubriques:
        errs.append(f"{where} : rubrique inconnue « {item['rubrique']} » (attendu : {', '.join(sorted(rubriques))})")
    url = item.get("url") or ""
    if url and not url.startswith(("http://", "https://")):
        errs.append(f"{where} : url invalide « {url} »")
    if item.get("date") is not None and not isinstance(item.get("date"), str):
        errs.append(f"{where} : date doit être une chaîne ISO 8601 ou null")
    if "suite" in item and not isinstance(item["suite"], bool):
        errs.append(f"{where} : suite doit être true ou false")
    hn = item.get("hn")
    if hn is not None:
        if not isinstance(hn, dict) or not str(hn.get("url", "")).startswith("https://news.ycombinator.com/"):
            errs.append(f"{where} : hn doit être null ou {{url, points, comments}} avec une url news.ycombinator.com")
    return errs


def check_edition(path: Path, ed: object, rubriques: set[str]) -> list[str]:
    name = path.name
    if not isinstance(ed, dict):
        return [f"{name} : la racine doit être un objet"]
    errs = []
    if ed.get("date") != path.stem or not DATE_RE.match(path.stem):
        errs.append(f"{name} : « date » doit valoir « {path.stem} » (nom du fichier, format AAAA-MM-JJ)")
    errs += check_item(ed.get("une"), f"{name} une", rubriques)
    items = ed.get("items")
    if not isinstance(items, list) or not items:
        errs.append(f"{name} : « items » doit être une liste non vide")
        items = []
    urls = {(ed.get("une") or {}).get("url")}
    for n, item in enumerate(items):
        errs += check_item(item, f"{name} items[{n}]", rubriques)
        if isinstance(item, dict):
            if item.get("url") in urls:
                errs.append(f"{name} items[{n}] : url en double « {item.get('url')} »")
            urls.add(item.get("url"))
    return errs


def load_all(rubriques: set[str]) -> tuple[list[dict], list[str]]:
    editions, errors = [], []
    for path in sorted(EDITIONS.glob("*.json")):
        try:
            ed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} : JSON invalide ({exc})")
            continue
        errs = check_edition(path, ed, rubriques)
        errors += errs
        if not errs:
            editions.append(ed)
    for n, ed in enumerate(editions, 1):
        ed["numero"] = n
    return editions, errors


def load_mods() -> tuple[dict, list[str]]:
    """Charge config/mods.json (facultatif) et le valide."""
    if not MODS.exists():
        return {"mods": [], "mixes": {}}, []
    try:
        cfg = json.loads(MODS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"mods": [], "mixes": {}}, [f"mods.json : JSON invalide ({exc})"]
    errs, seen = [], set()
    mods, mixes = cfg.get("mods"), cfg.get("mixes", {})
    if not isinstance(mods, list) or not isinstance(mixes, dict):
        return {"mods": [], "mixes": {}}, ["mods.json : « mods » doit être une liste et « mixes » un objet"]
    for n, m in enumerate(mods):
        where = f"mods.json mods[{n}]"
        if not isinstance(m, dict):
            errs.append(f"{where} : doit être un objet")
            continue
        if not isinstance(m.get("id"), int) or m["id"] <= 0:
            errs.append(f"{where} : « id » doit être l'identifiant numérique Mod Archive")
        elif m["id"] in seen:
            errs.append(f"{where} : id {m['id']} en double")
        seen.add(m.get("id"))
        for key in ("artiste", "titre", "licence"):
            if not isinstance(m.get(key), str) or not m[key].strip():
                errs.append(f"{where} : champ « {key} » manquant ou vide")
        if m.get("format") not in MOD_FORMATS:
            errs.append(f"{where} : format attendu parmi {', '.join(sorted(MOD_FORMATS))}")
        if not isinstance(m.get("ko"), int) or m["ko"] <= 0:
            errs.append(f"{where} : « ko » doit être la taille en Ko (entier)")
        if m.get("mix") is not None and str(m["mix"]) not in mixes:
            errs.append(f"{where} : mix {m['mix']} absent de « mixes »")
    sel = cfg.get("selection")
    if sel is not None and not (isinstance(sel, dict) and isinstance(sel.get("nom"), str) and sel["nom"].strip()
                                and str(sel.get("url", "")).startswith("https://")):
        errs.append("mods.json : « selection » doit être null ou {nom, url} avec une url https://")
    return cfg, errs


def mod_du_jour(mods_cfg: dict, day: str) -> dict | None:
    """Module de l'édition : parcourt la liste dans l'ordre, un morceau par jour."""
    mods = mods_cfg.get("mods") or []
    if not mods:
        return None
    m = mods[date.fromisoformat(day).toordinal() % len(mods)]
    return {
        "artiste": m["artiste"],
        "titre": m["titre"],
        "format": m["format"],
        "ko": m["ko"],
        "licence": m["licence"],
        "fichier": f"https://api.modarchive.org/downloads.php?moduleid={m['id']}",
        "page": f"https://modarchive.org/index.php?request=view_by_moduleid&query={m['id']}",
        "selection": mods_cfg.get("selection"),
    }


def copy_vendor() -> None:
    """Copie vendor/ dans docs/vendor/, en sautant les fichiers déjà identiques.

    Sous Windows, un fichier chargé par le navigateur de prévisualisation est verrouillé :
    le réécrire à l'identique ferait échouer le build.
    """
    if not VENDOR.is_dir():
        return
    for src in VENDOR.rglob("*"):
        if not src.is_file():
            continue
        dst = DOCS / "vendor" / src.relative_to(VENDOR)
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def to_script_json(data: object) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render(template: str, cfg: dict, mods_cfg: dict, editions: list[dict], idx: int, is_index: bool) -> str:
    ed = editions[idx]
    keep = cfg.get("archive_editions", 14)
    prefix = "editions/" if is_index else ""
    archive = [{
        "numero": e["numero"],
        "date": e["date"],
        "href": f"{prefix}{e['date']}.html",
        "items": [{"rubrique": i["rubrique"], "titre": i["titre"], "url": i["url"]} for i in [e["une"]] + e["items"]],
    } for e in reversed(editions[max(0, idx - keep):idx])]
    data = {
        "config": {
            "timezone": cfg.get("timezone", "Europe/Paris"),
            "rubriques": [{"id": r["id"], "nom": r["nom"], "couleur": r["couleur"]} for r in cfg["rubriques"]],
        },
        "edition": ed,
        "mod": mod_du_jour(mods_cfg, ed["date"]),
        "lecteur": ("./" if is_index else "../") + "vendor/chiptune3/chiptune3.js",
        "archive": archive,
        "nav": {
            "accueil": None if is_index else "../index.html",
            "precedente": f"{prefix}{editions[idx - 1]['date']}.html" if idx > 0 else None,
            "suivante": f"{editions[idx + 1]['date']}.html" if idx + 1 < len(editions) and not is_index else None,
        },
    }
    page = template.replace("__DATA__", to_script_json(data)).replace("__VERSION__", version())
    return page.replace("__TITRE__", f"Le Petit Compilé · n° {ed['numero']} · {ed['date']}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="valide sans écrire docs/")
    args = parser.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    rubriques = {r["id"] for r in cfg["rubriques"]}
    editions, errors = load_all(rubriques)
    mods_cfg, mod_errors = load_mods()
    errors += mod_errors
    if errors:
        print(f"{len(errors)} erreur(s) :", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    if not editions:
        print("Aucune édition dans data/editions/.", file=sys.stderr)
        return 1
    last = editions[-1]
    print(f"{len(editions)} édition(s) valide(s), dernière : n° {last['numero']} du {last['date']} "
          f"({len(last['items']) + 1} articles)")
    mod = mod_du_jour(mods_cfg, last["date"])
    if mod:
        print(f"Chiptune du jour : {mod['artiste']} - {mod['titre']} ({len(mods_cfg['mods'])} morceaux dans la liste)")
    if args.check:
        return 0

    template = TEMPLATE.read_text(encoding="utf-8")
    (DOCS / "editions").mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    copy_vendor()
    for idx, ed in enumerate(editions):
        out = DOCS / "editions" / f"{ed['date']}.html"
        out.write_text(render(template, cfg, mods_cfg, editions, idx, is_index=False), encoding="utf-8")
    (DOCS / "index.html").write_text(render(template, cfg, mods_cfg, editions, len(editions) - 1, is_index=True),
                                     encoding="utf-8")
    print(f"Site généré dans {DOCS.relative_to(ROOT)}/ ({datetime.now(timezone.utc):%H:%M} UTC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
