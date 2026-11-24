#!/usr/bin/env python3
"""SFX library tool: build / find / page / pick / mix / check."""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, "catalog.jsonl")
EVENTS = ("typing key click error success notify alarm transition whoosh zoom swipe impact stamp land pop "
          "appear card paper peel lock coins counter glitch power-on rise magic crowd applause heartbeat ambience").split()
AUDIO_EXT = (".wav", ".ogg", ".flac", ".mp3")
LICENSES = {"kenney": "CC0 1.0", "sonniss": "Sonniss GDC royalty-free, no attribution", "mixkit": "Mixkit license, no attribution"}

# Hebrew words -> event names (also used for plain word search)
HE = {
    "שגיאה": "error", "טעות": "error", "כשלון": "error", "הקלדה": "typing", "מקלדת": "typing", "מקש": "key",
    "לחיצה": "click", "קליק": "click", "הצלחה": "success", "נכון": "success", "התראה": "notify", "הודעה": "notify",
    "אזעקה": "alarm", "מעבר": "transition", "ווש": "whoosh", "זום": "zoom", "החלקה": "swipe", "חבטה": "impact",
    "פגיעה": "impact", "חותמת": "stamp", "נחיתה": "land", "פופ": "pop", "הופעה": "appear", "כרטיס": "card",
    "נייר": "paper", "קילוף": "peel", "מנעול": "lock", "מטבעות": "coins", "כסף": "coins", "מונה": "counter",
    "גליץ'": "glitch", "גליץ": "glitch", "הדלקה": "power-on", "עלייה": "rise", "קסם": "magic", "קהל": "crowd",
    "מחיאות": "applause", "כפיים": "applause", "דופק": "heartbeat", "אווירה": "ambience", "רקע": "ambience",
    "משרד": "ambience", "דלת": "land",
}

# (regex on lowercased "folder file", what, events, class)  -- first match wins
RULES = [
    (r"applau|clap(s|ping)?|cheer", "applause / cheering crowd", "applause crowd", "accent"),
    (r"crowd|cheer|audience|stadium|people.*(talk|murmur)|walla|office|cafe|restaurant", "crowd / room ambience", "crowd ambience", "small"),
    (r"heartbeat|heart beat", "heartbeat", "heartbeat", "accent"),
    (r"typewriter.*\b(key|strike)|keyboard|typing|keystroke|key press", "typing / keys", "typing key", "small"),
    (r"typewriter", "typewriter mechanism (carriage / paper)", "paper lock", "small"),
    (r"thud|thump|wood.*(hit|heavy)|book.*(fall|close|slam)", "heavy dull thud", "stamp impact", "heavy"),
    (r"stamp", "stamp thump", "stamp impact", "heavy"),
    (r"error|fail|wrong|denied|buzzer|invalid", "error / negative feedback", "error", "accent"),
    (r"success|confirm|correct|achievement|win|victory|complete|fanfare|jingle", "success / positive chime", "success", "bell"),
    (r"alarm|siren|alert|warning", "alarm / alert", "alarm notify", "accent"),
    (r"notif|bell|ding|chime|ring|bong", "notification bell", "notify", "bell"),
    (r"coin|cash|money|chip|register|jackpot", "coins / money", "coins", "accent"),
    (r"counter|tally|ticker|count", "counter ticks", "counter", "small"),
    (r"glitch|static|digital error|corrupt|data ?mosh|bitcrush", "glitch / digital artifact", "glitch", "accent"),
    (r"power ?up|power ?on|boot|startup|activate|charge", "power-on / activation", "power-on rise", "accent"),
    (r"riser|rise|build ?up|swell|uplifter|tension", "riser / build-up", "rise", "accent"),
    (r"zoom", "zoom sweep", "zoom whoosh", "accent"),
    (r"whoosh|swoosh|swish|fly ?by|pass ?by|sweep|transition", "whoosh / transition", "whoosh transition", "accent"),
    (r"swipe|slide|slip|flick", "swipe / slide", "swipe", "small"),
    (r"slam|boom|hit|impact|crash|punch|explosion|thud|smash|drop", "impact / hit", "impact", "heavy"),
    (r"land|thump|footstep|step", "landing thump / step", "land", "accent"),
    (r"pop|bubble|blip|plop|pluck", "pop / pluck", "pop appear", "small"),
    (r"appear|reveal|open|unfold|show", "appear / reveal", "appear", "small"),
    (r"card|deal|shuffle|deck", "card handling", "card paper", "small"),
    (r"paper|page|book|cloth|fabric|rustle|wrap", "paper / cloth handling", "paper", "small"),
    (r"peel|sticker|tape|rip|tear|velcro", "peel / rip", "peel", "small"),
    (r"lock|latch|key|mechanism|clasp|click|switch|toggle|button|tick", "lock / latch / mechanical click", "lock click", "small"),
    (r"magic|spell|sparkle|shimmer|enchant|fairy|glitter|harp", "magic / sparkle", "magic", "accent"),
    (r"ui|interface|menu|select|hover|rollover|cursor|tap", "UI interaction", "click", "small"),
    (r"drone|ambien|room ?tone|atmos|wind|hum|loop|bed", "ambient bed", "ambience", "small"),
]

