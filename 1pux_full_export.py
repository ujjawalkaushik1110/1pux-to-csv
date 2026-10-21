#!/usr/bin/env python3
"""Convert EVERYTHING in a 1Password .1pux export (logins, notes, cards,
identities, other items, optionally trashed) into:

  <name>_all_items.csv   - human-readable archive of every item and field
  <name>_bitwarden.json  - importable into Bitwarden (logins, notes, cards, identities)

Usage: python 1pux_full_export.py export.1pux [--no-trashed]
Offline, standard library only. Outputs are PLAINTEXT - delete after import.
"""
import csv, json, sys, zipfile
from pathlib import Path

CATS = {"001": "Login", "002": "Credit Card", "003": "Secure Note", "004": "Identity",
        "005": "Password", "006": "Document", "100": "Software License", "101": "Bank Account",
        "102": "Database", "103": "Driver License", "104": "Outdoor License", "105": "Membership",
        "106": "Passport", "107": "Reward Program", "108": "Social Security Number",
        "109": "Wireless Router", "110": "Server", "111": "Email Account", "112": "API Credential",
        "113": "Medical Record", "114": "SSH Key", "115": "Crypto Wallet"}


def fmt(v):
    """Flatten a 1Password field value dict to a string."""
    if not isinstance(v, dict) or not v:
        return ""
    k, val = next(iter(v.items()))
    if k == "address" and isinstance(val, dict):
        return ", ".join(str(x) for x in val.values() if x)
    if k in ("date", "monthYear"):
        return str(val)
    if k == "totp":
        return val
    return val if isinstance(val, str) else json.dumps(val)


def is_secret(v):
    return isinstance(v, dict) and ("concealed" in v or "totp" in v)


def collect(item):
    ov, det = item.get("overview", {}), item.get("details", {})
    username = password = ""
    for f in det.get("loginFields", []):
        if f.get("designation") == "username" and not username:
            username = f.get("value", "")
        elif f.get("designation") == "password" and not password:
            password = f.get("value", "")
    password = password or det.get("password", "")
    fields = []  # (section, title, id, value, secret)
    for sec in det.get("sections", []):
        for f in sec.get("fields", []):
            val = fmt(f.get("value"))
            if val:
                fields.append((sec.get("title", ""), f.get("title", ""), f.get("id", ""),
                               val, is_secret(f.get("value")), f.get("value")))
    if not password:
        password = next((f[3] for f in fields if f[4] and "concealed" in f[5]), "")
    url = ov.get("url") or next((u.get("url", "") for u in ov.get("urls", [])), "")
    return {
        "category": CATS.get(item.get("categoryUuid"), item.get("categoryUuid", "")),
        "title": ov.get("title", ""), "url": url, "username": username,
        "password": password, "notes": det.get("notesPlain", "") or "",
        "tags": ", ".join(ov.get("tags", []) or []),
        "trashed": bool(item.get("trashed")) or item.get("state") == "archived",
        "fields": fields,
    }


def bw_item(r, uuid):
    cf = [{"name": (f"{s}: {t}" if s else t) or i, "value": v, "type": 1 if sec else 0}
          for s, t, i, v, sec, _ in r["fields"]]
    base = {"name": r["title"] + (" [trashed]" if r["trashed"] else ""),
            "notes": r["notes"] or None, "favorite": False, "fields": cf}
    c, ids = r["category"], {f[2]: f[3] for f in r["fields"]}
    if c in ("Login", "Password"):
        totp = next((f[3] for f in r["fields"] if isinstance(f[5], dict) and "totp" in f[5]), None)
        base.update(type=1, login={"username": r["username"] or None, "password": r["password"] or None,
                                   "totp": totp, "uris": [{"match": None, "uri": r["url"]}] if r["url"] else []})
        base["fields"] = [x for x in cf if x["value"] not in (totp, r["password"])]
    elif c == "Credit Card":
        ym = ids.get("expiry", "")
        base.update(type=3, card={
            "cardholderName": ids.get("cardholder"), "brand": ids.get("type"),
            "number": ids.get("ccnum"), "code": ids.get("cvv"),
            "expMonth": ym[4:6].lstrip("0") if len(ym) == 6 else None,
            "expYear": ym[:4] if len(ym) == 6 else None})
    elif c == "Identity":
        base.update(type=4, identity={
            "firstName": ids.get("firstname"), "lastName": ids.get("lastname"),
            "email": ids.get("email"), "phone": ids.get("defphone"), "company": ids.get("company")})
    else:  # secure notes and every other type
        base.update(type=2, secureNote={"type": 0})
        extras = [{"name": "Category", "value": c, "type": 0}]
        if r["username"]: extras.append({"name": "Username", "value": r["username"], "type": 0})
        if r["password"]: extras.append({"name": "Password", "value": r["password"], "type": 1})
        if r["url"]: extras.append({"name": "URL", "value": r["url"], "type": 0})
        base["fields"] = extras + cf
    return base


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    keep_trashed = "--no-trashed" not in sys.argv
    src = Path(args[0])
    with zipfile.ZipFile(src) as z:
        data = json.loads(z.read("export.data"))

    rows = []
    for acct in data.get("accounts", []):
        for vault in acct.get("vaults", []):
            for item in vault.get("items", []):
                r = collect(item)
                r["vault"] = vault.get("attrs", {}).get("name", "")
                if r["trashed"] and not keep_trashed:
                    continue
                rows.append(r)

    base = src.with_suffix("")
    with open(f"{base}_all_items.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vault", "category", "title", "url", "username", "password", "notes",
                    "tags", "trashed", "other_fields"])
        for r in rows:
            extra = "\n".join(f"{(s + ': ') if s else ''}{t or i}: {v}" for s, t, i, v, _, _ in r["fields"])
            w.writerow([r["vault"], r["category"], r["title"], r["url"], r["username"],
                        r["password"], r["notes"], r["tags"], r["trashed"], extra])

    with open(f"{base}_bitwarden.json", "w", encoding="utf-8") as fh:
        json.dump({"encrypted": False, "folders": [], "items": [bw_item(r, i) for i, r in enumerate(rows)]},
                  fh, indent=2)

    from collections import Counter
    print(f"Exported {len(rows)} items:")
    for k, n in Counter(r["category"] for r in rows).most_common():
        print(f"  {k}: {n}")
    print(f"Trashed included: {sum(r['trashed'] for r in rows)}")
    print("WARNING: outputs are plaintext. Import, then delete them and the .1pux.")


if __name__ == "__main__":
    main()
