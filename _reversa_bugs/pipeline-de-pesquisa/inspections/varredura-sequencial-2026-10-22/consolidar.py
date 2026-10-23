"""Consolidador da varredura sequencial Reversa.

Le os YAMLs de achados por feature, aplica dedupe heuristico (mesmos arquivos citados +
sobreposicao lexical do resumo), gera estatisticas por lente/confianca/severidade e
aponta clusters por componente. NAO registra bugs: apenas diagnostica e organiza.

Uso: python3 consolidar.py
"""
import glob
import os
import re
import sys
from collections import defaultdict

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ACHADOS = os.path.join(HERE, "achados")

STOP = set("""a o as os um uma de do da das dos em no na nos nas para por com sem e ou que
se ao aos como mas quando onde muito ja ainda apenas tambem nem sem entre sobre ate apos
ser sao esta estao ter havia foi eram seja sendo possui contem utilizando atraves
app py the of to in on for with""".split())


def tokens(text):
    return {t for t in re.findall(r"[a-zA-Z_]{4,}", (text or "").lower()) if t not in STOP}


def files_of(f):
    out = set()
    for e in f.get("evidence") or []:
        m = re.search(r"[\w/\.\-]+\.py", str(e))
        if m:
            out.add(m.group(0))
    return out


def load_all():
    items = []
    for path in sorted(glob.glob(os.path.join(ACHADOS, "feature-*.yaml"))):
        feat = os.path.basename(path).replace("feature-", "").replace(".yaml", "")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
        for row in data:
            row["_feature"] = feat
            row["_file"] = path
            items.append(row)
    return items


def dedupe(items):
    """Agrupa achados que citam os mesmos arquivos e compartilham vocabulario."""
    clusters = []
    used = set()
    for i, a in enumerate(items):
        if i in used:
            continue
        group = [a]
        used.add(i)
        fa, ta = files_of(a), tokens(a.get("summary"))
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            b = items[j]
            fb, tb = files_of(b), tokens(b.get("summary"))
            inter = fa & fb
            if not inter:
                continue
            jac = len(ta & tb) / max(1, len(ta | tb))
            same_symptom = jac >= 0.34 or (len(ta & tb) >= 4 and jac >= 0.2)
            if same_symptom:
                group.append(b)
                used.add(j)
        clusters.append(group)
    return clusters


def sev_rank(s):
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get((s or "").lower(), 9)


def main():
    items = load_all()
    if not items:
        print("nenhum achado encontrado em", ACHADOS)
        return 1

    print(f"achados brutos: {len(items)}")
    by_feat = defaultdict(int)
    by_lens = defaultdict(int)
    by_conf = defaultdict(int)
    by_sev = defaultdict(int)
    for f in items:
        by_feat[f["_feature"]] += 1
        by_lens[f.get("lens", "?")] += 1
        by_conf[f.get("confidence", "?")] += 1
        by_sev[f.get("suspected_severity", "?")] += 1

    print("\npor feature:", dict(sorted(by_feat.items())))
    print("\npor lente:")
    for k, v in sorted(by_lens.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    print("\npor confianca:", dict(sorted(by_conf.items())))
    print("\npor severidade suspeita:")
    for k in sorted(by_sev, key=sev_rank):
        print(f"  {by_sev[k]:3d}  {k}")

    clusters = dedupe(items)
    dupes = [c for c in clusters if len(c) > 1]
    print(f"\nclusters de duplicacao: {len(dupes)} (achados unicos logicos: {len(clusters)})")
    for c in dupes:
        ids = [x["finding_id"] for x in c]
        print(f"  {ids} -> {c[0].get('summary','')[:90]}")

    # clusters por componente (arquivo mais citado)
    comp = defaultdict(list)
    for f in items:
        for fl in files_of(f):
            comp[fl].append(f["finding_id"])
    top = sorted(comp.items(), key=lambda x: -len(x[1]))[:8]
    print("\narquivos com mais achados (indicio de causa estrutural):")
    for fl, ids in top:
        print(f"  {len(ids):3d}  {fl}")

    # severos primeiro
    print("\ntop severidade:")
    for f in sorted(items, key=lambda x: sev_rank(x.get("suspected_severity")))[:15]:
        print(f"  [{f.get('suspected_severity'):8s}] {f['finding_id']:12s} {f.get('summary','')[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
