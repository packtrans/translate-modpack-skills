# KubeJS Translation Guide

KubeJS is a Minecraft mod that lets pack developers add items, blocks, fluids, recipes, tooltips, and other behaviors via JavaScript. Text can appear in two ways:

1. **Language files** (`assets/<namespace>/lang/*.json`) — the standard Minecraft localization format.
2. **Hardcoded strings in scripts** (`.js` files under `startup_scripts/`, `client_scripts/`, and occasionally `server_scripts/`).

## Folder Structure

Typical `kubejs/` layout in a modpack:

```text
kubejs
├── assets/              # Resource-pack-like files (lang, textures, models)
│   └── <namespace>/
│       └── lang/
│           └── en_us.json
├── client_scripts/      # Client-side scripts (tooltips, JEI, events)
├── config/              # KubeJS configs — do NOT translate
├── data/                # Datapack-like files (recipes, loot, worldgen) — do NOT translate
├── server_scripts/      # Server-side scripts (recipes, tags, events)
├── startup_scripts/     # Startup scripts (item/block/fluid registration)
├── jsconfig.json        # IDE config — do NOT translate
└── README.txt           # Do NOT translate
```

## What to Translate

### 1. Language Files

Any file matching `assets/**/lang/*.json` should be translated.

- Copy the source language file (usually `en_us.json`) and rename it to the target language code (e.g., `zh_cn.json`).
- Translate **only the values**; keep all JSON keys exactly as-is.

Example (`assets/kubejs/lang/en_us.json` → `zh_cn.json`):

```json
{
  "mek1000.material.iron": "Iron",
  "item.mek1000.teleporter": "Teleporter",
  "mek1000.teleporter.desc": "§bRight-Click§e to Teleport!§r"
}
```

### 2. Startup Scripts with Hardcoded Names

Scripts under `startup_scripts/` register custom items, blocks, fluids, gases, etc. Some use hardcoded `.displayName()` or `.tooltip()` strings instead of translation keys.

**Patterns to look for:**

- `.displayName('Some Name')`
- `.tooltip('Some description')`
- `.tooltip(Text.of('Some description'))`
- `.displayName(Text.translate('key'))` — **do NOT translate** the key itself; translate it in the lang file.

If a hardcoded string is found, translate the string literal in-place.

Example (`startup_scripts/mekanism/custom_gas.js`):

```javascript
// Before
.event.create('mek1000:dvt').fuel(10, 2147483647).color(0xdda0dd).displayName('DVT fuel')

// After (zh_cn example)
.event.create('mek1000:dvt').fuel(10, 2147483647).color(0xdda0dd).displayName('DVT燃料')
```

> **Note:** The preferred modding practice is to use `Text.translate("your.mod.key")` and put the text in a lang file, but many packs still hardcode strings. If the script already uses `Text.translate()`, only the lang file needs translation.

#### Registry Loops with Auto-Generated IDs

Some startup scripts register items in a loop where the registry ID is derived from a display name. In these cases, **do not translate the ID**; only translate the display name passed to the register function.

Common pattern with `formatId`:

```javascript
function formatId(name) {
    return name.toLowerCase().replace(/'/, '').replace(/[^a-z]+/g, '_');
}

const items = [
  { name: "Item A", "__cn_name__": "物品 A" },
  { name: "Item B", "__cn_name__": "物品 B" }
]

items.forEach(item => {
  ItemRegistry.register(`prefix:${formatId(item.name)}`, item.__cn_name__);
})
```

> **Rule of thumb:** If a string is used to build a registry ID, a file path, or a translation key, leave it untouched. Only translate strings that are passed directly as display names or tooltips.

### 3. Client Scripts with Hardcoded Text

Scripts under `client_scripts/` often add tooltips, modify item names, or handle JEI events.

**Patterns to look for:**

- `Text.of('...')` or `Text.translate('...')`
- Plain string literals inside tooltip arrays or objects
- Object properties such as `{ name: "Infinity Ingot" }`
- Hardcoded dimension names, descriptions, or chat messages

Example (`client_scripts/tooltip.js`):

```javascript
// Before
let colorfulnames = [
  {
    id: "mek1000:infinity_ingot",
    name: "Infinity Ingot",   // <-- translate this
    nodes: [[255, 255, 0], [0, 255, 255], [255, 0, 255]],
    length: 5,
    time: 1,
  },
];

// After (zh_cn example)
let colorfulnames = [
  {
    id: "mek1000:infinity_ingot",
    name: "无尽锭",
    nodes: [[255, 255, 0], [0, 255, 255], [255, 0, 255]],
    length: 5,
    time: 1,
  },
];
```

If the script already references translation keys (e.g., `Text.translate("mek1000.sml_drill.desc")`), **do not modify the script**; translate the corresponding lang file instead.

### 4. Lang Files Belonging to Other Mods Inside KubeJS

Sometimes KubeJS `assets/` contains lang files for other mods or helper mods (e.g., `assets/ftbquestlocalizer/lang/en_us.json`). Translate these exactly like normal lang files.

## What NOT to Translate

- `server_scripts/`: IDs and code should not be translated.
- `data/`: Datapack JSONs (recipes, loot tables, worldgen), no need translation. 
- `config/`, `jsconfig.json`, `README.txt`, Textures, models, sounds and non-text assets: Developer files and untranslable files.
- Script IDs, registry names, item tags: These are code identifiers (e.g., `mek1000:dvt`, `forge:dusts`), do not translate.

## Output Paths

- **Lang files**: save under the same namespace but with the target language code:
  - Source: `kubejs/assets/kubejs/lang/en_us.json`
  - Output: `out/<modpack>/<version>/<lang-code>/kubejs/assets/kubejs/lang/zh_cn.json`
- **Scripts**: save with the **original file name** in the same relative path:
  - Source: `kubejs/startup_scripts/mekanism/custom_gas.js`
  - Output: `out/<modpack>/<version>/<lang-code>/kubejs/startup_scripts/mekanism/custom_gas.js`

Only modify translated strings; keep file names, internal keys, structure, and non-text data exactly as in the original.

## Best Practices

1. **Prefer lang files over hardcoded strings.** If you find a hardcoded English string in a script and there is already an `en_us.json` for that namespace, consider moving the string to the lang file and replacing the hardcoded value with `Text.translate("your.key")`. This keeps translations maintainable.
2. **Preserve formatting codes.** Minecraft uses `§` and some packs use `\u0026` for color/formatting. Keep them intact.
3. **Do not translate modpack names** unless the source language of the name is not English.
4. **Do not translate registry IDs or NBT keys.** Only translate human-readable strings.
5. **Check `client_scripts/` carefully.** Tooltip scripts are the most common source of missed translations.
