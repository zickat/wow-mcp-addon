# CharExport + WoW MCP — Guide d'installation

Addon WoW TBC Classic Anniversary + serveur MCP local pour analyser ton équipement et tes upgrades avec Claude.

Fonctionne pour **toutes les classes et spécialisations** (Mage, Warrior, Rogue, Priest, Druid, Shaman, Paladin, Hunter, Warlock).

---

## Ce que ça fait

- `/exportchar` en jeu → exporte ton équipement, tes talents et tes stats
- Le serveur MCP local expose ces données à Claude
- Claude peut alors suggérer tes **meilleurs upgrades par slot**, en tenant compte de ta classe, ta spé et ton hit cap actuel

---

## Prérequis

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Claude Desktop** — [claude.ai/download](https://claude.ai/download)
- **World of Warcraft TBC Classic Anniversary** installé

---

## 1. Copier l'addon

Copie le dossier `CharExport/` dans ton dossier AddOns WoW :

**macOS :**
```
/Applications/World of Warcraft/_classic_/Interface/AddOns/CharExport/
```

**Windows :**
```
C:\Program Files (x86)\World of Warcraft\_classic_\Interface\AddOns\CharExport\
```

Lance WoW, active l'addon dans la liste des AddOns au login.

---

## 2. Installer le serveur MCP

Copie ce dossier de projet entier sur ton ordi (demande à ton mate de te le partager).

Dans un terminal, depuis la racine du projet :

```bash
pip install -r wow-mcp/requirements.txt
```

---

## 3. Configurer Claude Desktop

Ouvre le fichier de config Claude Desktop :

**macOS :** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows :** `%APPDATA%\Claude\claude_desktop_config.json`

Ajoute le bloc suivant dans `mcpServers` (remplace le chemin par l'emplacement réel du projet) :

```json
{
  "mcpServers": {
    "wow-char-export": {
      "command": "python3",
      "args": ["/chemin/vers/wow-tbc/wow-mcp/server.py"]
    }
  }
}
```

**Windows — remplace `python3` par `python` :**
```json
{
  "mcpServers": {
    "wow-char-export": {
      "command": "python",
      "args": ["C:\\chemin\\vers\\wow-tbc\\wow-mcp\\server.py"]
    }
  }
}
```

Redémarre Claude Desktop.

---

## 4. Exporter ton personnage en jeu

1. Connecte-toi sur ton perso
2. Tape `/exportchar` dans le chat (ou `/reload`)
3. L'addon exporte automatiquement à chaque login, changement de talent ou d'équipement

À faire à chaque fois que tu changes de gear ou de talents.

---

## 5. Utiliser avec Claude

Dans Claude Desktop, tu peux maintenant demander :

- **"Quels sont mes meilleurs upgrades pour la cape ?"**
- **"Analyse mon gear complet en Fury Warrior"**
- **"Est-ce que je suis cap hit spell ?"**
- **"Compare mes deux rings et dis-moi lequel est le mieux"**
- **"Liste tous les persos exportés"** (si plusieurs alts)

Claude détecte automatiquement ta classe et ta spé depuis tes talents.

---

## Plusieurs alts / plusieurs persos

Le SavedVariables accumule tous les persos du compte qui ont fait `/exportchar`. Pour interroger un alt spécifique, dis à Claude :

> "Regarde les upgrades de mon Warrior Grontar"

---

## Dépannage

**Claude dit que le fichier est introuvable**

L'addon n'a pas encore été flashé sur disque. En jeu, tape `/reload`. Si ça ne suffit pas, crée un fichier `.env` dans le dossier `wow-mcp/` :

```
WOW_SAVED_VARS_PATH=/chemin/complet/vers/CharExport.lua
```

Le chemin complet ressemble à :
- **macOS :** `/Applications/World of Warcraft/_classic_/WTF/Account/TON_COMPTE/SavedVariables/CharExport.lua`
- **Windows :** `C:\Program Files (x86)\World of Warcraft\_classic_\WTF\Account\TON_COMPTE\SavedVariables\CharExport.lua`

**Les données semblent vieilles**

Vérifie avec Claude : *"Quand est-ce que mes données ont été exportées ?"* — il te donnera l'horodatage. Si c'est vieux, refais `/exportchar` puis `/reload` en jeu.

---

## Caps de stats (référence rapide)

| Stat | Cap |
|------|-----|
| Hit spell (sans Draenei) | 202 rating (16%) |
| Hit spell (avec Draenei) | 189 rating (15%) |
| Hit melee (sans Draenei) | 142 rating (9%) |
| Expertise soft cap | 26 pts = 214 rating |
