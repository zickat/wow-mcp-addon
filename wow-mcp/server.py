#!/usr/bin/env python3
"""
wow-mcp/server.py
Serveur MCP local — expose les données du personnage WoW via SavedVariables.
Transport : stdio (compatible Claude Desktop).

Outils exposés :
  - list_characters    : liste tous les personnages exportés dans le SavedVariables
  - get_character_info : équipement + talents + stats d'un personnage
  - get_last_update    : horodatage du dernier export
  - get_item_info      : stats brutes d'un item par ID (base générique)
  - get_upgrades       : upgrades potentiels par slot pour n'importe quelle classe/spé
  - get_loot_table     : liste d'items utiles pour un mage Arcane (legacy)

Configuration :
  Créer un fichier .env (voir .env.example) pour préciser le chemin du fichier
  SavedVariables si l'auto-détection échoue.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from lua_parser import parse_saved_variables

load_dotenv()

# ------------------------------------------------------------------ data paths

import sys as _sys

def _data_dir() -> Path:
    """
    Résout le dossier data/ en mode normal et en mode PyInstaller frozen.
    - Normal   : <projet>/data/  (deux niveaux au-dessus de server.py)
    - Frozen   : sys._MEIPASS/data/  (données bundlées dans l'exe)
    """
    if getattr(_sys, "frozen", False):
        return Path(_sys._MEIPASS) / "data"  # type: ignore[attr-defined]
    return Path(__file__).parent.parent / "data"

_LOOT_JSON_PATH   = _data_dir() / "loot.json"
_ITEMS_DB_PATH    = _data_dir() / "items_db.json"
_WEIGHTS_PATH     = _data_dir() / "stat_weights.json"

_loot_cache:    Optional[dict] = None
_items_cache:   Optional[dict] = None
_weights_cache: Optional[dict] = None


def _load_loot() -> tuple[Optional[dict], Optional[str]]:
    global _loot_cache
    if _loot_cache is not None:
        return _loot_cache, None
    if not _LOOT_JSON_PATH.exists():
        return None, (
            "data/loot.json introuvable. "
            "Lancez : node generate-loot-json.js depuis le dossier du projet."
        )
    try:
        _loot_cache = json.loads(_LOOT_JSON_PATH.read_text(encoding="utf-8"))
        return _loot_cache, None
    except Exception as e:
        return None, f"Erreur lecture loot.json: {e}"


def _load_items_db() -> tuple[Optional[dict], Optional[str]]:
    global _items_cache
    if _items_cache is not None:
        return _items_cache, None
    if not _ITEMS_DB_PATH.exists():
        return None, (
            "data/items_db.json introuvable. "
            "Lancez : node build-items-db.js depuis le dossier du projet."
        )
    try:
        _items_cache = json.loads(_ITEMS_DB_PATH.read_text(encoding="utf-8"))
        return _items_cache, None
    except Exception as e:
        return None, f"Erreur lecture items_db.json: {e}"


def _load_weights() -> tuple[Optional[dict], Optional[str]]:
    global _weights_cache
    if _weights_cache is not None:
        return _weights_cache, None
    if not _WEIGHTS_PATH.exists():
        return None, "data/stat_weights.json introuvable."
    try:
        raw = json.loads(_WEIGHTS_PATH.read_text(encoding="utf-8"))
        # Strip _meta key
        _weights_cache = {k: v for k, v in raw.items() if not k.startswith("_")}
        return _weights_cache, None
    except Exception as e:
        return None, f"Erreur lecture stat_weights.json: {e}"

# ------------------------------------------------------------------ config

_WOW_SAVED_VARS_PATH: Optional[str] = os.getenv("WOW_SAVED_VARS_PATH")
_ADDON_DB_VAR = "CharExportDB"
_ADDON_FILE = "CharExport.lua"

# Sous-répertoires clients WoW Classic (par ordre de priorité)
_CLASSIC_SUBDIRS = ["_classic_", "_classic_era_", "_classic_ptr_", "_anniversary_"]

# Chemins de base WoW selon l'OS
_WOW_BASE_PATHS = [
    Path("/Applications/World of Warcraft"),           # macOS standard
    Path.home() / "Applications" / "World of Warcraft",
    Path("C:/Program Files (x86)/World of Warcraft"),  # Windows 32-bit install
    Path("C:/Program Files/World of Warcraft"),        # Windows 64-bit install
]

# ------------------------------------------------------------------ path resolution

def _find_saved_vars() -> Optional[Path]:
    """
    Localise CharExport.lua.
    Priorité : variable d'env WOW_SAVED_VARS_PATH > auto-détection.
    Si plusieurs fichiers trouvés, retourne le plus récemment modifié.
    """
    if _WOW_SAVED_VARS_PATH:
        p = Path(_WOW_SAVED_VARS_PATH)
        return p if p.exists() else None

    candidates: list[Path] = []
    for base in _WOW_BASE_PATHS:
        if not base.exists():
            continue
        for sub in _CLASSIC_SUBDIRS:
            account_root = base / sub / "WTF" / "Account"
            if account_root.exists():
                # SavedVariables account-wide : Account/<NOM>/SavedVariables/
                for f in account_root.rglob(_ADDON_FILE):
                    # Exclure les dossiers per-character (qui contiennent realm/perso dans le path)
                    # Les SavedVariables account-wide sont directement sous Account/<NOM>/SavedVariables/
                    parts = f.parts
                    sv_idx = next((i for i, p in enumerate(parts) if p == "SavedVariables"), None)
                    if sv_idx is not None:
                        # Account-wide : ...Account/<NOM>/SavedVariables/<fichier>
                        # Per-character : ...Account/<NOM>/<realm>/<perso>/SavedVariables/<fichier>
                        account_idx = next((i for i, p in enumerate(parts) if p == "Account"), None)
                        if account_idx is not None and sv_idx == account_idx + 2:
                            candidates.append(f)

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


# ------------------------------------------------------------------ data loading

def _load_data() -> tuple[Optional[dict], Optional[str]]:
    """
    Lit et parse le fichier SavedVariables.
    Retourne (data, None) en succès ou (None, message_erreur) en échec.
    """
    path = _find_saved_vars()

    if not path:
        return None, (
            "Fichier CharExport.lua introuvable. "
            "Copiez le dossier CharExport/ dans Interface/AddOns/ de WoW, "
            "connectez-vous en jeu, tapez /exportchar puis /reload. "
            "Ou définissez WOW_SAVED_VARS_PATH dans .env."
        )

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Impossible de lire {path}: {e}"

    try:
        db = parse_saved_variables(content, _ADDON_DB_VAR)
    except ValueError as e:
        return None, str(e)

    if not db:
        return None, (
            f"Variable '{_ADDON_DB_VAR}' absente de {path.name}. "
            "Utilisez /exportchar en jeu puis /reload."
        )

    file_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return {
        "db": db,
        "file_path": str(path),
        "file_mtime": file_mtime.isoformat(),
    }, None


def _fmt_ts(ts: int) -> str:
    """Convertit un timestamp Unix en string lisible UTC."""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


# ------------------------------------------------------------------ spec detection

# Talent tree → spec name per class (tab index 1-based, ordered as in-game)
_CLASS_SPECS: dict[str, list[str]] = {
    "MAGE":    ["Arcane", "Fire", "Frost"],
    "WARLOCK": ["Affliction", "Demonology", "Destruction"],
    "PRIEST":  ["Discipline", "Holy", "Shadow"],
    "DRUID":   ["Balance", "Feral", "Restoration"],
    "SHAMAN":  ["Elemental", "Enhancement", "Restoration"],
    "PALADIN": ["Holy", "Protection", "Retribution"],
    "HUNTER":  ["Beast Mastery", "Marksmanship", "Survival"],
    "ROGUE":   ["Assassination", "Combat", "Subtlety"],
    "WARRIOR": ["Arms", "Fury", "Protection"],
}


def _detect_spec(char_class: str, talents: list) -> Optional[str]:
    """
    Detect primary spec from talent distribution.
    Returns the spec name with the most points spent, or None.
    """
    specs = _CLASS_SPECS.get(char_class.upper(), [])
    if not specs or not talents:
        return None

    # talents is a list of tab dicts: [{tab, points_spent, talents:[...]}, ...]
    max_pts, best_tab = 0, 0
    for i, tab in enumerate(talents):
        pts = tab.get("points_spent", 0) if isinstance(tab, dict) else 0
        if pts > max_pts:
            max_pts, best_tab = pts, i

    if best_tab < len(specs):
        return specs[best_tab]
    return None


# ------------------------------------------------------------------ item scoring

# Map from items_db stat key → stat_weights key (most are identical)
_STAT_ALIAS: dict[str, str] = {
    "critRating":       "spellCritRating",  # fallback: many caster weights use spellCritRating
    "hitRating":        "spellHitRating",   # fallback for casters
}

# Slots that can score in our items_db
_SCOREABLE_SLOTS = {
    "Head", "Neck", "Shoulder", "Back", "Chest", "Wrist", "Hands",
    "Waist", "Legs", "Feet", "Finger", "Trinket",
    "MainHand", "OneHand", "TwoHand", "OffHand", "Held In Off-hand", "Ranged", "Relic",
}

# In-game slot → items_db slot values that can fill it
_SLOT_CANDIDATES: dict[str, list[str]] = {
    "Finger1":  ["Finger"],
    "Finger2":  ["Finger"],
    "Trinket1": ["Trinket"],
    "Trinket2": ["Trinket"],
    "MainHand": ["MainHand", "OneHand", "TwoHand"],
    "OffHand":  ["OffHand", "Held In Off-hand", "OneHand"],
    "Ranged":   ["Ranged"],
}


def _score_item(item_stats: dict, weights: dict, current_hit: float, hit_cap: float) -> float:
    """
    Compute a weighted score for an item's stats.
    Handles hit cap: above-cap hit is worthless.
    """
    score = 0.0
    for stat, val in item_stats.items():
        if stat == "armor":
            continue  # armor on cloth/leather irrelevant for scoring

        # Determine the weight key to use
        w_key = stat
        if stat not in weights:
            w_key = _STAT_ALIAS.get(stat, stat)

        # Check for hit cap
        if stat in ("hitRating", "spellHitRating"):
            cap_rating = hit_cap
            # Points below cap get full weight, above cap get 0
            below = max(0.0, min(float(val), cap_rating - current_hit))
            above = float(val) - below
            weight_below = weights.get(w_key, weights.get("spellHitRating", 0))
            weight_above = weights.get("spellHitRatingAboveCap", weights.get("hitRatingAboveCap", 0))
            score += below * weight_below + above * weight_above
        else:
            w = weights.get(w_key, 0.0)
            score += float(val) * w

    return score


# ------------------------------------------------------------------ buff subtraction

# TBC 2.4.3 — effets flat des buffs stat connus, indexés par spell ID.
# Clés = noms de stats tels qu'exportés par l'addon (stats lua).
# Les buffs % (Blessing of Kings, Moonkin Aura...) ne sont PAS listés ici
# car leur déduction nécessite la valeur de base pré-buff, impossible à récupérer via API.
_BUFF_EFFECTS: dict[int, dict[str, int]] = {
    # ── Arcane Intellect (rangs 1-7) ──────────────────────────────────────
    1459:  {"intellect": 3},
    3140:  {"intellect": 7},
    3141:  {"intellect": 11},
    10156: {"intellect": 17},
    10157: {"intellect": 22},
    27125: {"intellect": 31},
    # Arcane Brilliance (version groupe, rangs 1-3)
    23028: {"intellect": 31},
    27126: {"intellect": 31},

    # ── Mark of the Wild / Gift of the Wild ───────────────────────────────
    # rangs 1-8, valeurs all-stats (str/agi/sta/int/spi)
    5232:  {"strength": 6,  "agility": 6,  "stamina": 6,  "intellect": 6,  "spirit": 6},
    6756:  {"strength": 9,  "agility": 9,  "stamina": 9,  "intellect": 9,  "spirit": 9},
    5234:  {"strength": 11, "agility": 11, "stamina": 11, "intellect": 11, "spirit": 11},
    8907:  {"strength": 12, "agility": 12, "stamina": 12, "intellect": 12, "spirit": 12},
    9885:  {"strength": 16, "agility": 16, "stamina": 16, "intellect": 16, "spirit": 16},
    9886:  {"strength": 16, "agility": 16, "stamina": 16, "intellect": 16, "spirit": 16},
    26990: {"strength": 14, "agility": 14, "stamina": 14, "intellect": 14, "spirit": 14},  # rang 8
    # Gift of the Wild (groupe)
    21849: {"strength": 12, "agility": 12, "stamina": 12, "intellect": 12, "spirit": 12},
    26991: {"strength": 14, "agility": 14, "stamina": 14, "intellect": 14, "spirit": 14},

    # ── Bénédiction de Sagesse (MP5) ──────────────────────────────────────
    19742: {"mp5_casting": 41},   # rang 5
    25290: {"mp5_casting": 49},   # rang 6 (TBC)
    27142: {"mp5_casting": 49},

    # ── Bénédiction de Puissance (AP) ─────────────────────────────────────
    19740: {"attack_power": 185},  # rang 5
    25291: {"attack_power": 220},  # rang 6 (TBC)
    27140: {"attack_power": 220},

    # ── Flasques (SP) ─────────────────────────────────────────────────────
    28521: {"sp_arcane": 80, "sp_fire": 80, "sp_frost": 80, "sp_shadow": 80, "sp_holy": 80, "sp_nature": 80},  # Flask of Blinding Light
    28518: {"sp_shadow": 80, "sp_fire": 80, "sp_frost": 80, "sp_arcane": 80, "sp_holy": 80, "sp_nature": 80},  # Flask of Pure Death

    # ── Huile de Baguette (weapon oils, SP) ───────────────────────────────
    25122: {"sp_arcane": 36, "sp_fire": 36, "sp_frost": 36, "sp_shadow": 36, "sp_holy": 36, "sp_nature": 36},  # Brilliant Wizard Oil
    # Superior Wizard Oil (+42 SP)
    46978: {"sp_arcane": 42, "sp_fire": 42, "sp_frost": 42, "sp_shadow": 42, "sp_holy": 42, "sp_nature": 42},

    # ── Well Fed (nourriture SP) ──────────────────────────────────────────
    33254: {"sp_arcane": 23, "sp_fire": 23, "sp_frost": 23, "sp_shadow": 23, "sp_holy": 23, "sp_nature": 23, "spirit": 20},  # Blackened Basilisk
    33259: {"sp_arcane": 23, "sp_fire": 23, "sp_frost": 23, "sp_shadow": 23, "sp_holy": 23, "sp_nature": 23, "spirit": 20},  # Crunchy Serpent
    35272: {"sp_arcane": 23, "sp_fire": 23, "sp_frost": 23, "sp_shadow": 23, "sp_holy": 23, "sp_nature": 23, "spirit": 20},  # Broiled Bloodfin

    # ── Greater Arcane Elixir (+35 SP) ───────────────────────────────────
    11390: {"sp_arcane": 35, "sp_fire": 35, "sp_frost": 35, "sp_shadow": 35, "sp_holy": 35, "sp_nature": 35},

    # ── Stamina (bouffe stamina) ───────────────────────────────────────────
    33256: {"stamina": 30},   # Warp Burger / Spicy Crawdad +30 sta
    33257: {"stamina": 30},
}

# Buffs % : on les détecte pour les signaler, mais on ne les déduit pas
_PERCENT_BUFFS: dict[int, str] = {
    20217: "Bénédiction des Rois (+10% toutes stats)",
    25898: "Bénédiction des Rois (+10% toutes stats)",
    24907: "Aura Furie des bois (+5% crit sorts)",
    31869: "Totem de la Colère (+3% SP, +3% crit sorts)",
    34206: "Totem de la Colère (+3% SP, +3% crit sorts)",
    10060: "Infusion de Pouvoir (+20% SP, -20% temps de cast)",
}


def _compute_unbuffed_stats(stats: dict, buffs: list[dict]) -> tuple[dict, list[str], list[str]]:
    """
    Soustrait les effets flat des buffs connus des stats exportées.
    Retourne (stats_unbuffed, buffs_subtracted, buffs_percent_only).
    """
    unbuffed = dict(stats)
    subtracted: list[str] = []
    percent_warnings: list[str] = []

    for buff in buffs:
        sid = int(buff.get("spell_id", 0))
        name = buff.get("name", "?")

        if sid in _PERCENT_BUFFS:
            percent_warnings.append(f"{name} ({_PERCENT_BUFFS[sid]}) — non déduit (% multiplicatif)")
            continue

        effects = _BUFF_EFFECTS.get(sid)
        if effects:
            for stat, val in effects.items():
                if stat in unbuffed:
                    unbuffed[stat] = max(0, unbuffed[stat] - val)
            subtracted.append(f"{name} (spell {sid}): {effects}")

    return unbuffed, subtracted, percent_warnings


def _get_current_hit(char_stats: dict, char_class: str, spec: str) -> float:
    """Extract current hit rating relevant to the class/spec."""
    if char_class in _MELEE_CLASSES or spec in _MELEE_SPECS:
        if char_class == "HUNTER":
            return float(char_stats.get("hit_ranged_rating", char_stats.get("hit_melee_rating", 0)))
        return float(char_stats.get("hit_melee_rating", 0))
    return float(char_stats.get("hit_spell_rating", 0))


def _get_hit_cap(char_class: str, spec: str, draenei: bool) -> float:
    """Return the relevant hit cap rating for this class/spec."""
    if char_class in _MELEE_CLASSES or spec in _MELEE_SPECS:
        # Draenei racial (Heroic Presence) applies to all hit, melee too
        return HIT_CAP_MELEE_RATING - (13.0 if draenei else 0.0)
    return HIT_CAP_SPELL_DRAENEI if draenei else HIT_CAP_SPELL_RATING


def _resolve_character(db: dict, character: str | None) -> tuple[str, dict]:
    """
    Resolve which character to use.
    Returns (char_name, char_data).
    Falls back to last_active if character is None or not found.
    """
    characters: dict = db.get("characters") or {}
    last_active: str = db.get("last_active") or ""

    if character:
        # Case-insensitive match
        for name, data in characters.items():
            if name.lower() == character.lower():
                return name, data
        # Not found — return error signal
        return character, {}

    # Default: last_active
    return last_active, characters.get(last_active) or {}


HIT_CAP_SPELL_RATING   = 202.0  # 16% vs boss lvl 73, no racial
HIT_CAP_SPELL_DRAENEI  = 189.0  # 15% with Draenei in group
HIT_CAP_MELEE_RATING   = 142.0  # 9% vs boss lvl 73 (specials), 1% = 15.7692 rating
HIT_CAP_RANGED_RATING  = 142.0  # same formula for ranged
EXPERTISE_SOFT_CAP     = 26     # 26 expertise skill = removes dodge → 6.5% = ~214 rating
EXPERTISE_RATING_PER   = 8.2    # ~8.2 rating = 1 expertise skill point at lvl 70

# Melee classes that use melee hit cap instead of spell hit cap
_MELEE_CLASSES = {"WARRIOR", "ROGUE", "HUNTER", "PALADIN"}  # Enhancement Shaman / Feral handled via spec
_MELEE_SPECS   = {"Enhancement", "Feral"}
# Backward compat aliases
HIT_CAP_RATING = HIT_CAP_SPELL_RATING
HIT_CAP_DRAENEI = HIT_CAP_SPELL_DRAENEI


# ------------------------------------------------------------------ MCP server

server = Server("wow-char-export")


_CHARACTER_PARAM = {
    "character": {
        "type": "string",
        "description": (
            "Nom du personnage à interroger (ex: 'Zickatmago'). "
            "Si omis, utilise le dernier personnage actif. "
            "Utilisez list_characters pour voir tous les personnages disponibles."
        ),
    }
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_characters",
            description=(
                "Liste tous les personnages exportés dans le fichier SavedVariables. "
                "Indique pour chacun : classe, niveau, realm, date du dernier export. "
                "Utile pour savoir quels alts/guildmates ont utilisé /exportchar."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_character_info",
            description=(
                "Retourne l'équipement (slot par slot avec item_id et nom), les talents et les stats "
                "du personnage exporté via l'addon CharExport. "
                "Inclut l'horodatage de l'export — vérifiez qu'il est récent avant de l'utiliser. "
                "Les données sont mises à jour en jeu avec /exportchar, puis flushées sur disque avec /reload."
            ),
            inputSchema={
                "type": "object",
                "properties": {**_CHARACTER_PARAM},
                "required": [],
            },
        ),
        types.Tool(
            name="get_last_update",
            description=(
                "Retourne uniquement l'horodatage du dernier export et le chemin du fichier SavedVariables. "
                "Utile pour savoir si les données sont fraîches avant d'appeler get_character_info."
            ),
            inputSchema={
                "type": "object",
                "properties": {**_CHARACTER_PARAM},
                "required": [],
            },
        ),
        types.Tool(
            name="get_item_info",
            description=(
                "Retourne les stats brutes d'un item TBC Classic par son item ID. "
                "Base générique (tous items reqLevel 55-70). "
                "Inclut : stats, sockets, slot, qualité, iLvl. "
                "Aucun jugement de valeur — les stats sont brutes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "L'item ID WoW (ex: 29076 pour Collar of the Aldor).",
                    },
                },
                "required": ["item_id"],
            },
        ),
        types.Tool(
            name="get_upgrades",
            description=(
                "Retourne les upgrades potentiels par slot pour le personnage actif. "
                "Détecte automatiquement la classe et la spé depuis les talents exportés. "
                "Applique les poids stat correspondants (data/stat_weights.json) pour scorer "
                "chaque item candidat vs le gear actuel. "
                "Fonctionne pour toutes les classes et spés TBC Classic. "
                "Paramètres optionnels : slot (cibler un slot précis), "
                "min_ilvl (filtrer par iLvl minimum), draenei (si Draenei dans le groupe, "
                "réduit le hit cap à 189 rating), top_n (nombre de candidats par slot, défaut 5)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "slot": {
                        "type": "string",
                        "description": (
                            "Slot à analyser (ex: Head, Back, Finger1, Trinket2, MainHand). "
                            "Si omis, analyse tous les slots."
                        ),
                    },
                    "min_ilvl": {
                        "type": "integer",
                        "description": "iLvl minimum des candidats (ex: 100 pour filtrer le pré-raid).",
                    },
                    "draenei": {
                        "type": "boolean",
                        "description": "True si un Draenei est dans le groupe (réduit hit cap à 189 rating).",
                        "default": False,
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Nombre de candidats par slot (défaut: 5).",
                        "default": 5,
                    },
                    "class_override": {
                        "type": "string",
                        "description": (
                            "Force une classe (ex: MAGE, WARLOCK). "
                            "Utile si le personnage actif n'est pas encore exporté."
                        ),
                    },
                    "spec_override": {
                        "type": "string",
                        "description": (
                            "Force une spé (ex: Arcane, Fire, Affliction). "
                            "Utile pour simuler un respec."
                        ),
                    },
                    **_CHARACTER_PARAM,
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_loot_table",
            description=(
                "Retourne les items utiles pour un mage Arcane TBC. "
                "Sources : raids Phase 2 (Karazhan, Gruul, Magtheridon, SSC, TK), "
                "donjons TBC héroïques, items craftés (Tailoring : Spellfire, Frozen Shadoweave, Spellstrike, Primal Mooncloth), "
                "réputation/vendeurs TBC (Sha'tar, Aldor, Scryer, Lower City…). "
                "Filtres : source (raid/dungeon/crafted/reputation), zone/set, slot, rating minimum. "
                "Rating mage : S=top (SP+Hit), A=bon, B=correct, C=situationnel, D=peu utile."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["raid", "dungeon", "crafted", "reputation", "all"],
                        "description": "Type de source. 'all' pour tout chercher (défaut).",
                    },
                    "zone": {
                        "type": "string",
                        "description": (
                            "Nom partiel de zone/set (ex: 'SSC', 'Serpentshrine', 'TK', 'Karazhan', "
                            "'Spellfire', 'Mana-Tombs')"
                        ),
                    },
                    "slot": {
                        "type": "string",
                        "description": "Slot d'équipement (ex: 'Head', 'Chest', 'Finger', 'Trinket', 'Back')",
                    },
                    "min_rating": {
                        "type": "string",
                        "enum": ["S", "A", "B", "C", "D"],
                        "description": "Rating minimum mage (défaut: D = tous)",
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:

    data, error = _load_data()
    if error:
        return [types.TextContent(type="text", text=f"❌ {error}")]

    db: dict = data["db"]
    file_mtime: str = data["file_mtime"]
    file_path: str = data["file_path"]
    characters: dict = db.get("characters") or {}

    args = arguments or {}

    # ---- list_characters ------------------------------------------------
    if name == "list_characters":
        if not characters:
            return [types.TextContent(type="text", text="❌ Aucun personnage exporté. Utilisez /exportchar en jeu puis /reload.")]
        result = []
        for char_name, char_data in sorted(characters.items()):
            exported_at = char_data.get("exported_at")
            result.append({
                "name":        char_name,
                "class":       char_data.get("class", "?"),
                "level":       char_data.get("level", "?"),
                "realm":       char_data.get("realm", "?"),
                "last_export": _fmt_ts(exported_at) if exported_at else "jamais",
            })
        return [types.TextContent(type="text", text=json.dumps(
            {"characters": result, "last_active": db.get("last_active"), "file_last_modified": file_mtime},
            ensure_ascii=False, indent=2,
        ))]

    # -- resolve character for all remaining tools --
    char_name, char = _resolve_character(db, args.get("character"))

    # ---- get_last_update ------------------------------------------------
    if name == "get_last_update":
        exported_at = char.get("exported_at")
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "character": char_name,
                        "last_export": _fmt_ts(exported_at) if exported_at else "jamais",
                        "file_last_modified": file_mtime,
                        "file_path": file_path,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    # ---- get_character_info ---------------------------------------------
    if name == "get_character_info":
        if not char:
            return [
                types.TextContent(
                    type="text",
                    text=(
                        f"❌ Aucune donnée pour '{char_name}'. "
                        f"Personnages disponibles : {', '.join(sorted(characters.keys()))}. "
                        "Utilisez /exportchar en jeu puis /reload."
                    ),
                )
            ]

        exported_at = char.get("exported_at")

        equipment: dict = {}
        for slot, item in (char.get("equipment") or {}).items():
            if isinstance(item, dict):
                equipment[slot] = {
                    "item_id": item.get("item_id"),
                    "name": item.get("name", ""),
                    "link": item.get("link", ""),
                }

        raw_stats = char.get("stats") or {}
        char_buffs = char.get("buffs") or []
        stats_unbuffed, subtracted, pct_warnings = _compute_unbuffed_stats(raw_stats, char_buffs)

        output = {
            "character": char_name,
            "realm": char.get("realm"),
            "class": char.get("class"),
            "level": char.get("level"),
            "exported_at": _fmt_ts(exported_at) if exported_at else "inconnu",
            "file_last_modified": file_mtime,
            "equipment": equipment,
            "talents": char.get("talents") or [],
            "stats_buffed": raw_stats,
            "stats": stats_unbuffed,
            "buffs_active": char_buffs,
            "buffs_subtracted": subtracted,
            "buffs_percent_warnings": pct_warnings,
        }

        return [
            types.TextContent(
                type="text",
                text=json.dumps(output, ensure_ascii=False, indent=2),
            )
        ]

    # ---- get_item_info --------------------------------------------------
    if name == "get_item_info":
        items_db, ierr = _load_items_db()
        if ierr:
            return [types.TextContent(type="text", text=f"❌ {ierr}")]
        item_id = args.get("item_id")
        if not item_id:
            return [types.TextContent(type="text", text="❌ item_id requis.")]
        item = items_db.get(str(item_id)) or items_db.get(int(item_id))  # type: ignore
        if not item:
            return [types.TextContent(type="text", text=f"❌ Item {item_id} non trouvé dans items_db.")]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(item, ensure_ascii=False, indent=2),
            )
        ]

    # ---- get_upgrades ---------------------------------------------------
    if name == "get_upgrades":
        items_db, ierr = _load_items_db()
        if ierr:
            return [types.TextContent(type="text", text=f"❌ {ierr}")]
        weights_all, werr = _load_weights()
        if werr:
            return [types.TextContent(type="text", text=f"❌ {werr}")]

        if not char:
            return [types.TextContent(type="text", text=(
                f"❌ Aucune donnée pour '{char_name}'. "
                f"Personnages disponibles : {', '.join(sorted(characters.keys()))}. "
                "Utilisez /exportchar puis /reload."
            ))]

        slot_filter   = args.get("slot", "").strip()
        min_ilvl      = int(args.get("min_ilvl") or 0)
        draenei       = bool(args.get("draenei", False))
        top_n         = max(1, int(args.get("top_n") or 5))
        cls_override  = (args.get("class_override") or "").strip().upper()
        spec_override = (args.get("spec_override") or "").strip()

        char_class   = cls_override or (char.get("class") or "").upper()
        char_talents = char.get("talents") or []
        char_equip   = char.get("equipment") or {}
        raw_stats    = char.get("stats") or {}
        char_buffs   = char.get("buffs") or []
        char_stats, subtracted_upgrades, _ = _compute_unbuffed_stats(raw_stats, char_buffs)

        # Detect spec
        detected_spec = _detect_spec(char_class, char_talents)
        spec = spec_override or detected_spec or ""

        # Resolve weights
        class_weights = weights_all.get(char_class, {})
        spec_data     = class_weights.get(spec, {})
        if not spec_data and class_weights:
            spec_data = next(iter(class_weights.values()), {})
            spec = next(iter(class_weights.keys()), spec)
        weights = spec_data.get("weights", {}) if spec_data else {}

        if not weights:
            return [types.TextContent(type="text", text=(
                f"❌ Pas de poids stat pour {char_class}/{spec}. "
                f"Classes disponibles : {', '.join(weights_all.keys())}"
            ))]

        hit_cap     = _get_hit_cap(char_class, spec, draenei)
        current_hit = _get_current_hit(char_stats, char_class, spec)

        # Build current gear score per slot
        current_scores: dict[str, float] = {}
        current_items_info: dict[str, dict] = {}
        for slot_name, item_data in char_equip.items():
            if not isinstance(item_data, dict):
                continue
            iid = str(item_data.get("item_id", ""))
            db_item = items_db.get(iid)
            if db_item:
                current_scores[slot_name] = _score_item(
                    db_item.get("stats", {}), weights, current_hit, hit_cap
                )
                current_items_info[slot_name] = {
                    "item_id":   db_item["itemId"],
                    "name":      db_item["name"],
                    "itemLevel": db_item.get("itemLevel"),
                    "score":     round(current_scores[slot_name], 2),
                }
            else:
                current_scores[slot_name] = 0.0
                current_items_info[slot_name] = {
                    "item_id": item_data.get("item_id"),
                    "name":    item_data.get("name", "?"),
                    "score":   0.0,
                }

        # Determine which slots to analyse
        if slot_filter:
            slots_to_check = [slot_filter]
        else:
            slots_to_check = list(char_equip.keys())

        upgrades: dict[str, dict] = {}

        for slot_name in slots_to_check:
            if slot_name not in char_equip:
                upgrades[slot_name] = {"error": f"Slot '{slot_name}' absent du gear exporté."}
                continue

            # Determine which item db slots can fill this in-game slot
            candidate_slots = _SLOT_CANDIDATES.get(slot_name, [])
            if not candidate_slots:
                # Default: use the normalized slot name
                item_data = char_equip.get(slot_name, {})
                # Try to find the slot from current item
                cur_iid = str((item_data or {}).get("item_id", ""))
                cur_db  = items_db.get(cur_iid)
                if cur_db:
                    candidate_slots = [cur_db.get("slot", slot_name)]
                else:
                    candidate_slots = [slot_name]

            current_score = current_scores.get(slot_name, 0.0)
            cur_info      = current_items_info.get(slot_name, {})

            # Find candidates
            candidates_list = []
            for db_item in items_db.values():
                if not isinstance(db_item, dict):
                    continue
                if db_item.get("slot") not in candidate_slots:
                    continue
                if min_ilvl and (db_item.get("itemLevel") or 0) < min_ilvl:
                    continue
                # Skip current item
                if str(db_item.get("itemId")) == str((char_equip.get(slot_name) or {}).get("item_id")):
                    continue
                score = _score_item(db_item.get("stats", {}), weights, current_hit, hit_cap)
                if score <= 0:
                    continue
                candidates_list.append({
                    "item_id":   db_item["itemId"],
                    "name":      db_item["name"],
                    "itemLevel": db_item.get("itemLevel"),
                    "quality":   db_item.get("quality"),
                    "phase":     db_item.get("contentPhase"),
                    "stats":     db_item.get("stats", {}),
                    "sockets":   db_item.get("sockets"),
                    "score":     round(score, 2),
                    "delta":     round(score - current_score, 2),
                })

            # Sort by score descending, take top_n upgrades (positive delta)
            candidates_list.sort(key=lambda x: x["score"], reverse=True)
            top_upgrades = [c for c in candidates_list if c["delta"] > 0][:top_n]
            top_all      = candidates_list[:top_n]  # top by raw score even if not upgrade

            upgrades[slot_name] = {
                "current": cur_info,
                "upgrades": top_upgrades if top_upgrades else [],
                "top_candidates": top_all,
            }

        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "character":   char_name,
                        "class":       char_class,
                        "spec":        spec,
                        "hit_current": current_hit,
                        "hit_cap":     hit_cap,
                        "draenei":     draenei,
                        "weights_used": weights,
                        "slots": upgrades,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    # ---- get_loot_table -------------------------------------------------
    if name == "get_loot_table":
        loot, lerr = _load_loot()
        if lerr:
            return [types.TextContent(type="text", text=f"❌ {lerr}")]

        source_filter = (args.get("source") or "all").strip().lower()
        zone_filter   = (args.get("zone") or "").strip().lower()
        slot_filter   = (args.get("slot") or "").strip().lower()
        _RATING_ORDER = ["S", "A", "B", "C", "D"]
        min_rating    = args.get("min_rating", "D")
        min_idx       = _RATING_ORDER.index(min_rating) if min_rating in _RATING_ORDER else 4

        _ALIASES = {
            "ssc": "serpentshrine", "serpentshrine cavern": "serpentshrine",
            "tk": "tempest keep", "kara": "karazhan",
            "gruul": "gruul", "mag": "magtheridon",
            "blood furnace": "blood furnace", "slave pens": "slave pens",
        }
        zone_filter = _ALIASES.get(zone_filter, zone_filter)

        def matches(item: dict) -> bool:
            if slot_filter and slot_filter not in item["slot"].lower():
                return False
            if _RATING_ORDER.index(item["mage_rating"]) > min_idx:
                return False
            return True

        results: dict = {}

        # Raids
        if source_filter in ("all", "raid"):
            for zone_name, zone_data in loot.get("raids", {}).items():
                if zone_filter and zone_filter not in zone_name.lower():
                    continue
                found = [i for i in zone_data["all_items"] if matches(i)]
                if found:
                    results[f"[Raid] {zone_name}"] = found

        # Donjons
        if source_filter in ("all", "dungeon"):
            for zone_name, zone_data in loot.get("dungeons", {}).items():
                if zone_filter and zone_filter not in zone_name.lower():
                    continue
                found = [i for i in zone_data["all_items"] if matches(i)]
                if found:
                    results[f"[Donjon] {zone_name}"] = found

        # Craftés
        if source_filter in ("all", "crafted"):
            for set_name, set_data in loot.get("crafted", {}).items():
                if zone_filter and zone_filter not in set_name.lower():
                    continue
                found = [i for i in set_data["items"] if matches(i)]
                if found:
                    results[f"[Crafted] {set_name}"] = found

        # Réputation
        if source_filter in ("all", "reputation"):
            if not zone_filter or "rep" in zone_filter or "vendor" in zone_filter:
                found = [i for i in loot.get("reputation", []) if matches(i)]
                if found:
                    results["[Réputation] Vendeurs TBC"] = found

        if not results:
            return [types.TextContent(type="text", text="Aucun item trouvé pour ces filtres.")]

        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "filters": {
                            "source": source_filter,
                            "zone": args.get("zone"),
                            "slot": args.get("slot"),
                            "min_rating": min_rating,
                        },
                        "results": results,
                        "total_items": sum(len(v) for v in results.values()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    return [types.TextContent(type="text", text=f"❌ Outil inconnu : {name}")]


# ------------------------------------------------------------------ entrypoint

async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