# Kenney: family name (file stem without trailing number) -> (what, events, class); matched by prefix
KENNEY = [
    ("interface-sounds/error", "UI error beep", "error", "accent"),
    ("interface-sounds/confirmation", "UI confirmation chime", "success", "bell"),
    ("interface-sounds/bong", "UI bong / bell", "notify", "bell"),
    ("interface-sounds/question", "UI question prompt", "notify", "small"),
    ("interface-sounds/glitch", "UI glitch", "glitch", "accent"),
    ("interface-sounds/scratch", "UI scratch", "glitch", "small"),
    ("interface-sounds/drop", "UI drop plop", "pop appear", "small"),
    ("interface-sounds/pluck", "UI pluck", "pop", "small"),
    ("interface-sounds/open", "UI open", "appear", "small"),
    ("interface-sounds/maximize", "UI maximize", "appear swipe", "small"),
    ("interface-sounds/minimize", "UI minimize", "swipe", "small"),
    ("interface-sounds/close", "UI close", "click", "small"),
    ("interface-sounds/back", "UI back", "click swipe", "small"),
    ("interface-sounds/scroll", "UI scroll tick", "key", "small"),
    ("interface-sounds/tick", "UI tick", "key counter", "small"),
    ("interface-sounds/glass", "UI glass tap", "click", "small"),
    ("interface-sounds/", "UI click / select / toggle", "click", "small"),
    ("ui-audio/rollover", "UI rollover", "key", "small"),
    ("ui-audio/", "UI mouse click / switch", "click", "small"),
    ("digital-audio/highup", "digital rising blip", "success", "small"),
    ("digital-audio/zapthreetoneup", "digital rising zap", "success rise", "accent"),
    ("digital-audio/zapthreetonedown", "digital falling zap", "error", "accent"),
    ("digital-audio/highdown", "digital falling blip", "error", "small"),
    ("digital-audio/lowdown", "digital low falling tone", "error", "accent"),
    ("digital-audio/lowrandom", "digital low random bleeps", "glitch", "small"),
    ("digital-audio/spacetrash", "digital noise burst", "glitch", "accent"),
    ("digital-audio/phaserup", "phaser rising sweep", "rise whoosh", "accent"),
    ("digital-audio/phaserdown", "phaser falling sweep", "transition whoosh", "accent"),
    ("digital-audio/phasejump", "phase jump zip", "whoosh transition", "accent"),
    ("digital-audio/powerup", "digital power-up", "power-on rise", "accent"),
    ("digital-audio/pepsound", "digital pep pop", "pop appear", "small"),
    ("digital-audio/threetone", "three-tone notification", "notify", "bell"),
    ("digital-audio/lowthreetone", "low three-tone notification", "notify", "accent"),
    ("digital-audio/twotone", "two-tone notification", "notify", "bell"),
    ("digital-audio/zap", "digital zap", "glitch pop", "accent"),
    ("digital-audio/laser", "digital laser", "zoom whoosh", "accent"),
    ("digital-audio/tone", "digital tone", "notify", "small"),
    ("impact-sounds/footstep", "footstep", "land key", "small"),
    ("impact-sounds/impactwood_heavy", "heavy wood thud", "stamp impact", "heavy"),
    ("impact-sounds/impactplank", "plank thud", "stamp impact", "accent"),
    ("impact-sounds/impactsoft_heavy", "heavy soft thud", "stamp impact", "heavy"),
    ("impact-sounds/impactplate_heavy", "heavy plate thud", "stamp impact", "heavy"),
    ("impact-sounds/impactbell", "bell impact", "impact notify", "bell"),
    ("impact-sounds/", "foley impact", "impact", "accent"),
    ("casino-audio/card-slide", "card slide", "card swipe paper", "small"),
    ("casino-audio/card", "card handling", "card paper", "small"),
    ("casino-audio/cards", "card pack handling", "card paper", "small"),
    ("casino-audio/chip", "casino chips", "coins", "accent"),
    ("casino-audio/dice", "dice", "land", "small"),
    ("casino-audio/die", "dice throw", "land", "small"),
    ("rpg-audio/bookclose", "book close thud", "stamp paper", "accent"),
    ("rpg-audio/bookplace", "book placed down", "stamp land paper", "accent"),
    ("rpg-audio/book", "book / page", "paper", "small"),
    ("rpg-audio/handlecoins", "handling coins", "coins", "accent"),
    ("rpg-audio/metallatch", "metal latch", "lock", "small"),
    ("rpg-audio/metalclick", "metal click", "lock click", "small"),
    ("rpg-audio/door", "door", "land", "accent"),
    ("rpg-audio/cloth", "cloth / belt rustle", "paper swipe", "small"),
    ("rpg-audio/knife", "knife swipe", "swipe whoosh", "small"),
    ("rpg-audio/chop", "chop hit", "impact", "accent"),
    ("rpg-audio/creak", "creak", "ambience", "small"),
    ("rpg-audio/", "RPG foley", "land", "small"),
    ("sci-fi-sounds/forcefield", "force field hum", "power-on", "accent"),
    ("sci-fi-sounds/explosion", "explosion", "impact", "heavy"),
    ("sci-fi-sounds/lowfrequency_explosion", "low explosion", "impact", "heavy"),
    ("sci-fi-sounds/impactmetal", "sci-fi metal impact", "impact", "accent"),
    ("sci-fi-sounds/laser", "sci-fi laser", "zoom whoosh", "accent"),
    ("sci-fi-sounds/door", "sci-fi door", "appear transition", "accent"),
    ("sci-fi-sounds/thruster", "thruster burst", "whoosh rise", "accent"),
    ("sci-fi-sounds/spaceengine", "space engine rumble", "ambience rise", "small"),
    ("sci-fi-sounds/engine", "engine hum", "ambience", "small"),
    ("sci-fi-sounds/computernoise", "computer bleeps (5s ambient)", "ambience", "small"),
    ("sci-fi-sounds/slime", "slime", "pop", "small"),
    ("music-jingles/", "short musical jingle", "success", "bell"),
]


