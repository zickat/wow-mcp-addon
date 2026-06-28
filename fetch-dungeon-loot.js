#!/usr/bin/env node
/**
 * fetch-dungeon-loot.js
 * Génère un guide loot markdown pour un donjon TBC Classic
 *
 * Usage :
 *   node fetch-dungeon-loot.js                    → liste les donjons disponibles
 *   node fetch-dungeon-loot.js "Shadow Labyrinth" → génère guides/loot-shadow-labyrinth.md
 *   node fetch-dungeon-loot.js all                → génère un fichier par donjon TBC
 */

const { Items, Zones } = require('wow-classic-items');
const fs = require('fs');
const path = require('path');

const items = new Items('2.5.1');
const zones  = new Zones('2.5.1');

// ── Donjons TBC (lvl 58-70) ──────────────────────────────────────────────────
const TBC_DUNGEONS = zones.filter(z =>
  z.category === 'Dungeon' &&
  z.level &&
  z.level[1] >= 58 && z.level[1] <= 70
);

// ── Raids TBC (lvl 70-73) ────────────────────────────────────────────────────
const TBC_RAIDS = zones.filter(z =>
  z.category === 'Raid' &&
  z.level &&
  z.level[0] >= 70 && z.level[1] <= 73
);

const ALL_TBC = [...TBC_DUNGEONS, ...TBC_RAIDS];

// ── Slots intéressants pour un mage ─────────────────────────────────────────
const MAGE_SLOTS = new Set([
  'Head', 'Neck', 'Shoulder', 'Back', 'Chest', 'Wrist',
  'Hands', 'Waist', 'Legs', 'Feet', 'Finger', 'Trinket',
  'One-Hand', 'Main Hand', 'Off Hand', 'Held In Off-hand',
  'Two-Hand', 'Wand', 'Ranged'
]);

// Sous-classes armure utiles pour mage
const MAGE_ARMOR = new Set(['Cloth', 'Miscellaneous']);

function isMageUseful(item) {
  if (!MAGE_SLOTS.has(item.slot)) return false;
  if (item.class === 'Armor' && !MAGE_ARMOR.has(item.subclass)) return false;
  if (item.quality === 'Common' || item.quality === 'Poor') return false;
  return true;
}

function extractStats(item) {
  const stats = { sp: 0, hit: 0, crit: 0, haste: 0, int: 0, mp5: 0 };
  for (const t of (item.tooltip || [])) {
    if (!t.label) continue;
    const l = t.label;
    const spMatch = l.match(/spell power by (\d+)/i);
    if (spMatch) stats.sp += parseInt(spMatch[1]);
    const hitMatch = l.match(/spell hit rating by (\d+)/i);
    if (hitMatch) stats.hit += parseInt(hitMatch[1]);
    const critMatch = l.match(/critical strike rating by (\d+)/i);
    if (critMatch) stats.crit += parseInt(critMatch[1]);
    const hasteMatch = l.match(/haste rating by (\d+)/i);
    if (hasteMatch) stats.haste += parseInt(hasteMatch[1]);
    const intMatch = l.match(/\+(\d+) Intellect/);
    if (intMatch) stats.int += parseInt(intMatch[1]);
    const mp5Match = l.match(/(\d+) mana per 5/i);
    if (mp5Match) stats.mp5 += parseInt(mp5Match[1]);
  }
  return stats;
}

function getStatLine(item) {
  const s = extractStats(item);
  const parts = [];
  if (s.sp)    parts.push(`+${s.sp} SP`);
  if (s.hit)   parts.push(`+${s.hit} Hit`);
  if (s.crit)  parts.push(`+${s.crit} Crit`);
  if (s.haste) parts.push(`+${s.haste} Haste`);
  if (s.int)   parts.push(`+${s.int} Int`);
  if (s.mp5)   parts.push(`+${s.mp5} MP5`);
  return parts.length ? parts.join(', ') : '—';
}

function rateMageItem(item) {
  const s = extractStats(item);
  const spThreshold = item.slot === 'Ranged' ? 10 : 20; // Baguettes ont moins de SP
  if (s.sp >= spThreshold && s.hit > 0) return '✅ Top pièce';
  if (s.sp >= spThreshold)               return '✅ Bonne pièce';
  if (s.sp > 0 || s.hit > 0)            return '⚠️ Situationnel';
  if (s.crit > 0 && s.int > 0)          return '⚠️ Situationnel';
  return '❌ Peu utile';
}

