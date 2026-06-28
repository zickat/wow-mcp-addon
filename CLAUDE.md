# WoW TBC Classic — Mage Lvl 70

## Contexte du projet
- Jeu : World of Warcraft Burning Crusade Classic **Anniversary**
- Serveur : Thunderstrike
- Personnage : Zickatmago — Mage Gnome niveau 70
- Spé : Arcane
- **Phase actuelle : Phase 2 (SSC / The Eye)**
- Objectif : progression endgame (raids, BiS, optimisation)

## MCP — Données live du personnage

Un serveur MCP local expose les données de Zickatmago en temps réel via l'addon **CharExport**.

**Règle : toujours appeler `get_character_info` en début de conversation** avant de donner un conseil sur l'équipement, les talents ou les upgrades. Les données statiques ci-dessous sont une référence de secours uniquement.

Outils disponibles :
- `get_character_info` — équipement complet (item_id, nom, link) + talents avec rangs réels + stats
- `get_last_update` — horodatage du dernier export (vérifier la fraîcheur si doute)
- `get_upgrades` — upgrades par slot pour n'importe quelle classe/spé (générique). Détecte la spé depuis les talents, applique les poids stat, compare vs gear actuel. Paramètres : `slot`, `min_ilvl`, `draenei`, `top_n`, `spec_override`.
- `get_item_info` — stats brutes d'un item par item_id (base DB générique, tous items TBC reqLevel 55-70)
- `get_loot_table` — *(legacy)* liste filtrée d'items pour Mage Arcane avec ratings S/A/B/C/D

Workflow de mise à jour en jeu : `/exportchar` → `/reload`

---

## Personnage

### Professions
- Tailoring : 368 (viser Spellfire set si pas encore craftés)
- Enchanting : 1 → **à monter en priorité** (ring +12 SP x2 = 24 SP gratuits)

### Talents (40/0/21) (⚠️ référence statique — utiliser `get_character_info` pour les rangs live)
`25000523000301503301250-0000000000000000000000-0535000310030010000000`

**Arcane (40 pts) :**
- Arcane Subtlety 2/2
- Arcane Focus 5/5 (+2% hit arcane)
- Arcane Concentration 5/5 (Clearcasting proc)
- Arcane Meditation 3/3
- Presence of Mind 1/1
- Arcane Instability 3/3
- Mind Mastery 5/5 (15% int → SP)
- Spell Power 2/2
- Harmonisation de la magie 2/2 → **à déplacer** (talent inutile en raid)
- Arcane Empowerment 5/5

**Frost (21 pts) — AoE farm :**
- Ice Shards 5/5
- Cold Snap 1/1
- Improved Blizzard 3/3
- Shatter 1/1
- Elemental Precision 3/3

**Manque :** Projectiles des arcanes surpuissants (Empowered Arcane Missiles) — à considérer si respec

### Stats actuelles (⚠️ référence statique — utiliser `get_character_info` pour les données live)
- Spell Power : 879
- Hit arcane : 5.79% (73 rating — manque ~10.2% pour cap à 16%)
- Crit : 21.46%
- Intelligence : 600
- Spirit : 219
- MP5 en combat : 250

### Gear actuel (⚠️ référence statique — utiliser `get_character_info` pour les données live)

| Slot | Item | iLvl | Notes |
|------|------|-------|-------|
| Tête | Collar of the Aldor | 120 | Glyph of Power |
| Cou | Torc of the Sethekk Prophet | 115 | |
| Épaules | Mana-Etched Spaulders | 115 | Inscription of the Orb |
| Cape | Ogre Slayer's Cover | **100** | **Pièce la plus faible** |
| Torse | Vestments of the Aldor | 120 | |
| Poignets | Harbinger Bands | 115 | |
| Mains | Gloves of the Aldor | 120 | |
| Ceinture | Belt of Divine Inspiration | 125 | |
| Jambes | Trial-Fire Trousers | 115 | |
| Pieds | Sigil-Laced Boots | 115 | |
| Bague 1 | Spectral Band of Innervation | 115 | |
| Bague 2 | Violet Signet | 120 | |
| Trinket 1 | Icon of the Silver Crescent | 110 | +53 SP passif |
| Trinket 2 | Xi'ri's Gift | 115 | |
| Main droite | Greatsword of Horrid Dreams | 115 | Héroïque Auchindoun |
| Main gauche | Jewel of Infinite Possibilities | 115 | |
| Baguette | Nethekurse's Rod of Torment | 109 | |

**Gemmes à remplacer :** Blood Garnet (+6 SP) → Runed Living Ruby (+9 SP) sur plusieurs pièces

### Performances raid (logs analysés)
- Lurker Below : ~577 DPS
- Leotheras : ~560 DPS
- Magtheridon (rotation corrigée) : **755 DPS** (sans consommables)