def classify(source, rel):
    stem = os.path.splitext(os.path.basename(rel))[0]
    if source == "kenney":
        pack = rel.replace("\\", "/").split("/")[0]
        key = f"{pack}/{re.sub(r'[_-]?\d+$', '', stem).lower()}"
        key2 = f"{pack}/{stem.lower()}"
        for pre, what, ev, cl in KENNEY:
            if key.startswith(pre) or key2.startswith(pre):
                return what, ev.split(), cl, False
        return stem, ["click"], "small", True
    text = (rel.replace("\\", "/").replace("_", " ").replace("-", " ")).lower()
    # drop the vendor/UCS prefix noise but keep category + description
    for rx, what, ev, cl in RULES:
        if re.search(rx, text):
            return what, ev.split(), cl, False
    return stem, [], "small", True


def measure(path):
    try:
        return _measure(path)
    except Exception:
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as td:
            t = os.path.join(td, "x.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", "40", t], check=True)
            return _measure(t)


def _measure(path):
    import numpy as np, soundfile as sf
    info = sf.info(path)
    sr = info.samplerate
    data, sr = sf.read(path, frames=sr * 40, always_2d=True, dtype="float32")
    mono = np.abs(data).max(axis=1)
    if mono.size == 0:
        return None
    thr = 10 ** (-50 / 20)
    idx = np.nonzero(mono > thr)[0]
    start = int(idx[0]) if idx.size else 0
    trimmed = mono[start:]
    hit = float(np.argmax(trimmed)) / sr
    total = info.frames / sr
    seconds = max(total - start / sr, 0)
    shape = "one-shot" if seconds <= 3.5 else ("long" if seconds <= 15 else "bed")
    return {"seconds": round(seconds, 3), "onset": round(start / sr, 3), "hit": round(hit, 3), "shape": shape}


