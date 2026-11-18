#!/usr/bin/env python3
"""Contrôle des pages citées (relais « Chances de gain »).

Usage : python3 verifier_pages.py items.json textes1.json [textes2.json …] > items_verifies.json
  items.json   : liste des faits (format result.items) ;
  textesN.json : {"documents": [{"url", "texte": [{"page", "texte"}]}]} (fichier rendu par le relais GitHub,
                 ou texte d'une lecture directe mis au même format).
Pour chaque fait tiré d'un de ces documents et qui cite une page, chaque CHIFFRE de la preuve (montant, nombre décimal,
nombre de 4 chiffres ou plus, numéro d'appel d'offres « 24-20499 ») est cherché sur la page citée. S'il n'y est pas, la page
la plus proche qui le contient est ajoutée (origine.pages). S'il ne figure nulle part : origine.pageVerifiee = false et la
certitude le signale. Écrit les faits corrigés sur la sortie standard et le bilan {verifies, corriges, nonRetrouves,
chiffresControles} sur la sortie d'erreur (dernière ligne, JSON).
"""
import json, re, sys

ESP = re.compile(r"[\s  ]+")
# chiffre isolé : ni collé à une lettre ou à un chiffre ; entier nu : 5 chiffres ou plus, sans 0 initial (« CM03 0900 » ou une année ne sont pas des montants)
CHIFFRE = re.compile(r"(?<![\w.,-])(?:\d{2}-\d{5}|\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+[.,]\d+|[1-9]\d{4,})(?![\w-]|[.,]\d)")

def norm(t):
    return ESP.sub(" ", t or "").strip()

def compact(t):
    # sans espaces, virgule et point décimaux confondus (« 10 620 738,00 » = « 10620738.00 »)
    return t.replace(" ", "").replace(".", ",")

def present(ch, page_txt, page_compact):
    return ch in page_txt or compact(ch) in page_compact

def chiffres(preuve):
    vus = []
    for m in CHIFFRE.finditer(norm(preuve)):
        c = m.group(0)
        if re.fullmatch(r"(19|20)\d{2}", c):  # une année seule n'est pas un chiffre à contrôler
            continue
        if c not in vus:
            vus.append(c)
    return vus

def main():
    items = json.load(open(sys.argv[1], encoding="utf-8"))
    docs = {}
    for f in sys.argv[2:]:
        for d in json.load(open(f, encoding="utf-8")).get("documents", []):
            pages = {}
            for e in d.get("texte") or []:
                t = norm(e.get("texte"))
                pages[int(e["page"])] = (t, compact(t))
            if pages:
                docs[d.get("url")] = pages
    bilan = {"verifies": 0, "corriges": 0, "nonRetrouves": 0, "chiffresControles": 0}
    for it in items:
        o = it.get("origine") or {}
        url = o.get("url") or it.get("lien")
        cites = [int(p) for p in (o.get("pages") or ([o["page"]] if o.get("page") else [])) if str(p).isdigit()]
        if not cites or url not in docs:
            continue
        P = docs[url]
        finales, absents = list(cites), []
        for ch in chiffres(it.get("preuve", "")):
            bilan["chiffresControles"] += 1
            if any(present(ch, *P.get(p, ("", ""))) for p in finales):
                continue
            ou = sorted((abs(p - cites[0]), p) for p, (t, c) in P.items() if present(ch, t, c))
            if ou:
                finales.append(ou[0][1])
            else:
                absents.append(ch)
        finales = sorted(set(finales), key=lambda p: (p not in cites, p))
        o = dict(o)
        o["page"] = finales[0]
        if len(finales) > 1:
            o["pages"] = finales
        else:
            o.pop("pages", None)
        if absents:
            o["pageVerifiee"] = False
            it["certitude"] = (it.get("certitude") or "") + " — chiffre(s) non retrouvé(s) dans le document : " + ", ".join(absents)
            bilan["nonRetrouves"] += 1
        else:
            o["pageVerifiee"] = True
            bilan["verifies"] += 1
            if finales != cites:
                bilan["corriges"] += 1
        it["origine"] = o
    json.dump(items, sys.stdout, ensure_ascii=False, indent=1)
    print(json.dumps(bilan, ensure_ascii=False), file=sys.stderr)

if __name__ == "__main__":
    main()
