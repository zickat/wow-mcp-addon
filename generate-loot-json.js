#!/usr/bin/env node
/**
 * generate-loot-json.js
 * Génère data/loot.json — tous les items TBC utiles pour un mage Arcane.
 * Sources couvertes : raids Phase 2, donjons TBC, métiers (crafted), réputation.
 *
 * Usage : node generate-loot-json.js
 */

const { Items, Zones } = require('wow-classic-items');
const fs   = require('fs');
const path = require('path');

const items = new Items('2.5.1');
const zones = new Zones('2.5.1');

// ── Raids Phase 2 ─────────────────────────────────────────────────────────────
const PHASE2_RAIDS = {
  'Karazhan':             3457,
  "Gruul's Lair":         3923,
  "Magtheridon's Lair":   3836,
  'Serpentshrine Cavern': 3607,
  'Tempest Keep':         3845,
};

// ── Donjons TBC Héroïques (lvl 58-70) ────────────────────────────────────────
const TBC_DUNGEONS = {
  'Hellfire Ramparts':    3562,
  'The Blood Furnace':    3713,
  'The Slave Pens':       3717,
  'The Underbog':         3716,
  'Mana-Tombs':           3792,
  'Sethekk Halls':        3791,
  'Auchenai Crypts':      3790,
  'Old Hillsbrad Foothills': 2367,
};

// ── Items craftés (Tailoring TBC) — pas de source dans la DB ─────────────────
const CRAFTED_ITEMS = {
  'Spellfire': [21846, 21847, 21848],        // Belt, Gloves, Robe
  'Frozen Shadoweave': [21869, 21870, 21871], // Shoulders, Boots, Robe
  'Spellstrike': [24262, 24266],              // Pants, Hood
  'Primal Mooncloth': [21873, 21874, 21875],  // Belt, Shoulders, Robe
};

// ── Blacklist items heal-only (la DB wow-classic-items normalise healing power
//    et spell damage power au même label "spell power" — impossible à distinguer
//    autrement qu'à la main pour les items bien connus)
const HEALER_ONLY_IDS = new Set([
  // Armes heal-only connues
  28771, // Light's Justice (Prince Malchezaar, Kara)
  28522, // Shard of the Virtuous (Maiden, Kara)
  27876, // Will of the Fallen Exarch (Auchenai Crypts)
  24378, // Coilfang Hammer of Renewal (SSC)
  30317, // Cosmic Infuser (SSC)
  30108, // Lightfathom Scepter (SSC)
  29981, // Ethereum Life-Staff
  28216, // Dathrohan's Ceremonial Hammer (Old Hillsbrad)
  24094, // Heart Fire Warhammer
  // Off-hands / bijoux heal-only
  29354, // Light-Touched Stole of Altruism (Auchenai Crypts)
  28213, // Lordaeron Medical Guide (Old Hillsbrad)
  // Capes heal-only
  27946, // Avian Cloak of Feathers (Sethekk Halls — +42 heal / +14 dmg, ratio heal-only)
]);

// ── Filtres mage ──────────────────────────────────────────────────────────────
const MAGE_SLOTS = new Set([
  'Head', 'Neck', 'Shoulder', 'Back', 'Chest', 'Wrist',
  'Hands', 'Waist', 'Legs', 'Feet', 'Finger', 'Trinket',
  'One-Hand', 'Main Hand', 'Off Hand', 'Held In Off-hand',
  'Two-Hand', 'Wand',
]);

// Mages TBC : dagues, épées 1H, bâtons, baguettes uniquement
// Pas de masses, haches, armes de pugilat, lances
const MAGE_WEAPON_SUBCLASSES = new Set(['Dagger', 'Staff', 'One-Handed Sword', 'Wand']);

function isMageUseful(item, minIlvl = 95) {
  if (HEALER_ONLY_IDS.has(item.itemId)) return false;
  if (!MAGE_SLOTS.has(item.slot)) return false;
  if (item.class === 'Armor' && !['Cloth', 'Miscellaneous'].includes(item.subclass)) return false;
  if (item.class === 'Weapon' && !MAGE_WEAPON_SUBCLASSES.has(item.subclass)) return false;
  if (['Common', 'Poor'].includes(item.quality)) return false;
  if (item.itemLevel < minIlvl) return false;

  // Heuristique healer : SP + (MP5 ou Spirit) sans aucun stat offensif = heal-only
  // Items DPS caster ont toujours au moins un de : crit, hit, haste, int
  const stats = extractStats(item);
  if (stats.sp > 0 && stats.crit === 0 && stats.hit === 0 && stats.haste === 0 && stats.int === 0) {
    if (stats.mp5 > 0 || stats.spi > 0) return false;
  }

  return true;
}

// ── Stats ──────────────────────────────────────────────────────────────────────
function extractStats(item) {
  const s = { sp: 0, hit: 0, crit: 0, haste: 0, int: 0, mp5: 0, spi: 0 };
  for (const t of (item.tooltip || [])) {
    const l = t.label || '';
    const m = re => { const r = l.match(re); return r ? parseInt(r[1]) : 0; };
    s.sp    += m(/increases spell power by (\d+)/i);
    s.hit   += m(/improves hit rating by (\d+)/i);
    s.crit  += m(/improves critical strike rating by (\d+)/i);
    s.haste += m(/improves haste rating by (\d+)/i) + m(/haste rating by (\d+)/i);
    s.int   += m(/\+(\d+) Intellect/);
    s.mp5   += m(/(\d+) mana per 5 sec/i);
    s.spi   += m(/\+(\d+) Spirit/);
  }
  return s;
}

