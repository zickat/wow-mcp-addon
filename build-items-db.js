#!/usr/bin/env node
/**
 * build-items-db.js
 * Génère data/items_db.json à partir du package wow-classic-items.
 * Parse les labels tooltip pour extraire les stats brutes structurées.
 *
 * Usage :
 *   node build-items-db.js              # tous les items TBC reqLevel 60-70
 *   node build-items-db.js --ilvl 100   # seulement iLvl >= 100
 *   node build-items-db.js --ids 29076,28530  # items spécifiques par ID
 */

const fs   = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const OUT_PATH = path.join(__dirname, "data", "items_db.json");

const args = process.argv.slice(2);
const minIlvl   = parseInt(args[args.findIndex(a => a === "--ilvl") + 1] || "0") || 0;
const idsFlag   = args.find(a => a.startsWith("--ids"));
const filterIds = idsFlag ? new Set(idsFlag.split("=")[1].split(",").map(Number)) : null;

// ---------------------------------------------------------------------------
// Stat parser — extracts numeric stats from tooltip label strings
// ---------------------------------------------------------------------------

/**
 * Mappings : regex → stat key
 * Order matters : more specific patterns first.
 */
const STAT_PATTERNS = [
  // Primary stats
  [/\+(\d+)\s+Strength/i,                        "strength"],
  [/\+(\d+)\s+Agility/i,                         "agility"],
  [/\+(\d+)\s+Stamina/i,                         "stamina"],
  [/\+(\d+)\s+Intellect/i,                       "intellect"],
  [/\+(\d+)\s+Spirit/i,                          "spirit"],

  // Spell ratings
  [/spell power by (\d+)/i,                      "spellPower"],
  [/spell haste rating by (\d+)/i,               "hasteRating"],
  [/haste rating by (\d+)/i,                     "hasteRating"],
  [/spell hit rating by (\d+)/i,                 "spellHitRating"],
  [/spell critical strike rating by (\d+)/i,     "spellCritRating"],
  [/spell penetration by (\d+)/i,                "spellPenetration"],

  // Melee/ranged ratings (used for non-caster classes)
  [/critical strike rating by (\d+)/i,           "critRating"],
  [/hit rating by (\d+)/i,                       "hitRating"],
  [/attack power by (\d+)/i,                     "attackPower"],
  [/armor penetration by (\d+)/i,                "armorPenetration"],
  [/expertise rating by (\d+)/i,                 "expertise"],
  [/parry rating by (\d+)/i,                     "parryRating"],
  [/dodge rating by (\d+)/i,                     "dodgeRating"],
  [/defense rating by (\d+)/i,                   "defenseRating"],
  [/block rating by (\d+)/i,                     "blockRating"],
  [/block value by (\d+)/i,                      "blockValue"],

  // Mana regen
  [/Restores? (\d+) mana per 5 sec/i,            "mp5"],

  // Armor (from tooltip line like "164 Armor")
  [/^(\d+)\s+Armor$/i,                           "armor"],
];

/**
 * Parse a single item's tooltip array into a flat stats object.
 * Returns only stats with value > 0.
 */
function parseStats(tooltip) {
  if (!tooltip || !Array.isArray(tooltip)) return {};
  const stats = {};

  for (const entry of tooltip) {
    const label = (entry.label || "").trim();
    if (!label) continue;

    for (const [regex, key] of STAT_PATTERNS) {
      const match = label.match(regex);
      if (match) {
        const val = parseInt(match[1], 10);
        if (!isNaN(val) && val > 0) {
          // Accumulate (e.g. two "hit rating" lines on same item)
          stats[key] = (stats[key] || 0) + val;
        }
        break; // first matching pattern wins for this label line
      }
    }
  }
  return stats;
}

/**
 * Extract gem socket count from tooltip.
 * Returns e.g. { Red: 1, Blue: 2, Yellow: 0, Meta: 1 }
 */
function parseSockets(tooltip) {
  if (!tooltip) return {};
  const sockets = {};
  for (const entry of tooltip) {
    const label = (entry.label || "").trim();
    const m = label.match(/^(Red|Blue|Yellow|Meta|Prismatic)\s+Socket$/i);
    if (m) {
      const color = m[1];
      sockets[color] = (sockets[color] || 0) + 1;
    }
  }
  return Object.keys(sockets).length ? sockets : undefined;
}

/**
 * Extract drop source from tooltip (set name, phase, etc.)
 * Returns a best-effort source string.
 */
function parseSource(tooltip) {
  if (!tooltip) return null;
  // Look for "Dropped by", "Sold by", "Quest" etc.
  // The package doesn't always include this — return undefined if not found.
  return undefined;
}

// ---------------------------------------------------------------------------
// Slot normalisation — map tooltip label to canonical slot name
// ---------------------------------------------------------------------------
const SLOT_MAP = {
  "head": "Head", "helm": "Head",
  "neck": "Neck", "necklace": "Neck",
  "shoulder": "Shoulder", "shoulders": "Shoulder",
  "back": "Back", "cloak": "Back",
  "chest": "Chest",
  "wrist": "Wrist", "wrists": "Wrist", "bracers": "Wrist",
  "hands": "Hands", "gloves": "Hands",
  "waist": "Waist", "belt": "Waist",
  "legs": "Legs", "pants": "Legs",
  "feet": "Feet", "boots": "Feet",
  "finger": "Finger", "ring": "Finger",
  "trinket": "Trinket",
  "main hand": "MainHand",
  "one-hand": "OneHand",
  "off hand": "OffHand",
  "two-hand": "TwoHand",
  "ranged": "Ranged",
  "relic": "Relic",
  "wand": "Ranged",
};

function normaliseSlot(rawSlot) {
  if (!rawSlot) return rawSlot;
  return SLOT_MAP[rawSlot.toLowerCase()] || rawSlot;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
const { Items } = require("wow-classic-items");
const allItems = Object.values(new Items());

let candidates = allItems.filter(item =>
  item.requiredLevel >= 55 &&  // include some lvl 55+ blues for pre-raid
  item.requiredLevel <= 70
);

if (filterIds) {
  candidates = allItems.filter(i => filterIds.has(i.itemId));
}

if (minIlvl > 0) {
  candidates = candidates.filter(i => (i.itemLevel || 0) >= minIlvl);
}

console.log(`Processing ${candidates.length} items…`);

const db = {};

for (const item of candidates) {
  const stats = parseStats(item.tooltip);

  // Skip items with no relevant stats (e.g. quest items, tokens, purely cosmetic)
  if (Object.keys(stats).length === 0 && !filterIds) continue;

  const sockets = parseSockets(item.tooltip);

  const entry = {
    itemId:        item.itemId,
    name:          item.name,
    itemLevel:     item.itemLevel || 0,
    requiredLevel: item.requiredLevel || 0,
    quality:       item.quality,
    slot:          normaliseSlot(item.slot),
    subclass:      item.subclass,
    contentPhase:  item.contentPhase,
    stats,
  };

  if (sockets)              entry.sockets = sockets;
  if (item.uniqueName)      entry.uniqueName = item.uniqueName;

  db[item.itemId] = entry;
}

const count = Object.keys(db).length;
fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
fs.writeFileSync(OUT_PATH, JSON.stringify(db, null, 2), "utf-8");

console.log(`✅  ${count} items écrits dans ${OUT_PATH}`);
console.log(`    Taille : ${(fs.statSync(OUT_PATH).size / 1024 / 1024).toFixed(1)} MB`);
