# Kitty Tabline

A highly customizable, Lualine-inspired tab bar for the Kitty terminal emulator.

This project replaces Kitty's default tab bar with a functional status line that integrates session information, system metrics, and clean tab navigation using a Powerline-style aesthetic.

## Features

- **Lualine Aesthetic:** Powerline-style separators (``, ``, ``, ``) and the Catppuccin Mocha color palette.
- **Mode Indicator:** Displays the current Kitty mode (NORMAL, PREFIX, COPY, ZOOM) with relevant icons.
- **Session Info:** Shows current Git branch and active process name (cached for performance).
- **Adaptive Tab Sizing:** Dynamically calculates tab widths to prevent overflows and ensure the right-side status is always visible.
- **System Metrics:** Real-time CPU, RAM, and Battery status (conditional based on available space).
- **Robust Rendering:** Uses a sequential drawing architecture to prevent layout collisions and "..." error indicators.

## Requirements

- **Kitty Terminal Emulator**
- **Python 3**
- **Nerd Fonts:** Required for icons and Powerline separators.
- **Operating System:** Linux (CPU/RAM/Battery metrics currently optimized for Linux `/proc` and `/sys` interfaces).

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/devnullvoid/kitty-tabline.git ~/Dev/misc/kitty-tabline
   ```

2. Symlink `tab_bar.py` to your Kitty configuration directory:
   ```bash
   ln -s ~/Dev/misc/kitty-tabline/tab_bar.py ~/.config/kitty/tab_bar.py
   ```

3. Configure Kitty to use the custom tab bar in `~/.config/kitty/kitty.conf`:
   ```conf
   tab_bar_style custom
   ```

4. Restart Kitty or press `ctrl+shift+f5` to reload the configuration.

## Configuration

The script uses the Catppuccin Mocha palette by default. You can adjust colors and separators directly in `tab_bar.py`.

Key settings in `tab_bar.py`:
- `REFRESH_TIME`: How often to update system metrics (default: 1s).
- `MAX_BRANCH_LEN`: Maximum width for the Git branch display.
- Palette variables (e.g., `PEACH`, `MAUVE`, `SURFACE0`) for color customization.

## License

MIT