function generateMarkdown(zone) {
  const zoneItems = items
    .filter(i =>
      i.source?.zone === zone.id &&
      i.source?.category === 'Boss Drop' &&
      isMageUseful(i) &&
      i.itemLevel >= 95
    )
    .sort((a, b) => b.itemLevel - a.itemLevel);

  if (zoneItems.length === 0) {
    return `# Loot ${zone.name} — Mage Arcane\n\n> Aucun item intéressant pour mage trouvé dans la base.\n`;
  }

  // Grouper par boss
  const byBoss = {};
  for (const item of zoneItems) {
    const boss = item.source.name || 'Inconnu';
    if (!byBoss[boss]) byBoss[boss] = [];
    byBoss[boss].push(item);
  }

  let md = `# Loot ${zone.name} — Mage Arcane\n`;
  md += `> Généré avec wow-classic-items (TBC 2.5.1) | iLvl ≥ 95, Cloth/Bijoux seulement\n`;
  md += `> Marquage : ✅ Bonne pièce | ⚠️ Situationnel | ❌ Peu utile\n\n---\n\n`;

  for (const [boss, bossItems] of Object.entries(byBoss)) {
    md += `## ${boss}\n\n`;
    md += `| Item | iLvl | Slot | Stats clés | Mage ? |\n`;
    md += `|------|------|------|-----------|--------|\n`;
    for (const item of bossItems) {
      const wowheadLink = `[${item.name}](https://www.wowhead.com/tbc/item=${item.itemId})`;
      const stats = getStatLine(item);
      const rating = rateMageItem(item);
      const dropChance = item.source.dropChance
        ? ` (${(item.source.dropChance * 100).toFixed(1)}%)`
        : '';
      md += `| **${wowheadLink}**${dropChance} | ${item.itemLevel} | ${item.slot} | ${stats} | ${rating} |\n`;
    }
    md += '\n';
  }

  return md;
}

// ── Main ─────────────────────────────────────────────────────────────────────
const arg = process.argv[2];

if (!arg) {
  console.log('\nDonjons TBC disponibles :\n');
  TBC_DUNGEONS.forEach(z => console.log(`  - ${z.name} (lvl ${z.level[0]}-${z.level[1]})`));
  console.log('\nRaids TBC disponibles :\n');
  TBC_RAIDS.forEach(z => console.log(`  - ${z.name} (lvl ${z.level[0]}-${z.level[1]})`));
  console.log('\nUsage : node fetch-dungeon-loot.js "Nom du donjon ou raid"');
  console.log('        node fetch-dungeon-loot.js all         → donjons + raids');
  console.log('        node fetch-dungeon-loot.js all-raids   → raids seulement\n');
  process.exit(0);
}

const guidesDir = path.join(__dirname, 'guides');
if (!fs.existsSync(guidesDir)) fs.mkdirSync(guidesDir);

if (arg === 'all' || arg === 'all-raids') {
  const list = arg === 'all-raids' ? TBC_RAIDS : ALL_TBC;
  let count = 0;
  for (const zone of list) {
    const md = generateMarkdown(zone);
    const filename = 'loot-' + zone.name.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md';
    const filepath = path.join(guidesDir, filename);
    fs.writeFileSync(filepath, md);
    const itemCount = (md.match(/\| \*\*/g) || []).length;
    console.log(`✓ ${zone.name} → guides/${filename} (${itemCount} items)`);
    count++;
  }
  console.log(`\n${count} fichiers générés dans guides/`);
} else {
  const zone = ALL_TBC.find(z =>
    z.name.toLowerCase().includes(arg.toLowerCase())
  );
  if (!zone) {
    console.error(`Donjon "${arg}" introuvable. Lance le script sans argument pour voir la liste.`);
    process.exit(1);
  }
  const md = generateMarkdown(zone);
  const filename = 'loot-' + zone.name.toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md';
  const filepath = path.join(guidesDir, filename);
  fs.writeFileSync(filepath, md);
  const itemCount = (md.match(/\| \*\*/g) || []).length;
  console.log(`✓ ${zone.name} → guides/${filename} (${itemCount} items)`);
}
