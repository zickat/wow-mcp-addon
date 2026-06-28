-- CharExport.lua
-- Exporte équipement + talents dans CharExportDB (SavedVariables account-wide).
-- Commande : /exportchar
-- Les données sont flushées sur disque au prochain /reload ou déconnexion.

-- ============================================================
-- Slots inventaire (TBC Classic)
-- ============================================================
local SLOTS = {
    [1]  = "Head",
    [2]  = "Neck",
    [3]  = "Shoulder",
    [4]  = "Shirt",
    [5]  = "Chest",
    [6]  = "Waist",
    [7]  = "Legs",
    [8]  = "Feet",
    [9]  = "Wrist",
    [10] = "Hands",
    [11] = "Finger1",
    [12] = "Finger2",
    [13] = "Trinket1",
    [14] = "Trinket2",
    [15] = "Back",
    [16] = "MainHand",
    [17] = "OffHand",
    [18] = "Ranged",
    [19] = "Tabard",
}

-- ============================================================
-- Export équipement
-- ============================================================
local function ExportEquipment()
    local equipment = {}
    for slotId, slotName in pairs(SLOTS) do
        local link = GetInventoryItemLink("player", slotId)
        if link then
            local itemId   = link:match("item:(%d+)")
            local itemName = link:match("%[(.-)%]")
            equipment[slotName] = {
                slot_id = slotId,
                item_id = tonumber(itemId) or 0,
                name    = itemName or "",
                link    = link,
            }
        end
    end
    return equipment
end

