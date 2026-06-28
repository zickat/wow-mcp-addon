#!/bin/bash
# Copie le dossier CharExport/ dans les AddOns WoW TBC Anniversary

SRC="$(dirname "$0")/CharExport"
DST="/Applications/World of Warcraft/_anniversary_/Interface/AddOns/CharExport"

echo "Copie $SRC → $DST"
cp -r "$SRC" "$(dirname "$DST")"
echo "✅ Addon mis à jour. Faites /exportchar puis /reload en jeu."
