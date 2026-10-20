"""Relais de veille SQORUS : télécharge des données publiques ouvertes (licence ouverte Etalab) que le service de Claude
ne peut pas joindre directement, garde les lignes qui contiennent les mots-clés, et publie de petits fichiers JSON dans
donnees/. Le service de Claude lit ensuite ces fichiers sur raw.githubusercontent.com.
Sources : APProch (projets d'achats publics de l'État) et DECP consolidées (marchés attribués).
Aucune clé, aucun secret. Chaque source a son statut (ok / échec + erreur exacte) dans donnees/statut.json."""
import csv, io, json, re, sys, time, unicodedata, urllib.request, datetime, traceback, os

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "donnees")
CFG = json.load(open(os.path.join(ICI, "mots-cles.json"), encoding="utf-8"))
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if not unicodedata.combining(c))
MOTS = [(m, re.compile(r"\b" + re.escape(norm(m)) + r"\b")) for m in CFG["mots_cles"]]
EXCL = [norm(x) for x in CFG.get("exclusions", [])]
def correspond(texte):
    t = norm(texte)
    if any(x in t for x in EXCL): return []
    return [m for m, rx in MOTS if rx.search(t)]
MAINTENANT = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
UA = {"User-Agent": "sqorus-veille-relais/1.0 (+https://github.com/oumaima99999/sqorus-veille-donnees)"}
def telecharger(url, fichier=None, essais=3):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=600) as r:
                if fichier:
                    with open(fichier, "wb") as f:
                        while True:
                            b = r.read(1 << 20)
                            if not b: break
                            f.write(b)
                    return r.geturl()
                return r.read(), r.geturl()
        except Exception as e:
            if k == essais - 1: raise
            time.sleep(5 * (k + 1))

statut = {"genere_le": MAINTENANT, "sources": {}}

# 1. APProch : projets d'achats publics (export CSV, séparateur ;)
URL_APPROCH = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/exports/csv?use_labels=true&delimiter=%3B"
try:
    brut, finale = telecharger(URL_APPROCH)
    texte = brut.decode("utf-8-sig")
    lignes = list(csv.DictReader(io.StringIO(texte), delimiter=";"))
    trouvees = []
    for l in lignes:
        m = correspond(" ".join(str(v) for v in l.values()))
        if m: trouvees.append({"mots_cles": m, "ligne": l})
    json.dump({"source": "APProch — projets d'achats publics (data.economie.gouv.fr)", "url": URL_APPROCH, "genere_le": MAINTENANT,
               "lignes_lues": len(lignes), "colonnes": list(lignes[0].keys()) if lignes else [], "resultats": trouvees},
              open(os.path.join(SORTIE, "approch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    statut["sources"]["approch"] = {"statut": "ok", "lignes_lues": len(lignes), "resultats": len(trouvees)}
except Exception as e:
    statut["sources"]["approch"] = {"statut": "échec", "erreur": f"{type(e).__name__} : {e}"[:500]}

# 2. DECP consolidées (Parquet, ~240 Mo) : marchés attribués, filtrés avec DuckDB sur toutes les colonnes texte
URL_DECP = "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
try:
    import duckdb
    fichier = "/tmp/decp.parquet"; finale = telecharger(URL_DECP, fichier)
    con = duckdb.connect()
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{fichier}')").fetchall()
    texte_cols = [c[0] for c in cols if "VARCHAR" in c[1].upper()]
    total = con.execute(f"SELECT count(*) FROM read_parquet('{fichier}')").fetchone()[0]
    concat = " || ' ' || ".join(f"coalesce(CAST(\"{c}\" AS VARCHAR), '')" for c in texte_cols)
    cond = " OR ".join(f"strip_accents(lower({concat})) LIKE '%{norm(m).replace(chr(39), chr(39)*2)}%'" for m, _ in MOTS)
    rows = con.execute(f"SELECT * FROM read_parquet('{fichier}') WHERE {cond} LIMIT 5000").fetchdf()
    res = []
    for r in rows.to_dict(orient="records"):
        r = {k: (None if v is None else (v.isoformat() if hasattr(v, "isoformat") else (v if isinstance(v, (int, float, str, bool)) else str(v)))) for k, v in r.items()}
        m = correspond(" ".join(str(r.get(c) or "") for c in texte_cols))
        if m: res.append({"mots_cles": m, "ligne": r})
    json.dump({"source": "DECP consolidées (data.gouv.fr)", "url": URL_DECP, "fichier_reel": finale, "genere_le": MAINTENANT,
               "lignes_lues": total, "colonnes": [c[0] for c in cols], "resultats": res},
              open(os.path.join(SORTIE, "decp.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    statut["sources"]["decp"] = {"statut": "ok", "lignes_lues": total, "resultats": len(res), "fichier_reel": finale}
except Exception as e:
    statut["sources"]["decp"] = {"statut": "échec", "erreur": f"{type(e).__name__} : {e}"[:500]}

json.dump(statut, open(os.path.join(SORTIE, "statut.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(statut, ensure_ascii=False))
