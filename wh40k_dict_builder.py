#!/usr/bin/env python3
"""
Unofficial Warhammer 40k Kindle Lexicon - dictionary builder v1.6
-----------------------------------------------------------------
Builds a Kindle pop-up dictionary from the Warhammer 40k Fandom wiki
(warhammer40k.fandom.com) plus a hand-written custom entries file. Long-press a
40k term on your Kindle and get a short definition, like the regular dictionary.

Needs: Python 3.8+ (no extra packages) and kindlegen 2.9 (Amazon's retired
command-line tool that makes Kindle dictionary files; see the README).

Usage (from a terminal in this folder):
    python wh40k_dict_builder.py                  full build (downloads ~15-30 min, resumable)
    python wh40k_dict_builder.py --limit 200      quick test with 200 articles
    python wh40k_dict_builder.py --build-only     rebuild from what's already downloaded
    python wh40k_dict_builder.py --kindlegen PATH tell it where kindlegen is

Custom entries: wh40k_custom_entries.txt next to this script (or --custom PATH).
Each line is   Headword | other spellings | definition   and is merged in at build time.

Licences: this script is MIT. Dictionary text is CC BY-SA 3.0 (wiki text from
Fandom contributors; custom entries by the project contributors).
Unofficial fan project, not affiliated with or endorsed by Games Workshop.
Warhammer 40,000 and associated names are trademarks of Games Workshop Limited.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request

VERSION = "1.6"
API = "https://warhammer40k.fandom.com/api.php"
WIKI = "https://warhammer40k.fandom.com/wiki/"
UA = f"WH40K-Kindle-Dictionary-Builder/{VERSION} (personal e-reader dictionary; low request rate)"
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "wh40k_dict_work")
OUT = os.path.join(HERE, "wh40k_dictionary_output")
CACHE = os.path.join(WORK, "cache.json")
DICT_TITLE = "Warhammer 40k Lexicon (unofficial)"
MAX_CHARS = 700
CUSTOM_DEFAULT = os.path.join(HERE, "wh40k_custom_entries.txt")

def find_custom(explicit):
    """Explicit path, else wh40k_custom_entries*.txt (incl. browser copies like '(1)') here or in the current folder."""
    if explicit:
        return explicit
    import glob
    for d in (HERE, os.getcwd()):
        hits = sorted(glob.glob(os.path.join(d, "wh40k_custom_entries*.txt")), key=os.path.getmtime, reverse=True)
        if hits:
            return hits[0]
    return None

def load_custom(path):
    """Read 'Headword | alt, alt | definition' lines. Returns list of (head, alts, text)."""
    if not path or not os.path.exists(path):
        return []
    out, bad = [], 0
    with open(path, encoding="utf-8-sig") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split("|")]
            if len(parts) == 2:
                parts = [parts[0], "", parts[1]]
            if len(parts) < 3 or not parts[0] or not parts[2]:
                bad += 1; print(f"   ! custom entries line {n} skipped (needs  Headword | spellings | definition)")
                continue
            head, alts, text = parts[0], [a.strip() for a in parts[1].split(",") if a.strip()], "|".join(parts[2:]).strip()
            out.append((head, alts, text))
    return out

# ----------------------------------------------------------------- network
class WikiError(Exception):
    pass

def api(params, delay):
    params = dict(params, format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(delay)
            if "error" in data:
                raise WikiError(data["error"].get("info", "API error"))
            return data
        except WikiError:
            raise
        except Exception as e:
            wait = min(120, 5 * 2 ** attempt)
            print(f"   network hiccup ({e}); retrying in {wait}s…")
            time.sleep(wait)
    raise SystemExit("The wiki isn't answering. Check your internet connection and run again (progress is saved).")

def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {"titles": [], "titles_done": False, "redirects": {}, "redirects_done": False, "text": {}}

def save_cache(c):
    os.makedirs(WORK, exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    os.replace(tmp, CACHE)

def list_titles(c, delay):
    if c["titles_done"]:
        return
    print("Step 1/4: listing wiki articles…")
    cont = {}; titles = []
    while True:
        d = api(dict(action="query", list="allpages", apnamespace=0, apfilterredir="nonredirects", aplimit=500, **cont), delay)
        titles += [p["title"] for p in d["query"]["allpages"]]
        print(f"   {len(titles)} articles found", end="\r")
        if "continue" not in d:
            break
        cont = {"apcontinue": d["continue"]["apcontinue"]}
    print()
    c["titles"] = titles; c["titles_done"] = True; save_cache(c)

def list_redirects(c, delay):
    if c["redirects_done"]:
        return
    print("Step 2/4: collecting alternate names (wiki redirects)…")
    names = c.get("redirect_names")
    if not names:
        cont = {}; names = []
        while True:
            d = api(dict(action="query", list="allpages", apnamespace=0, apfilterredir="redirects", aplimit=500, **cont), delay)
            names += [p["title"] for p in d["query"]["allpages"]]
            print(f"   {len(names)} alternate names found", end="\r")
            if "continue" not in d:
                break
            cont = {"apcontinue": d["continue"]["apcontinue"]}
        print()
        c["redirect_names"] = names; c["redirects"] = {}; c["redirect_pos"] = 0; save_cache(c)
    pos = c.get("redirect_pos", 0)
    while pos < len(names):
        batch = names[pos:pos + 50]
        d = api(dict(action="query", titles="|".join(batch), redirects=1), delay)
        for r in d.get("query", {}).get("redirects", []):
            c["redirects"].setdefault(r["to"], []).append(r["from"])
        pos += len(batch); c["redirect_pos"] = pos
        print(f"   matched {pos} / {len(names)} alternate names to their articles", end="\r")
        if (pos // 50) % 10 == 0:
            save_cache(c)
    print()
    c["redirects_done"] = True; save_cache(c)

def fetch_text(c, delay, limit):
    todo = [t for t in c["titles"] if t not in c["text"]]
    if limit:
        have = len(c["text"]); todo = todo[: max(0, limit - have)]
    if not todo:
        return
    print(f"Step 3/4: downloading article intros ({len(todo)} to go, 50 per request)…")
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        d = api(dict(action="query", prop="revisions", rvprop="content", rvslots="main", titles="|".join(batch)), delay)
        for p in d.get("query", {}).get("pages", []):
            try:
                wt = p["revisions"][0]["slots"]["main"]["content"]
            except (KeyError, IndexError):
                wt = ""
            c["text"][p["title"]] = summarize(wt)
        for t in batch:
            c["text"].setdefault(t, "")
        done = len(c["text"])
        print(f"   {done} / {limit or len(c['titles'])} articles", end="\r")
        if (i // 50) % 10 == 0:
            save_cache(c)
    print(); save_cache(c)

# ----------------------------------------------------------------- wikitext → plain text
def strip_nested(text, open_s, close_s):
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith(open_s, i):
            depth += 1; i += len(open_s); continue
        if depth and text.startswith(close_s, i):
            depth -= 1; i += len(close_s); continue
        if not depth:
            out.append(text[i])
        i += 1
    return "".join(out)

def summarize(wt):
    if not wt or re.search(r"\{\{\s*(disambig|disambiguation)", wt, re.I):
        return ""
    t = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = strip_nested(t, "{{", "}}")
    t = strip_nested(t, "{|", "|}")
    t = re.sub(r"\[\[(?:File|Image|Category|Media)\s*:[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[[a-z]{2,3}:[^\]]*\]\]", "", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\]", "", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    paras = []
    for block in re.split(r"\n\s*\n", t):
        lines = [l.strip() for l in block.split("\n")]
        lines = [l for l in lines if l and not re.match(r"^(=|\*|#|:|;|\||!|__)", l)]
        p = " ".join(lines).strip()
        p = re.sub(r"\s+", " ", p)
        if len(p) >= 60 and not p.lower().startswith(("for other uses", "this article", "see also", "main article")):
            paras.append(p)
        if sum(len(x) for x in paras) > MAX_CHARS or len(paras) >= 2:
            break
    s = " ".join(paras)
    if len(s) > MAX_CHARS:
        cut = s[:MAX_CHARS]
        dot = cut.rfind(". ")
        s = (cut[:dot + 1] if dot > MAX_CHARS * 0.5 else cut.rstrip() + "…")
    s = re.sub(r"\s+([,.;:])", r"\1", s).replace("( ", "(").replace(" )", ")").replace("()", "")
    return s.strip()

# ----------------------------------------------------------------- dictionary build
def forms_for(title, alts):
    base = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    forms = set([title, base] + list(alts))
    out = set()
    for f in forms:
        f = f.strip()
        if not f or len(f) > 60:
            continue
        out.add(f)
        out.add(f.lower())
        if " " not in f and f.isalpha():
            if f.endswith("s") and len(f) > 3:
                out.add(f[:-1])
            else:
                out.add(f + "s")
            if not f.endswith("s"):
                out.add(f + "'s"); out.add(f + "\u2019s")
    out.discard(base)
    return base, sorted(out)

COMMON = set("""a an the of and or in on at to for from by with without into onto over under upon about after before
between through during against among within along across behind beyond near far up down out off new old great grand high low
first second third last lost dark light black white red blue green gold golden silver grey gray iron steel stone fire blood death
war wars battle battles siege fall rise star stars sun moon world worlds void space marine marines guard imperial imperium chaos
lord lords king queen prince saint holy sacred eternal ancient dead living legion legions chapter chapters company order orders
knight knights hunter hunters wolf wolves eagle eagles lion lions dragon dragons angel angels son sons father mother brother brothers
sister sisters daughter daughters house city hive fortress gate gates tower towers wall walls sword swords blade blades shield
hammer hammers axe spear bolt bolter gun guns cannon storm thunder lightning wind winds sea ocean river mountain mountains
forge fleet ship ships crusade campaign war's day night time age era empire empires god gods man men human humans
mark pattern class type model series ii iii iv v vi vii viii ix x one two three four five six seven eight nine ten
alpha beta gamma delta omega prime major minor north south east west the
commander captain sergeant chaplain librarian inquisitor general colonel admiral warmaster primarch master veteran
lieutenant governor regiment regiments squad squads hand hands eye eyes heart hearts skull skulls clan clans warrior warriors
fist fists claw claws tooth teeth head heads crown throne keeper keepers lady sir high-lord magos archmagos cardinal
abbess canoness confessor commissar marshal castellan champion champions guardian guardians watcher watchers council
battle-barge cruiser frigate destroyer titan titans engine engines array station base outpost hive-world""".split())

def name_parts(titles):
    """Distinctive first/last words of multi-word titles, mapped to their article."""
    from collections import Counter, defaultdict
    whole = {re.sub(r"\s*\([^)]*\)\s*$", "", t).strip().lower() for t in titles}
    count, owner = Counter(), defaultdict(list)
    for t in titles:
        base = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
        words = [w for w in re.split(r"[\s\-]+", base) if w]
        if len(words) < 2:
            continue
        for w in {words[0], words[-1]}:
            w2 = w.strip("'\".,")
            if len(w2) < 4 or not w2[:1].isupper() or not re.match(r"^[A-Za-z'\u00C0-\u017F]+$", w2):
                continue
            lw = w2.lower()
            if lw in COMMON or lw in whole:
                continue
            count[lw] += 1; owner[lw].append((t, w2))
    out = defaultdict(list)
    for lw, n in count.items():
        if n <= 2:
            for t, w2 in owner[lw]:
                out[t].append(w2)
    return out

def esc(s):
    return html.escape(s, quote=True)

def build(c, custom=()):
    print("Step 4/4: building the Kindle dictionary…")
    if os.path.isdir(os.path.join(WORK, "src")):
        shutil.rmtree(os.path.join(WORK, "src"))
    src = os.path.join(WORK, "src"); os.makedirs(src)
    # one entry per headword; articles sharing a headword (e.g. a character and a novel) become numbered senses
    groups = {}   # base.lower() -> [base, [(title or None, text)], set(forms)]
    parts = name_parts([t for t, x in c["text"].items() if x])
    for title, text in sorted(c["text"].items()):
        if not text:
            continue
        base, forms = forms_for(title, c["redirects"].get(title, []) + parts.get(title, []))
        g = groups.setdefault(base.lower(), [base, [], set()])
        if title == base:          # the plain-named article goes first
            g[1].insert(0, (title, text))
        else:
            g[1].append((title, text))
        g[2].update(forms)
    added = merged = 0
    for head, alts, text in custom:
        base, forms = forms_for(head, alts)
        g = groups.get(base.lower())
        if g:
            merged += 1
        else:
            g = groups.setdefault(base.lower(), [base, [], set()]); added += 1
        g[1].append((None, text)); g[2].update(forms)
    if custom:
        print(f"   custom entries: {added} new, {merged} added to existing entries")
    multi = sum(1 for g in groups.values() if len(g[1]) > 1)
    if multi:
        print(f"   {multi} headwords have more than one meaning (shown as numbered senses)")
    entries = []
    for base, senses, forms in groups.values():
        forms.discard(base)
        entries.append((base, senses, sorted(forms)))
    entries.sort(key=lambda e: e[0].lower())
    if not entries:
        raise SystemExit("No usable articles yet. Run without --build-only first.")
    files = []
    head = ('<html xmlns:math="http://exslt.org/math" xmlns:svg="http://www.w3.org/2000/svg" '
            'xmlns:tl="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
            'xmlns:saxon="http://saxon.sf.net/" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cx="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:mbp="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
            'xmlns:mmc="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
            'xmlns:idx="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf">'
            '<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head><body><mbp:frameset>')
    tail = "</mbp:frameset></body></html>"
    CHUNK = 4000
    for k in range(0, len(entries), CHUNK):
        name = f"entries{k // CHUNK + 1:02d}.html"; files.append(name)
        with open(os.path.join(src, name), "w", encoding="utf-8") as f:
            f.write(head)
            for base, senses, forms in entries[k:k + CHUNK]:
                infl = "".join(f'<idx:iform value="{esc(x)}"/>' for x in forms)
                body = []
                numbered = len(senses) > 1
                for n, (title, text) in enumerate(senses, 1):
                    label = ""
                    if numbered:
                        sub = re.search(r"\(([^)]*)\)\s*$", title or "")
                        label = f"<b>{n}.</b> " + (f"<i>({esc(sub.group(1))})</i> " if sub else "")
                    paras = text.split("\n")
                    body.append(f"<p>{label}{esc(paras[0])}</p>" + "".join(f"<p>{esc(t)}</p>" for t in paras[1:]))
                    if title:
                        body.append(f'<p><small>{esc(WIKI + title.replace(" ", "_"))}</small></p>')
                f.write(f'<idx:entry name="default" scriptable="yes" spell="yes">'
                        f'<idx:orth value="{esc(base)}"><b>{esc(base)}</b>'
                        + (f"<idx:infl>{infl}</idx:infl>" if infl else "") +
                        f'</idx:orth>' + "".join(body) + '</idx:entry><hr/>\n')
            f.write(tail)
    with open(os.path.join(src, "about.html"), "w", encoding="utf-8") as f:
        f.write(f"<html><head><meta http-equiv='Content-Type' content='text/html; charset=utf-8'/></head><body>"
                f"<h1>{DICT_TITLE}</h1><p>{len(entries)} entries. Built {time.strftime('%Y-%m-%d')} with builder v{VERSION}.</p>"
                "<p><b>Unofficial fan project.</b> Not affiliated with or endorsed by Games Workshop. Warhammer 40,000 "
                "and all associated names and marks are trademarks of Games Workshop Limited. Free to share.</p>"
                "<p><b>Sources.</b> Entries with a web link are shortened from the Warhammer 40k Wiki "
                "(warhammer40k.fandom.com) by its contributors, licensed under CC BY-SA 3.0; each such entry links to its "
                "source article. Entries without a link are custom additions written for this dictionary by the project "
                "contributors. The Fenrisian word list was compiled with help from the Lexicanum page Fenris Vulgaris "
                "(wh40k.lexicanum.com), which draws on the lexicon appendix of the novel The Wolftime.</p>"
                "<p><b>Licence.</b> This dictionary is licensed under Creative Commons Attribution-ShareAlike 3.0 "
                "(https://creativecommons.org/licenses/by-sa/3.0/). You may copy, share and adapt it, including "
                "commercially under the licence's terms, as long as you give credit and share your version under the same "
                "licence. (Games Workshop's trademarks are not covered by this licence.)</p></body></html>")
    manifest = '<item id="about" href="about.html" media-type="application/xhtml+xml"/>' + "".join(
        f'<item id="e{i}" href="{n}" media-type="application/xhtml+xml"/>' for i, n in enumerate(files))
    spine = '<itemref idref="about"/>' + "".join(f'<itemref idref="e{i}"/>' for i in range(len(files)))
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">'
           f'<dc:title>{DICT_TITLE}</dc:title><dc:language>en</dc:language><dc:creator>Warhammer 40k Wiki contributors and Lexicon project contributors</dc:creator><dc:rights>CC BY-SA 3.0. Unofficial; not affiliated with Games Workshop.</dc:rights>'
           f'<dc:identifier id="uid">wh40k-lexicon-{VERSION}</dc:identifier>'
           '<x-metadata><DictionaryInLanguage>en</DictionaryInLanguage><DictionaryOutLanguage>en</DictionaryOutLanguage>'
           '<DefaultLookupIndex>default</DefaultLookupIndex></x-metadata></metadata>'
           f'<manifest>{manifest}</manifest><spine>{spine}</spine></package>')
    opf_path = os.path.join(src, "wh40k_lexicon.opf")
    with open(opf_path, "w", encoding="utf-8") as f:
        f.write(opf)
    print(f"   {len(entries)} entries written ({sum(len(e[2]) for e in entries)} alternate spellings)")
    return opf_path, len(entries)

def find_kindlegen(explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    found = shutil.which("kindlegen")
    if found:
        return found
    roots = []
    for v in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)", "APPDATA"):
        r = os.environ.get(v)
        if r and os.path.isdir(r):
            roots.append(r)
    roots.append("/Applications")
    for r in roots:
        try:
            tops = [d for d in os.listdir(r) if "amazon" in d.lower() or "kindle" in d.lower() or d.lower() == "programs"]
        except OSError:
            continue
        for t in tops:
            base = os.path.join(r, t)
            for dirpath, dirnames, filenames in os.walk(base):
                if dirpath[len(base):].count(os.sep) > 8:
                    dirnames[:] = []
                    continue
                if t.lower() == "programs" and dirpath == base:
                    dirnames[:] = [d for d in dirnames if "amazon" in d.lower() or "kindle" in d.lower()]
                for n in filenames:
                    if n.lower() in ("kindlegen.exe", "kindlegen"):
                        return os.path.join(dirpath, n)
    return None

def compile_mobi(opf_path, explicit=None):
    kg = find_kindlegen(explicit)
    if not kg:
        print("\n! Couldn't find kindlegen. Download kindlegen 2.9 (see README), unzip it, and pass its path, e.g.:")
        print('  python ' + os.path.basename(__file__) + ' --build-only --kindlegen "C:\\path\\to\\kindlegen.exe"')
        print(f"  (The dictionary source is ready in {os.path.dirname(opf_path)})")
        return None
    print(f"   Using kindlegen at: {kg}")
    print(f"   Compiling with kindlegen (this can take several minutes for a big dictionary)…")
    os.makedirs(OUT, exist_ok=True)
    name = f"WH40K_Lexicon_v{VERSION}.mobi"
    r = subprocess.run([kg, opf_path, "-c1", "-dont_append_source", "-o", name], capture_output=True, text=True, errors="ignore")
    built = os.path.join(os.path.dirname(opf_path), name)
    if not os.path.exists(built):
        print(r.stdout[-3000:]); print(r.stderr[-2000:])
        raise SystemExit("kindlegen did not produce a file. The messages above say why.")
    if r.returncode not in (0, 1):
        print("   (kindlegen finished with warnings; that's usually fine)")
    final = os.path.join(OUT, name); shutil.move(built, final)
    return final

def main():
    ap = argparse.ArgumentParser(description=f"Warhammer 40k Kindle Dictionary Builder v{VERSION}")
    ap.add_argument("--limit", type=int, default=0, help="only download this many articles (quick test)")
    ap.add_argument("--build-only", action="store_true", help="don't download; rebuild from saved data")
    ap.add_argument("--kindlegen", default=None, help="full path to kindlegen.exe if it isn't found automatically")
    ap.add_argument("--custom", default=None, help="custom entries file (default: wh40k_custom_entries.txt next to this script)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between wiki requests (be polite: 1+)")
    a = ap.parse_args()
    print(f"Warhammer 40k Kindle Dictionary Builder v{VERSION}\n")
    c = load_cache()
    if not a.build_only:
        try:
            list_titles(c, a.delay); list_redirects(c, a.delay); fetch_text(c, a.delay, a.limit)
        except WikiError as e:
            raise SystemExit(f"\nThe wiki refused a request: {e}\nProgress is saved. Please send this message to Claude so the builder can be fixed.")
    cpath = find_custom(a.custom)
    custom = load_custom(cpath)
    if custom:
        print(f"Loaded {len(custom)} custom entries from {cpath}")
    elif a.custom:
        print(f"! Custom entries file not found or empty: {a.custom}")
    else:
        print("!" * 60)
        print("! No wh40k_custom_entries.txt found next to this script, so NO custom entries")
        print(f"! (Fenrisian terms etc.) will be included. Looked in: {HERE}")
        print("!" * 60)
    opf, n = build(c, custom)
    mobi = compile_mobi(opf, a.kindlegen)
    if mobi:
        print(f"\nDone! Your dictionary: {mobi}\n")
        print("Put it on your Kindle:")
        print("  1. Plug the Kindle into the PC and open it in File Explorer (This PC > Kindle).")
        print("  2. Open Internal Storage > documents > dictionaries  (create 'dictionaries' if it's missing).")
        print(f"  3. Copy {os.path.basename(mobi)} into that folder, then unplug the Kindle.")
        print("  4. In a book, long-press any word, tap the dictionary's name in the pop-up,")
        print(f"     and choose '{DICT_TITLE}'. Switch back the same way.")

if __name__ == "__main__":
    main()