-- ============================================================
-- Export talents (TBC Classic : 3 tabs, rang par rang)
-- ============================================================
local function ExportTalents()
    local tabs = {}
    local numTabs = GetNumTalentTabs()
    for t = 1, numTabs do
        -- GetTalentTabInfo retourne les valeurs dans un ordre qui varie selon la version du client.
        -- On capture tout et on trouve le string (nom de l'arbre) parmi les retours.
        local r1, r2, r3, r4, r5 = GetTalentTabInfo(t)
        local tabName
        for _, v in ipairs({ r1, r2, r3, r4, r5 }) do
            if type(v) == "string" and #v > 2 then
                tabName = v
                break
            end
        end
        tabName = tabName or tostring(r1)

        local tabData = {
            tab          = tabName,
            points_spent = 0,   -- calculé ci-dessous depuis les rangs réels
            talents      = {},
        }
        for i = 1, GetNumTalents(t) do
            local name, _, tier, col, rank, maxRank = GetTalentInfo(t, i)
            if rank and rank > 0 then
                table.insert(tabData.talents, {
                    name     = name,
                    tier     = tier,
                    col      = col,
                    rank     = rank,
                    max_rank = maxRank,
                })
                tabData.points_spent = tabData.points_spent + rank
            end
        end
        table.insert(tabs, tabData)
    end
    return tabs
end

-- ============================================================
-- Export buffs actifs (nom + spell ID pour détecter les buffs stat côté serveur)
-- ============================================================
local function ExportBuffs()
    local buffs = {}
    local i = 1
    while true do
        local name, _, _, _, _, _, _, _, _, _, spellId = UnitBuff("player", i)
        if not name then break end
        table.insert(buffs, { name = name, spell_id = spellId or 0 })
        i = i + 1
    end
    return buffs
end

-- Export stats (TBC Classic)
-- pcall sur chaque appel pour être robuste aux variantes de client
-- ============================================================
local function Safe(fn, ...)
    local ok, v = pcall(fn, ...)
    return ok and v or nil
end

local function ExportStats()
    local s = {}

    -- Stats primaires (valeurs effectives avec buffs)
    local function stat(i)
        local eff = Safe(UnitStat, "player", i)
        return eff or 0
    end
    s.strength  = stat(1)
    s.agility   = stat(2)
    s.stamina   = stat(3)
    s.intellect = stat(4)
    s.spirit    = stat(5)

    -- Ressources
    s.health_max = Safe(UnitHealthMax, "player") or 0
    -- UnitManaMax peut ne pas exister en TBC Classic Anniversary → fallback UnitPowerMax
    s.mana_max   = Safe(UnitManaMax, "player") or Safe(UnitPowerMax, "player", 0) or 0

    -- Spell power par école (1=Phys, 2=Holy, 3=Fire, 4=Nature, 5=Frost, 6=Shadow, 7=Arcane)
    local sp = GetSpellBonusDamage
    s.sp_arcane = Safe(sp, 7) or 0
    s.sp_fire   = Safe(sp, 3) or 0
    s.sp_frost  = Safe(sp, 5) or 0
    s.sp_shadow = Safe(sp, 6) or 0
    s.sp_holy   = Safe(sp, 2) or 0
    s.sp_nature = Safe(sp, 4) or 0

    -- Spell crit % par école
    s.crit_arcane_pct = Safe(GetSpellCritChance, 7) or 0
    s.crit_fire_pct   = Safe(GetSpellCritChance, 3) or 0
    s.crit_frost_pct  = Safe(GetSpellCritChance, 5) or 0

    -- Combat ratings bruts
    -- CR: 6=MeleeHit, 7=RangedHit, 8=SpellHit, 9=MeleeCrit, 10=RangedCrit, 11=SpellCrit,
    --     13=Dodge, 14=Parry, 15=Defense, 16=Block, 18=MeleeHaste, 19=RangedHaste,
    --     20=SpellHaste, 23=Expertise
    local cr = GetCombatRating

    -- Spell
    s.hit_spell_rating   = Safe(cr, 8)  or 0
    s.crit_spell_rating  = Safe(cr, 11) or 0
    s.haste_spell_rating = Safe(cr, 20) or 0

    -- Melee / Ranged
    s.hit_melee_rating    = Safe(cr, 6)  or 0
    s.hit_ranged_rating   = Safe(cr, 7)  or 0
    s.crit_melee_rating   = Safe(cr, 9)  or 0
    s.crit_ranged_rating  = Safe(cr, 10) or 0
    s.haste_melee_rating  = Safe(cr, 18) or 0
    s.haste_ranged_rating = Safe(cr, 19) or 0
    s.expertise_rating    = Safe(cr, 23) or 0

    -- Tank
    s.defense_rating = Safe(cr, 15) or 0
    s.dodge_rating   = Safe(cr, 13) or 0
    s.parry_rating   = Safe(cr, 14) or 0
    s.block_rating   = Safe(cr, 16) or 0

    -- Hit % bonus depuis rating (GetCombatRatingBonus retourne le % si disponible)
    local hitBonus = Safe(GetCombatRatingBonus, 8)
    if hitBonus then
        s.hit_spell_pct = hitBonus
    else
        s.hit_spell_pct = s.hit_spell_rating / 12.615
    end
    s.hit_spell_pct = math.floor(s.hit_spell_pct * 100 + 0.5) / 100

    local hitMeleeBonus = Safe(GetCombatRatingBonus, 6)
    s.hit_melee_pct = hitMeleeBonus
        and (math.floor(hitMeleeBonus * 100 + 0.5) / 100)
        or  math.floor((s.hit_melee_rating / 15.7692) * 100 + 0.5) / 100

    -- Haste % bonus
    local hasteBonus = Safe(GetCombatRatingBonus, 20)
    s.haste_spell_pct = hasteBonus and (math.floor(hasteBonus * 100 + 0.5) / 100) or 0

    -- Attack power (melee)
    do
        local ok, base, pos, neg = pcall(UnitAttackPower, "player")
        s.attack_power = ok and ((base or 0) + (pos or 0) + (neg or 0)) or 0
    end

    -- Attack power (ranged)
    do
        local ok, base, pos, neg = pcall(UnitRangedAttackPower, "player")
        s.ranged_attack_power = ok and ((base or 0) + (pos or 0) + (neg or 0)) or 0
    end

    -- Block value
    s.block_value = Safe(GetShieldBlock) or 0

    -- Expertise (points, pas rating) — GetExpertise() retourne melee, ranged
    do
        local ok, exp_melee = pcall(GetExpertise)
        s.expertise = ok and (exp_melee or 0) or 0
    end

    -- Mana regen (GetManaRegen retourne des valeurs par seconde → ×5 pour MP5)
    local castRegen, noCastRegen = Safe(GetManaRegen) or 0, 0
    if type(castRegen) == "number" then
        s.mp5_casting     = math.floor(castRegen * 5)
    else
        s.mp5_casting = 0
    end
    local ok2, nc = pcall(GetManaRegen)
    if ok2 then
        -- GetManaRegen() retourne 2 valeurs : casting, not casting
        local _, nc2 = GetManaRegen()
        s.mp5_not_casting = math.floor((nc2 or 0) * 5)
    else
        s.mp5_not_casting = 0
    end

    -- Armor : UnitArmor retourne base, posBuff, negBuff, effective
    -- pcall directement pour capturer les 4 valeurs de retour
    do
        local ok, base, _, _, effective = pcall(UnitArmor, "player")
        s.armor = ok and (effective or base or 0) or 0
    end

    -- Résistances (0=Armor, 1=Holy, 2=Fire, 3=Nature, 4=Frost, 5=Shadow, 6=Arcane)
    local function res(i)
        local v = Safe(UnitResistance, "player", i)
        return v or 0
    end
    s.resist_arcane = res(6)
    s.resist_fire   = res(2)
    s.resist_frost  = res(4)
    s.resist_nature = res(3)
    s.resist_shadow = res(5)
    s.resist_holy   = res(1)

    -- Spell penetration (si disponible)
    s.spell_penetration = Safe(GetSpellPenetration) or 0

    return s
end

-- ============================================================
-- Export principal
-- ============================================================
local function DoExport()
    local charName = UnitName("player")
    if not charName then return end

    -- Initialisation de la DB si premier lancement
    CharExportDB                    = CharExportDB or {}
    CharExportDB.characters         = CharExportDB.characters or {}

    CharExportDB.last_active        = charName
    CharExportDB.characters[charName] = {
        exported_at = time(),
        realm       = GetRealmName(),
        class       = select(2, UnitClass("player")),
        level       = UnitLevel("player"),
        equipment   = ExportEquipment(),
        talents     = ExportTalents(),
        stats       = ExportStats(),
        buffs       = ExportBuffs(),
    }

    print("|cff00ff00[CharExport]|r "
        .. charName .. " exporté ("
        .. date("%H:%M:%S")
        .. "). |cffffffffFaites /reload|r pour sauvegarder sur disque.")
end

-- ============================================================
-- Gestion des événements
-- ============================================================
local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
frame:RegisterEvent("PLAYER_TALENT_UPDATE")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")

frame:SetScript("OnEvent", function(self, event)
    if event == "PLAYER_LOGIN" then
        -- Délai court pour que tous les slots soient chargés au login
        C_Timer.After(2, DoExport)
    else
        DoExport()
    end
end)

-- ============================================================
-- Commande slash : /exportchar
-- ============================================================
SLASH_EXPORTCHAR1 = "/exportchar"
SlashCmdList["EXPORTCHAR"] = function()
    DoExport()
end