function mageRating(stats) {
  if (stats.sp >= 40 && stats.hit > 0) return 'S';
  if (stats.sp >= 30 && stats.hit > 0) return 'A';
  if (stats.sp >= 40)                   return 'A';
  if (stats.sp >= 20)                   return 'B';
  if (stats.sp > 0 || stats.hit > 0)   return 'C';
  return 'D';
}

function formatItem(item, extra = {}) {
  const stats = extractStats(item);
  return {
    item_id:     item.itemId,
    name:        item.name,
    slot:        item.slot,
    item_level:  item.itemLevel,
    quality:     item.quality,
    stats,
    mage_rating: mageRating(stats),
    wowhead:     `https://www.wowhead.com/tbc/item=${item.itemId}`,
    ...extra,
  };
}

function groupByBoss(itemList) {
  const byBoss = {};
  for (const item of itemList) {
    const boss = item.boss || 'Unknown';
    if (!byBoss[boss]) byBoss[boss] = [];
    byBoss[boss].push(item);
  }
  return byBoss;
}

// ── Génération ────────────────────────────────────────────────────────────────
const output = {
  generated_at: new Date().toISOString(),
  version:      '2.5.1',
  raids:        {},
  dungeons:     {},
  crafted:      {},
  reputation:   [],
};

// -- Raids
for (const [zoneName, zoneId] of Object.entries(PHASE2_RAIDS)) {
  const zoneItems = items
    .filter(i => i.source?.zone === zoneId && i.source?.category === 'Boss Drop' && isMageUseful(i))
    .sort((a, b) => b.itemLevel - a.itemLevel)
    .map(i => formatItem(i, {
      boss:        i.source.name || 'Unknown',
      drop_chance: i.source.dropChance ? parseFloat((i.source.dropChance * 100).toFixed(2)) : null,
    }));

  output.raids[zoneName] = {
    zone_id:    zoneId,
    item_count: zoneItems.length,
    by_boss:    groupByBoss(zoneItems),
    all_items:  zoneItems,
  };
  console.log(`✓ [Raid]    ${zoneName.padEnd(25)} — ${zoneItems.length} items`);
}

// -- Donjons
for (const [zoneName, zoneId] of Object.entries(TBC_DUNGEONS)) {
  const zoneItems = items
    .filter(i => i.source?.zone === zoneId && i.source?.category === 'Boss Drop' && isMageUseful(i))
    .sort((a, b) => b.itemLevel - a.itemLevel)
    .map(i => formatItem(i, {
      boss:        i.source.name || 'Unknown',
      drop_chance: i.source.dropChance ? parseFloat((i.source.dropChance * 100).toFixed(2)) : null,
    }));

  output.dungeons[zoneName] = {
    zone_id:    zoneId,
    item_count: zoneItems.length,
    by_boss:    groupByBoss(zoneItems),
    all_items:  zoneItems,
  };
  console.log(`✓ [Donjon]  ${zoneName.padEnd(25)} — ${zoneItems.length} items`);
}

// -- Craftés
for (const [setName, ids] of Object.entries(CRAFTED_ITEMS)) {
  const setItems = items
    .filter(i => ids.includes(i.itemId))
    .sort((a, b) => b.itemLevel - a.itemLevel)
    .map(i => formatItem(i, { set: setName, profession: 'Tailoring' }));

  output.crafted[setName] = {
    profession: 'Tailoring',
    item_count: setItems.length,
    items:      setItems,
  };
  console.log(`✓ [Crafted] ${setName.padEnd(25)} — ${setItems.length} items`);
}

// -- Réputation / Vendors TBC (ilvl 100-135, pas PvP, avec SP)
const PVP_WORDS = ['general','sergeant','lieutenant','commander','marshal','warlord','gladiator'];
const repItems = items.filter(i => {
  if (i.source?.category !== 'Vendor') return false;
  if (!isMageUseful(i, 100)) return false;
  if (i.itemLevel > 135) return false;         // Cap TBC Phase 5
  if (PVP_WORDS.some(p => i.name.toLowerCase().includes(p))) return false;
  // Garder seulement si a du SP
  return (i.tooltip || []).some(t => /increases spell power by/i.test(t.label || ''));
});

output.reputation = repItems
  .sort((a, b) => b.itemLevel - a.itemLevel)
  .map(i => formatItem(i, {
    vendor: i.source?.name || 'Unknown',
  }));

console.log(`✓ [Rep]     ${'Vendeurs Sha\'tar/Aldor/…'.padEnd(25)} — ${output.reputation.length} items`);

// -- Stats globales
const total = Object.values(output.raids).reduce((n, z) => n + z.item_count, 0)
            + Object.values(output.dungeons).reduce((n, z) => n + z.item_count, 0)
            + Object.values(output.crafted).reduce((n, z) => n + z.item_count, 0)
            + output.reputation.length;

const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir);
fs.writeFileSync(path.join(dataDir, 'loot.json'), JSON.stringify(output, null, 2));
console.log(`\n✅ data/loot.json — ${total} items total`);
