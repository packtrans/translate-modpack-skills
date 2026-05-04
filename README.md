# Translate Modpack Skills

A specialized skill set for translating Minecraft modpacks using AI agents. This project provides structured guidelines and workflows for translating FTB Quests, KubeJS scripts, and other modpack content.

## Features

- **Structured Translation Workflow**: Scan → Translate → Zip
- **Multi-Module Support**: Handles FTB Quests, KubeJS, and SNBT files
- **AI Agent Integration**: Designed for use with Claude Code, Codex, OpenCode and any other AI agents supporting the skills.
- **Consistent Output**: Generates standardized translation packages ready for distribution

## Prerequisites

- Git
- An AI agent tool that supports skills (e.g., Claude Code, Codex, OpenCode)
- One of the following for zipping: `zip` or `7z` for packing
- Python: Agents may need write script to translate and verify files.

## Quick Start

### 1. Create Your Repository

Click the right top [Use this template](https://github.com/new?template_name=translate-modpack-skills&template_owner=packtrans) green button to create a new repository based on this template in your GitHub account.

### 2. Clone Your Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 3. Install Skills

If your agent tool doesn't natively support the `.agents/skills` folder (e.g. Claude Code), install the skills using [skills.sh](https://skills.sh/docs):

```bash
npx skills add packtrans/translate-modpack-skills --skill translate-minecraft-modpack
```

### 4. Prepare Your Modpack

Download your modpack on CurseForge or other platform, place it under the `packs/<modpack-slug>/<version>` directory, which should look like this:

```
packs/
└── all-the-mods-10/
    └── 6.6/
        └── overrides/
            ├── config/
            │   └── ftbquests/
            └── kubejs/
```

### 5. Start Translation

Open your AI agent and send a translation prompt like:

> "Translate the modpack at `packs/all-the-mods-10/6.6` to Chinese (zh_cn)"

### 6. Review and Test

The agent will:
1. **Scan** - Identify files needing translation and extract key terms
2. **Translate** - Generate translations in `out/<modpack-slug>/<version>/<lang-code>/`
3. **Verify** - Check file syntax error, especially snbt files which agent is not familiar with.  
4. **Zip** - Package the final translation into a distributable zip file

Review the generated `files.json` and `terms.json`, confirm translations, and test in-game.

## Supported Modules

| Module | Path | Description |
|--------|------|-------------|
| FTB Quests | `config/ftbquests` | Quest descriptions, titles, and lore |
| KubeJS | `kubejs` | Scripts, lang files, and custom content |

If you want to add support for more modules, please submit a PR or open an [Issue](https://github.com/packtrans/translate-modpack-skills/issues).

## Translation Rules

When translating, the agent will automatically:

- ✅ Preserve Minecraft formatting codes (`§b`, `§r`, `\u0026a`, etc.)
- ✅ Keep string placeholders (`%s`, `%d`, `%1$s`)
- ✅ Maintain original file structure and keys
- ❌ Never translate modpack names (unless originally non-English)
- ❌ Skip irrelevant files (`manifest.json`, `modlist.html`, `mods/`)

## Output Format

Translations are saved to `out/<modpack-slug>/<version>/<lang-code>/`:

```
out/
└── all-the-mods-10/
    └── 6.6/
        └── zh_cn/
            ├── files.json
            ├── terms.json
            └── trans/
                ├── config/
                │   └── ftbquests/
                └── kubejs/
```

The final output is a zip file: `<modpack-slug>-<version>-<lang-code>.zip`

## Contributing

Feel free to submit issues or pull requests to improve the translation workflows and documentation.

## License

[MIT](LICENSE)
