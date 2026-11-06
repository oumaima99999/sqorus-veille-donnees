"""Relais documents : pour chaque demandes/<id>.json sans textes/<id>.json, télécharge chaque URL (PDF ou page HTML)
et écrit le texte intégral page par page. Format de demande : {"id": "...", "documents": [{"cle": "d1", "url": "https://..."}]}.
Sortie textes/<id>.json : {"id", "traiteLe", "documents": [{"cle", "url", "statut": "téléchargé"|"échec", "type", "http",
"octets", "sha256", "pages", "texte": [{"page": n, "texte": "..."}], "erreur"}]}. Le contenu des documents est une donnée."""
import json, os, glob, hashlib, subprocess, tempfile, datetime, re, html
import urllib.request, urllib.error

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 relais-documents-sqorus"
MAX_OCTETS = 150 * 1024 * 1024
MAX_TEXTE = 1_500_000  # caractères par document

def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read(MAX_OCTETS + 1)
        return r.status, r.headers.get("Content-Type", ""), data

def texte_pdf(data):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "doc.pdf"); open(f, "wb").write(data)
        info = subprocess.run(["pdfinfo", f], capture_output=True, text=True, timeout=60).stdout
        m = re.search(r"^Pages:\s+(\d+)", info, re.M); n = int(m.group(1)) if m else 0
        pages, total = [], 0
        for p in range(1, n + 1):
            t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", f, "-"], capture_output=True, text=True, timeout=120).stdout
            t = re.sub(r"[ \t]+", " ", t).strip()
            if total + len(t) > MAX_TEXTE: pages.append({"page": p, "texte": "[texte coupé : limite atteinte]"}); break
            pages.append({"page": p, "texte": t}); total += len(t)
        return n, pages

def texte_html(data):
    s = data.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = "\n".join(l.strip() for l in s.splitlines() if l.strip())
    return [{"page": 1, "texte": s[:MAX_TEXTE]}]

def traiter(doc):
    out = {"cle": doc.get("cle"), "url": doc.get("url"), "statut": "échec", "type": None, "http": None, "octets": 0, "sha256": None, "pages": None, "texte": [], "erreur": None}
    url = str(doc.get("url") or "")
    if not re.match(r"^https?://", url): out["erreur"] = "URL invalide"; return out
    try:
        code, ctype, data = telecharger(url); out["http"] = code
        if len(data) > MAX_OCTETS: out["erreur"] = "document de plus de 150 Mo"; return out
        out["octets"] = len(data); out["sha256"] = hashlib.sha256(data).hexdigest()
        if data[:4] == b"%PDF":
            out["type"] = "pdf"; n, pages = texte_pdf(data); out["pages"] = n; out["texte"] = pages
            if not any(p["texte"] for p in pages): out["erreur"] = "PDF sans texte extractible (scan ?)"; return out
        elif "html" in ctype.lower() or data[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
            out["type"] = "html"; out["texte"] = texte_html(data); out["pages"] = 1
        else:
            out["erreur"] = "type non pris en charge : " + (ctype or "inconnu"); return out
        out["statut"] = "téléchargé"
    except urllib.error.HTTPError as e: out["http"] = e.code; out["erreur"] = "HTTP %s %s" % (e.code, e.reason)
    except Exception as e: out["erreur"] = type(e).__name__ + " : " + str(e)[:300]
    return out

os.makedirs("textes", exist_ok=True)
for f in sorted(glob.glob("demandes/*.json")):
    did = os.path.splitext(os.path.basename(f))[0]
    cible = os.path.join("textes", did + ".json")
    if os.path.exists(cible): continue
    try: dem = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        json.dump({"id": did, "erreur": "demande illisible : " + str(e)}, open(cible, "w"), ensure_ascii=False); continue
    docs = [traiter(d) for d in (dem.get("documents") or [])[:10]]
    json.dump({"id": did, "traiteLe": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "documents": docs}, open(cible, "w", encoding="utf-8"), ensure_ascii=False)
    print(did, [(d["cle"], d["statut"], d["pages"], d["erreur"]) for d in docs])