**Problème identifié et corrigé :** Arcane Missiles absent de la rotation → macro `/stopcasting` + Arcane Missiles sur proc Clearcasting

**Rotation correcte :**
```
Arcane Blast → Arcane Blast → Arcane Blast
Clearcasting proc → /stopcasting → Arcane Missiles
Mana 50% → Mana Gem
Mana 40% → Super Mana Potion
Mana 30% → Dark Rune (Rune sombre)
Mana bas → Evocation (à 30%, pas à 0%)
```

### Consommables à utiliser en raid
- Flask of Blinding Light (+80 SP arcane/feu/sacré)
- Blackened Basilisk ou Crunchy Serpent (+23 SP)
- Brilliant Wizard Oil sur arme (+36 SP)
- Super Mana Potion (2 min CD)
- Dark Rune / Rune sombre (15 min CD, indépendant des gems)
- Mana Gem (15 min CD, indépendant des runes)

## Règles générales

### Spécificité TBC Classic Anniversary
- Toujours distinguer TBC Classic (2.4.3) du retail ou du WotLK Classic — les mécaniques, stats et BiS diffèrent
- **Serveurs Anniversary** : même patch 2.4.3 mais calendrier de phases différent — se baser sur la phase actuelle du serveur
- Les caps de stats TBC à retenir : hit cap spell = 202 (16%) PvE boss, 76 (6%) avec Draenei dans le groupe
- Utiliser les données de Phase 2 pour le BiS (SSC + The Eye disponibles)
- Contenu disponible : Karazhan, Gruul, Magtheridon, SSC, The Eye

### Réponses et conseils
- Être précis sur la spé Arcane — c'est la spé du personnage
- Mentionner les talents clés : Arcane Concentration, Mind Mastery, Arcane Potency, Presence of Mind
- Pour les rotations, donner des priorités claires et courtes
- Pour le BiS, toujours indiquer la source (boss, faction, craft) et confirmer dispo Phase 2
- **Ne pas inventer les stats ou sources d'items SSC** — toujours vérifier via le fichier loot-ssc.md

### Ressources de référence
- Wowhead TBC Classic pour items, talents, quêtes
- Seventyupgrades.com pour le BiS
- `guides/loot-ssc.md` — liste complète des loots SSC avec utilité mage
- `guides/bis-pre-raid-arcane.md` — BiS pré-raid Arcane Phase 2

### Script build-items-db.js
Génère `data/items_db.json` — base générique de tous les items TBC (reqLevel 55-70) avec stats brutes parsées depuis les tooltips du package `wow-classic-items`. Utilisée par `get_upgrades` et `get_item_info`.

```bash
node build-items-db.js              # tous les items (reqLevel 55-70)
node build-items-db.js --ilvl 100   # seulement iLvl >= 100
node build-items-db.js --ids 29076,28530  # items spécifiques
```

Le fichier `data/stat_weights.json` contient les poids stat par classe/spé pour les 9 classes TBC (Mage/Warlock/Priest/Druid/Shaman/Paladin/Hunter/Rogue/Warrior). Éditable manuellement.

### Script fetch-dungeon-loot.js
Génère automatiquement un guide loot markdown filtré pour mage à partir du package npm `wow-classic-items`.

**Prérequis (une seule fois) :**
```bash
npm install wow-classic-items
```

**Usage :**
```bash
node fetch-dungeon-loot.js                        # liste les zones disponibles
node fetch-dungeon-loot.js "Serpentshrine Cavern" # génère guides/loot-serpentshrine-cavern.md
node fetch-dungeon-loot.js "Mana-Tombs"           # donjon
node fetch-dungeon-loot.js all-raids              # tous les raids TBC
node fetch-dungeon-loot.js all                    # donjons + raids
```

**Raids disponibles :** Karazhan, Gruul's Lair, Magtheridon's Lair, Serpentshrine Cavern, Tempest Keep, Zul'Aman, Black Temple, Hyjal Summit, Sunwell Plateau

**Limitations :**
- Tokens T5/T6 apparaissent sans stats (normal — les stats sont sur l'item final, pas le token)
- Quelques donjons TBC absents de la base (Shadow Labyrinth, Steamvault, Botanica, Arcatraz, Mechanar)
- Les guides générés automatiquement sont un point de départ — vérifier les pièces clés sur Wowhead

### Format des fichiers
- Guides : `.md` dans le dossier `/guides/`
- Listes BiS : `.xlsx` ou `.md` selon le besoin
- Notes rapides : `.md` à la racine

### Ce projet couvre
- Listes BiS par phase (focus Phase 2 actuellement)
- Rotations et priorités Arcane
- Gestion des consommables (potions, flacons, nourriture)
- Macros et addons utiles
- Progression de contenu (SSC, TK en cours)
- PvP éventuel (arènes, BG)
