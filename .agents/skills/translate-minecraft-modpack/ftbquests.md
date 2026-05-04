# FTB Quests Translation Guide

## Overview

FTB Quests stores quest data in SNBT (Structured NBT) format under `config/ftbquests/quests/`. These files define quest chapters, individual quests, rewards, and UI organization.

## Directory Structure

```
config/ftbquests/quests/
├── data.snbt              # Global settings, pack title
├── chapter_groups.snbt    # Chapter grouping definitions
├── chapters/              # Individual chapter files (*.snbt)
│   ├── chapter_id.snbt
│   └── ...
├── lang/                  # Minecraft version 1.21+ support snbt lang file for translation keys(*.snbt)
│   └── *.snbt
└── reward_tables/         # Shared reward definitions
    └── *.snbt
```

## SNBT Format

SNBT is similar to JSON but with these key differences:
- Keys are typically unquoted (e.g., `title: "value"` instead of `"title": "value"`)
- Commas between entries are often optional/omitted
- Supports NBT-specific types (e.g., `5.0d` for doubles, `1b` for booleans)
- Preserve the exact formatting style of the original file when editing

Read [Full SNBT syntax docs](snbt.md) if necessary.

## Translatable Fields

Scan these specific fields for translatable text. **Do not** modify IDs, coordinates (`x`, `y`), item references, or structural data.

### `chapter_groups.snbt`
- `title` — Group names shown in the quest book sidebar

### `chapters/*.snbt`
- `title` — Chapter name
- `subtitle` — Chapter subtitle (may be an array of strings)
- Inside each `quests` entry:
  - `title` — Quest name
  - `subtitle` — Quest subtitle
  - `description` — Array of strings, may contain multiple lines

### `lang/*.snbt`

FTB Quests language files store human-readable quest text separately from the quest structure. **Do not** translate raw text inside `chapters/*.snbt` or `chapter_groups.snbt` if the pack uses translation keys — translate the corresponding entries in the lang file instead.

#### Location & Format by Version

| Minecraft Version | Lang File Location | Format |
|---|---|---|
| 1.21+ | `config/ftbquests/quests/lang/xx_xx.snbt` | SNBT |
| 1.20.1 and earlier | `kubejs/assets/kubejs/lang/xx_xx.json` (or mod-specific namespace) | JSON |

#### SNBT Lang Format (1.21+)

The file is a single SNBT compound where each key is a dot-separated translation key and each value is the displayed string:

```snbt
{
	chapter.083FB2FC095A6686.title: "Flourishing Island"
	chapter.0A799F91D9A1C8A1.title: "Blazing Island"
	quest.1234567890ABCDEF.title: "Gather Wood"
	quest.1234567890ABCDEF.description: "Collect 16 oak logs."
}
```

**Key patterns to translate:**
- `chapter.<hex-id>.title` — Chapter names
- `chapter.<hex-id>.subtitle` — Chapter subtitles
- `quest.<hex-id>.title` — Quest names
- `quest.<hex-id>.subtitle` — Quest subtitles
- `quest.<hex-id>.description` — Quest descriptions (may be a single string or an array)
- `quest.<hex-id>.description1`, `description2`, … — Multi-line descriptions exported as separate keys
- `reward_table.<hex-id>.title` — Reward table names

**Translation rules:**
1. Keep the key (left side) exactly as-is; only translate the quoted string value (right side).
2. Preserve formatting codes (`§b`, `§r`, `\u0026a`, etc.) and placeholders (`%s`, `%d`, `%1$s`).
3. Leave empty strings (`""`) unchanged — they are often used as paragraph breaks in descriptions.
4. Do not add or remove keys unless you are also editing the quest structure itself.

#### JSON Lang Format (1.20.1 and earlier)

Older packs store FTB Quest translations in standard Minecraft JSON lang files, typically under `kubejs/assets/kubejs/lang/` or another mod namespace. The content follows the same key patterns but in regular JSON:

```json
{
  "chapter.083FB2FC095A6686.title": "Flourishing Island",
  "quest.1234567890ABCDEF.description": "Collect 16 oak logs."
}
```

Translate only the JSON values; keep keys unchanged.

#### How Lang Files Relate to Quest SNBT

When a quest file contains a translation key in curly braces:

```snbt
title: "{chapter.083FB2FC095A6686.title}"
```

the actual text is looked up in the lang file. **Translate the lang file entry, not the SNBT value.**

If a quest file contains raw text instead:

```snbt
title: "Flourishing Island"
```

the pack is either old or does not use the lang system. In that case, translate the raw text in-place inside the SNBT file (or export it first with `/ftblang export` and then translate the resulting lang file).


### `reward_tables/*.snbt`
- `title` — Reward table name


## DO NOT Translate

### `data.snbt`
- `title` — Keep modpack name displayed as-is

## Translation Key vs Raw Text

FTB Quests supports two text patterns. Handle each differently:

### Translation Keys

Text wrapped in curly braces are translation keys, e.g.:

```snbt
title: "{chapter.083FB2FC095A6686.title}"
description: [
    "{quest.1234567890ABCDEF.description1}"
    ""
    "{quest.1234567890ABCDEF.description2}"
]
```

**Do NOT translate these keys in the SNBT files.** These keys reference lang files (see [`lang/*.snbt`](#langsnbt) above). You can search the key (without the braces) using `grep` if you can't find the keys in files mentioned above. If the modpack uses translation keys throughout, the SNBT files themselves may contain no raw text to translate. In this case, `files.json` should not include these SNBT files.

### Raw Text

Direct string values without curly braces must be translated in-place:
```snbt
title: "Translate this title"
```

When translating raw text in SNBT:
1. Keep the exact key name and structure
2. Replace only the string value
3. Preserve any escape sequences (e.g., `\"`, `\\n`)
4. Maintain SNBT formatting (quoted keys if originally quoted, unquoted if not)

## Empty Strings and Special Values

- Leave empty strings (`""`) unchanged
- Leave formatting-only entries (like `""` used as paragraph breaks in `description` arrays) unchanged
- Do not add or remove entries from `description` arrays unless they contain translatable text

## Output Structure

Save translated `.snbt` files to the same relative path under the output folder. Keep original filenames. Only modify the translatable string values; preserve all IDs, structure, coordinates, item references, and SNBT formatting.
