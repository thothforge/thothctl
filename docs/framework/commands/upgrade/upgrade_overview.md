# Upgrade Command

The `upgrade` command in ThothCTL provides functionality to update ThothCTL to the latest version available on PyPI. It ensures you have access to the newest features, bug fixes, and security improvements.

## Overview

The upgrade command helps developers and teams to:

- Check for available ThothCTL updates
- Upgrade to the latest version automatically
- Maintain up-to-date tooling for optimal performance
- Access new features and security patches

## Basic Usage

```bash
# Check for updates and upgrade if available
thothctl upgrade

# Only check for updates without installing
thothctl upgrade --check-only
```

## Command Options

| Option | Description |
|--------|-------------|
| `--check-only` | Only check for updates without installing them |

## How It Works

1. **Version Check**: Compares your current ThothCTL version with the latest available on PyPI
2. **Update Notification**: Shows current and latest versions
3. **Confirmation**: Asks for confirmation before proceeding with the upgrade
4. **Installation**: Uses pip to upgrade ThothCTL to the latest version
5. **Completion**: Provides feedback on successful upgrade

## Example Output

```bash
$ thothctl upgrade
📦 Current version: 1.2.3
🔍 Latest version: 1.3.0
⚠️  Update available: 1.2.3 → 1.3.0
Upgrade from 1.2.3 to 1.3.0? [Y/n]: y
🚀 Upgrading thothctl...
✅ ThothCTL upgraded successfully!
💡 Restart your terminal or run 'hash -r' to use the new version
```

## Check-Only Mode

Use the `--check-only` flag to see if updates are available without installing them:

```bash
$ thothctl upgrade --check-only
📦 Current version: 1.2.3
🔍 Latest version: 1.3.0
⚠️  Update available: 1.2.3 → 1.3.0
💡 Run 'thothctl upgrade' to install the update
```

## Benefits

1. **Stay Current**: Keep ThothCTL up-to-date with the latest features and fixes
2. **Security**: Ensure you have the latest security patches
3. **Automation**: Simple one-command upgrade process
4. **Safety**: Confirmation prompt prevents accidental upgrades
5. **Transparency**: Clear feedback on current and available versions

## Requirements

- Internet connection to check PyPI for latest version
- Appropriate permissions to install Python packages
- pip package manager available in your environment

## Troubleshooting

If the upgrade fails:

1. Check your internet connection
2. Ensure you have proper permissions to install packages
3. Try upgrading manually with: `pip install --upgrade thothctl`
4. Check if you're in a virtual environment that needs activation

## Next Steps

After upgrading:

1. Restart your terminal or run `hash -r` to refresh the command cache
2. Verify the new version with `thothctl --version`
3. Check the changelog for new features and changes
4. Update any automation scripts if needed
