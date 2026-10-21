# 1pux-to-.csv
Convert 1Password .1pux exports to CSV (Google/Chrome) or Bitwarden JSON. Offline, no dependencies.
Google Password Manager only stores logins, so it can’t take notes, cards, or identities. I wrote a second script, 1pux_full_export.py, that exports everything:

python 1pux_full_export.py yourenamedfile.1pux

It creates two files and prints a count per category:

..._bitwarden.json: import into Bitwarden (free) via Tools, then Import data, then format “Bitwarden (json)”. Logins, secure notes, cards, and identities all come across as proper types. Other item types (servers, databases, API credentials, etc.) become secure notes with every field kept.
..._all_items.csv: a readable archive of every item and field, for backup.

Notes:

Trashed items are included and marked [trashed] in the name. Add --no-trashed to leave them out.
Document attachments (files) are not converted. They stay inside the .1pux, which is a zip you can open and extract from.
Keep using the first script and Google for your logins if you prefer, and use Bitwarden only for the rest.
The outputs are plaintext. Delete them and the .1pux once imported.