def cmd_build(_a):
    n = 0
    seen = set()
    with open(CATALOG, "w", encoding="utf-8") as out:
        for source in ("kenney", "sonniss", "mixkit"):
            base = os.path.join(ROOT, source)
            for dp, _d, files in os.walk(base):
                for fn in sorted(files):
                    if not fn.lower().endswith(AUDIO_EXT) or fn.lower().startswith("preview"):
                        continue
                    full = os.path.join(dp, fn)
                    rel = os.path.relpath(full, base)
                    try:
                        m = measure(full)
                    except Exception as e:
                        print("skip", rel, e, file=sys.stderr)
                        continue
                    if not m:
                        continue
                    what, events, cl, auto = classify(source, rel)
                    sid = re.sub(r"[^a-z0-9]+", "-", f"{source}-{os.path.splitext(rel)[0]}".lower()).strip("-")[:90]
                    base_id, k = sid, 2
                    while sid in seen:
                        sid = f"{base_id}-{k}"; k += 1
                    seen.add(sid)
                    ev_set = set(events)
                    pre = 0.0
                    if ev_set & {"whoosh", "zoom", "rise"} and m["shape"] != "bed":
                        pre = min(m["hit"], 3.0)
                    row = {"id": sid, "file": os.path.relpath(full, ROOT).replace("\\", "/"), "source": source,
                           "license": LICENSES[source], "what": what, "events": events, "class": cl,
                           "seconds": m["seconds"], "onset": m["onset"], "hit": m["hit"], "preroll": round(pre, 3),
                           "shape": m["shape"]}
                    if auto:
                        row["meta"] = "auto"
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
    print(f"catalog: {n} sounds -> {CATALOG}")


