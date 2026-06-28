# WoW TBC Classic — Analyseur de gear avec Claude

Cet outil permet à Claude (IA) d'analyser ton personnage WoW en temps réel : upgrades par slot, hit cap, comparaison d'items, conseil BiS — pour toutes les classes et spés TBC Classic Anniversary.

---

## Ce que ça fait concrètement

Tu poses une question à Claude dans l'appli Claude Desktop :

> *"Quels sont mes meilleurs upgrades pour la cape ?"*  
> *"Est-ce que je suis cap hit ?"*  
> *"Compare mes deux bagues"*  
> *"Analyse mon gear complet en Fury Warrior"*

Claude lit ton équipement et tes talents directement depuis WoW, et répond avec des conseils adaptés à ta classe, ta spé et ton hit actuel.

---

## Installation — 3 étapes

### Étape 1 — L'addon WoW

Télécharge **CharExport-addon.zip** depuis la [dernière Release](../../releases/latest) et extrais le dossier `CharExport/` dans :

| OS | Chemin |
|----|--------|
| Windows | `C:\Program Files (x86)\World of Warcraft\_classic_\Interface\AddOns\` |
| macOS | `/Applications/World of Warcraft/_classic_/Interface/AddOns/` |

Lance WoW, active l'addon dans la liste des AddOns au login, puis en jeu :
```
/exportchar
/reload
```

L'addon s'actualise automatiquement à chaque changement d'équipement ou de talents.

---

### Étape 2 — Le serveur MCP

Télécharge le binaire pour ton OS depuis la [dernière Release](../../releases/latest) :

- **Windows** → `wow-mcp-windows.exe`
- **macOS** → `wow-mcp-macos`

Place-le quelque part de permanent (ex: `Documents/wow-mcp/`).

> **macOS uniquement** — Gatekeeper va bloquer le binaire la première fois. Ouvre un Terminal et tape :
> ```bash
> xattr -c ~/Documents/wow-mcp/wow-mcp-macos
> chmod +x ~/Documents/wow-mcp/wow-mcp-macos
> ```

---

### Étape 3 — Configurer Claude Desktop

Installe [Claude Desktop](https://claude.ai/download) si ce n'est pas déjà fait.

Ouvre le fichier de configuration :

| OS | Chemin |
|----|--------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Ajoute le bloc suivant (crée le fichier s'il n'existe pas) :

**Windows :**
```json
{
  "mcpServers": {
    "wow-char-export": {
      "command": "C:\\Users\\TonNom\\Documents\\wow-mcp\\wow-mcp-windows.exe"
    }
  }
}
```

**macOS :**
```json
{
  "mcpServers": {
    "wow-char-export": {
      "command": "/Users/TonNom/Documents/wow-mcp/wow-mcp-macos"
    }
  }
}
```

Remplace le chemin par l'emplacement réel du binaire, puis **redémarre Claude Desktop**.

---

## Vérification

Dans Claude Desktop, tape :

> *"Liste mes personnages exportés"*

Claude doit répondre avec ton nom de perso, ta classe et la date du dernier export. Si c'est le cas, tout fonctionne.

---

## Mise à jour

Quand une nouvelle version est disponible :
1. Télécharge les nouveaux fichiers depuis les [Releases](../../releases)
2. Remplace le binaire et le dossier addon
3. `/reload` en jeu

---

## Dépannage

**Claude dit que le fichier est introuvable**

L'addon n'a pas encore écrit sur le disque. En jeu, tape `/reload`. Si le problème persiste, crée un fichier `.env` dans le même dossier que le binaire :

```
WOW_SAVED_VARS_PATH=C:\chemin\complet\vers\CharExport.lua
```

Le fichier se trouve dans :
- **Windows** : `C:\Program Files (x86)\World of Warcraft\_classic_\WTF\Account\TON_COMPTE\SavedVariables\CharExport.lua`
- **macOS** : `/Applications/World of Warcraft/_classic_/WTF/Account/TON_COMPTE/SavedVariables/CharExport.lua`

**Les stats semblent trop élevées**

Tu avais des buffs actifs au moment de l'export. L'outil les détecte et les soustrait automatiquement pour les buffs courants (flasques, nourriture, Arcane Intellect, Mark of the Wild…). Les buffs % comme Blessing of Kings sont signalés séparément.

**Plusieurs alts sur le même compte**

Chaque perso qui fait `/exportchar` est stocké. Précise le nom à Claude :
> *"Regarde les upgrades de mon Warrior Grontar"*
