---
name: translate-minecraft-modpack
description: This skill docs how to fully translate a Minecraft modpack. Must use this skill if user requires you to translate a modpack from one language to another language.
---

# Translate Minecraft Modpack

## Pack Source

If user provided a modpack folder under `packs/<modpack-slug>/<version>` folder like `packs/all-the-mods-10/6.6`, go to the folder stucture part. Or if the path doesn't follow this rule, you should ask user whether to move the provided folder to `packs` folder and move it on behalf of the user if permitted.

## Folder Structure

Following structure shows folders that need to be translated. DON'T read other files especially `manifest.json`, `modlist.html` or `mods/`, they will be huge and irrelevant to translations, hardcoded text inside `.jar` mod files do not need be translated.

```text
packs
└── all-the-mods-10
    └── 6.6
        └── overrides
            ├── config
            │   └── ftbquests
            └── kubejs
```

If required, create the `out/<modpack-slug>/<version>/<lang-code>` (e.g. `out/all-the-mods-10/6.6/zh_cn`) folder under root folder (same level as `packs` folder) for storing all translation outputs. The out folder structured like:

```text
out
└── all-the-mods-10
    └── 6.6
        └── zh_cn
            ├── files.json
            ├── terms.json
            └── trans
                ├── config
                │   └── ftbquests
                └── kubejs
```

Note we don't need a `overrides` layer in the out.

## Module

We split translation guidelines by modules. `ftbquests` and `kubejs` modules are supported now. Read the specific modules' documentations if corresponding folder exists before getting into translation job.

- [ftbquests](ftbquests.md) for `config/ftbquests` folder translation
- [kubejs](kubejs.md) for `kubejs` folder translation

## Steps

>  It would be better if you can do heavy steps in a single dedicated sub-agent.

Do translatation in order:

### Scan 

Scan files in only mentioned folder, generate a `files.json` and a `terms.json`.

`files.json` including all file need be changed (if a file only contains translation key like `ftbquests.chapter_groups_123456.title` but not real text phrase to translate, we don't include that file). Example:

```json
[
  "config/ftbquests/quests/chapter_groups.snbt",
]
```

`terms.json` containing all generic terms (usually item name) and their translation in these files. Keep this file small, don't put  entire sentences in this file. Example:

```
{
  "Some Generic Term": "Some Generic Term in target language"
}
```

You MUST require user to confirm the terms before next step.

### Translate

When translating, create a copy of the source file and save it in the corresponding location under the out folder. 

For example, if you are translating language file like `kubejs/assets/kubejs/lang/en_us.json`, you should save the translation to `out/<modpack-slug>/<version>/<lang-code>/kubejs/assets/kubejs/lang/<lang-code>.json`, this applied to quest lang snbt file (like `config/ftbquests/quests/lang/en_us.snbt`) as well. For non-lang `.snbt` file, `.js` and other scripts files, you should save it in the same path but with original file name.  Only modify the translated strings; keep file names, internal keys, structure, and non-text data exactly as in the original.

#### Rules MUST follow when translating

- NEVER translate modpack name into other language unless the source language of name is not English.
- Preserve Minecraft formatting codes such as `§b`, `§r`, `\u0026a`, etc.
- Preserve string placeholders like `%s`, `%d`, `%1$s`.

You MUST require user to confirm the translation before next step.

### Zip

Pack the files and folders under `out/<modpack-slug>/<version>/<lang-code>` into a zip file named `<modpack-slug>-<version>-<lang-code>.zip`, `config` folder should be at the top layer, DO NOT add an extra top folder. Try these command: `zip -r <out> <in>`, `7z a <out> -tzip <in>`, `python/python3 -m zipfile -c <out> <in>` to pack, noting that `<out>` and `<in>` may be different in these command. If none of them works, tell user to install one of them and how to zip the out folder manually.