def load():
    with open(CATALOG, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def search(words, limit=10):
    q = []
    for w in words:
        for t in re.split(r"[,\s]+", w.lower()):
            if t:
                q.append(t)
    evs = {HE[t] for t in q if t in HE} | {t for t in q if t in EVENTS}
    terms = [t for t in q if t not in HE]
    scored = []
    for r in load():
        hay = (r["what"] + " " + r["file"]).lower().replace("_", " ")
        s = 0
        for e in evs:
            if e in r["events"]:
                s += 4 if r["events"][0] == e else 3
        for t in terms:
            if t in hay:
                s += 1
        if s and r.get("meta") == "auto":
            s -= 0.5
        if s and r["shape"] == "one-shot":
            s += 0.2
        if s > 0:
            scored.append((s, r))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [r for _s, r in scored[:limit]]


def cmd_find(a):
    for r in search(a.words, a.n):
        print(f'{r["id"]:<60} {",".join(r["events"]):<22} {r["class"]:<7} {r["seconds"]:>6.2f}s  {r["what"]}')


SR = 48000
TARGET_PEAK_DB = -1.0
TRANSITION_EVENTS = {"transition", "whoosh", "zoom", "swipe", "impact", "rise"}


def cmd_page(a):
    import html, pathlib, webbrowser
    rows = search(a.words, a.n)
    cards = []
    for r in rows:
        uri = pathlib.Path(os.path.join(ROOT, r["file"])).as_uri()
        cards.append(
            f'<div class="c"><b>{html.escape(r["id"])}</b><br>{html.escape(r["what"])} · {",".join(r["events"])} · '
            f'{r["class"]} · {r["seconds"]}s · {r["source"]}<br><audio controls preload="none" src="{uri}"></audio></div>')
    page = ('<!doctype html><meta charset="utf-8"><title>sfx</title><style>body{font:15px system-ui;margin:20px;max-width:760px}'
            '.c{border-bottom:1px solid #ccc;padding:10px 0}b{font-size:13px;word-break:break-all}</style>'
            f'<h2>{html.escape(" ".join(a.words))} ({len(rows)})</h2>' + "".join(cards))
    out = os.path.join(ROOT, "page.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)
    webbrowser.open(pathlib.Path(out).as_uri())


def _ffmpeg_decode(path):
    import subprocess, tempfile
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        t = os.path.join(td, "x.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ar", str(SR), "-ac", "2", t], check=True)
        data, _ = sf.read(t, dtype="float32", always_2d=True)
    return data


def cmd_pick(a):
    import numpy as np, soundfile as sf
    rows = {r["id"]: r for r in load()}
    if a.id not in rows:
        sys.exit(f"unknown id: {a.id} (use find)")
    r = rows[a.id]
    data = _ffmpeg_decode(os.path.join(ROOT, r["file"]))
    idx = np.nonzero(np.abs(data).max(axis=1) > 10 ** (-50 / 20))[0]
    data = data[int(idx[0]) if idx.size else 0:]
    f0 = int(a.from_s * SR) if a.from_s else 0
    f1 = int(a.to_s * SR) if a.to_s else len(data)
    data = data[f0:f1].copy()
    if data.size == 0:
        sys.exit("empty after trim")
    if a.to_s:
        k = min(int(0.02 * SR), len(data))
        data[-k:] *= np.linspace(1, 0, k)[:, None]
    pk = float(np.abs(data).max())
    if pk > 0:
        data = data * (10 ** (TARGET_PEAK_DB / 20) / pk)
    name = re.sub(r"[^\w-]+", "-", a.name or r["id"]).strip("-")[:60]
    sdir = os.path.join(a.project, "sfx")
    os.makedirs(sdir, exist_ok=True)
    sf.write(os.path.join(sdir, name + ".wav"), data, SR, subtype="PCM_24")
    hit = max(r["hit"] - (a.from_s or 0), 0.0)
    pre = round(min(hit, 3.0), 3) if r["preroll"] > 0 else 0.0
    jpath = os.path.join(sdir, "sfx.json")
    meta = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
    meta[name] = {"id": r["id"], "source": r["source"], "license": r["license"], "events": r["events"],
                  "class": r["class"], "seconds": round(len(data) / SR, 3), "hit": round(hit, 3), "preroll": pre,
                  "file": name + ".wav"}
    json.dump(meta, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{name}.wav  {len(data)/SR:.2f}s  preroll={pre}  [{r['source']}]")


def _load_cues(cues_path, sfx_dir=None):
    cues = json.load(open(cues_path, encoding="utf-8"))
    sdir = sfx_dir or os.path.join(os.path.dirname(os.path.abspath(cues_path)), "sfx")
    jpath = os.path.join(sdir, "sfx.json")
    meta = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
    for c in cues:
        if c["sound"] not in meta:
            sys.exit(f'cue at t={c["t"]}: sound "{c["sound"]}" not in {jpath} (run pick)')
    return sorted(cues, key=lambda c: c["t"]), meta, sdir


def cmd_mix(a):
    import numpy as np, soundfile as sf
    cues, meta, sdir = _load_cues(a.cues, a.sfx)
    n = int(round(a.duration * SR))
    out = np.zeros((n, 2), dtype=np.float64)
    cache = {}
    for c in cues:
        m = meta[c["sound"]]
        if c["sound"] not in cache:
            d, sr = sf.read(os.path.join(sdir, m["file"]), dtype="float32", always_2d=True)
            if sr != SR:
                sys.exit(f'{m["file"]} is {sr} Hz; re-run pick')
            cache[c["sound"]] = d if d.shape[1] == 2 else np.repeat(d[:, :1], 2, axis=1)
        d = cache[c["sound"]]
        if c.get("dur"):
            d = d[: int(c["dur"] * SR)].copy()
            k = min(int(0.05 * SR), len(d))
            d[-k:] *= np.linspace(1, 0, k)[:, None]
        start = int(round((c["t"] - m["preroll"]) * SR))
        if start < 0:
            d = d[-start:]
            start = 0
        end = min(start + len(d), n)
        if end <= start:
            continue
        ang = (max(-1.0, min(1.0, c.get("pan", 0))) + 1) * np.pi / 4
        pan = np.array([np.cos(ang), np.sin(ang)]) * np.sqrt(2)
        out[start:end] += d[: end - start] * (10 ** (c.get("gain", -20) / 20)) * pan
    pk = float(np.abs(out).max())
    if pk > 0.98:
        out *= 0.98 / pk
        print(f"warning: peak {pk:.2f} limited to 0.98 (lower some gains)")
    sf.write(a.out, out.astype(np.float32), SR, subtype="PCM_24")
    print(f"{a.out}: {len(cues)} cues, {a.duration}s, peak {20*np.log10(max(pk,1e-9)):.1f} dBFS")


def cmd_check(a):
    cues, meta, _ = _load_cues(a.cues, a.sfx)
    fails, warns = [], []
    iv = []
    for c in cues:
        m = meta[c["sound"]]
        s = c["t"] - m["preroll"]
        length = m["seconds"] if m["seconds"] > 3.5 else min(m["seconds"], 1.0)
        iv.append((max(s, 0.0), s + length))
    iv.sort()
    cur, gaps = 0.0, []
    for s, e in iv:
        if s - cur > 2.5:
            gaps.append((cur, s))
        cur = max(cur, e)
    if a.duration - cur > 2.5:
        gaps.append((cur, a.duration))
    for g0, g1 in gaps:
        fails.append(f"silence {g0:.2f}-{g1:.2f}s ({g1-g0:.1f}s without sound)")
    cuts = [float(x) for x in a.cuts.split(",") if x.strip()] if a.cuts else []
    for ct in cuts:
        ok = any(abs(c["t"] - ct) <= 0.35 and set(meta[c["sound"]]["events"]) & TRANSITION_EVENTS for c in cues)
        if not ok:
            warns.append(f"cut at {ct:.2f}s has no transition sound within 0.35s")
    prev = None
    for c in cues:
        if c["sound"] == prev:
            warns.append(f'{c["sound"]} repeats back-to-back at t={c["t"]}')
        prev = c["sound"]
        if meta[c["sound"]]["class"] == "heavy" and c.get("gain", -20) > -12:
            warns.append(f'heavy {c["sound"]} at t={c["t"]} too loud ({c.get("gain", -20)} dB, target -14)')
    heavy = [c for c in cues if meta[c["sound"]]["class"] == "heavy"]
    if len(heavy) > 2:
        warns.append(f"{len(heavy)} heavy hits; keep to 1-2 peaks")
    for w in warns:
        print("WARN ", w)
    for f in fails:
        print("FAIL ", f)
    print("check:", "FAILED" if fails else "ok", f"({len(cues)} cues, {len(warns)} warnings)")
    sys.exit(1 if fails else 0)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=cmd_build)
    f = sub.add_parser("find"); f.add_argument("words", nargs="+"); f.add_argument("-n", type=int, default=10); f.set_defaults(fn=cmd_find)
    g = sub.add_parser("page"); g.add_argument("words", nargs="+"); g.add_argument("-n", type=int, default=24); g.set_defaults(fn=cmd_page)
    k = sub.add_parser("pick"); k.add_argument("id"); k.add_argument("project"); k.add_argument("--as", dest="name")
    k.add_argument("--from", dest="from_s", type=float); k.add_argument("--to", dest="to_s", type=float); k.set_defaults(fn=cmd_pick)
    m = sub.add_parser("mix"); m.add_argument("cues"); m.add_argument("out"); m.add_argument("--duration", type=float, required=True)
    m.add_argument("--sfx"); m.set_defaults(fn=cmd_mix)
    c = sub.add_parser("check"); c.add_argument("cues"); c.add_argument("--duration", type=float, required=True)
    c.add_argument("--cuts"); c.add_argument("--sfx"); c.set_defaults(fn=cmd_check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
