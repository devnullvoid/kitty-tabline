import sys
from datetime import datetime
import subprocess
import re
import time
import os
from typing import List, Tuple, Optional
from kitty.boss import get_boss
from kitty.fast_data_types import Screen, add_timer, get_options, wcswidth
from kitty.utils import color_as_int
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    Formatter,
    TabBarData,
    as_rgb,
    draw_attributed_string,
    draw_title,
)

opts = get_options()

# Catppuccin Mocha palette (matching tmux config)
ROSEWATER = as_rgb(color_as_int(0xF5E0DC))
FLAMINGO = as_rgb(color_as_int(0xF2CDCD))
PINK = as_rgb(color_as_int(0xF5C2E7))
BLUE = as_rgb(color_as_int(0x89B4FA))
LAVENDER = as_rgb(color_as_int(0xB4BEFE))
GREEN = as_rgb(color_as_int(0xA6E3A1))
TEAL = as_rgb(color_as_int(0x94E2D5))
SKY = as_rgb(color_as_int(0x89DCEB))
SAPPHIRE = as_rgb(color_as_int(0x74C7EC))
PEACH = as_rgb(color_as_int(0xFAB387))
YELLOW = as_rgb(color_as_int(0xF9E2AF))
MAUVE = as_rgb(color_as_int(0xCBA6F7))
RED = as_rgb(color_as_int(0xF38BA8))
MAROON = as_rgb(color_as_int(0xEBA0AC))
TEXT = as_rgb(color_as_int(0xCDD6F4))
SUBTEXT1 = as_rgb(color_as_int(0xBAC2DE))
SUBTEXT0 = as_rgb(color_as_int(0xA6ADC8))
OVERLAY0 = as_rgb(color_as_int(0x6C7086))
OVERLAY1 = as_rgb(color_as_int(0x7F849C))
OVERLAY2 = as_rgb(color_as_int(0x9399B2))
SURFACE0 = as_rgb(color_as_int(0x313244))
SURFACE1 = as_rgb(color_as_int(0x45475A))
SURFACE2 = as_rgb(color_as_int(0x585B70))
BASE = as_rgb(color_as_int(0x1E1E2E))
MANTLE = as_rgb(color_as_int(0x181825))
CRUST = as_rgb(color_as_int(0x11111B))

# Mode colors
MODE_PREFIX = PEACH
MODE_COPY = BLUE
MODE_ZOOM = TEAL
MODE_NORMAL = MAUVE

# Separators
SEPARATOR_SYMBOL, SOFT_SEPARATOR_SYMBOL = ("", "")
LEFT_SEPARATOR_SYMBOL, LEFT_SOFT_SEPARATOR_SYMBOL = ("", "")
DIVIDER, SOFT_DIVIDER = ("", "")
RIGHT_DIVIDER, RIGHT_SOFT_DIVIDER = ("", "")

# Other settings
RIGHT_MARGIN = 1
REFRESH_TIME = 1
ICON = " 󰣇 "
UNPLUGGED_ICONS = {
    10: "󰁺",
    20: "󰁻",
    30: "󰁼",
    40: "󰁽",
    50: "󰁾",
    60: "󰁿",
    70: "󰂀",
    80: "󰂁",
    90: "󰂂",
    100: "󰁹",
}
PLUGGED_ICONS = {
    1: "󰂄",
}
UNPLUGGED_COLORS = {
    15: RED,
    16: TEXT,
}
PLUGGED_COLORS = {
    15: RED,
    16: SAPPHIRE,
    99: SAPPHIRE,
    100: GREEN,
}

# Simple palette helpers for metrics
CPU_LOW = GREEN
CPU_MED = YELLOW
CPU_HIGH = RED
MEM_CLR = BLUE


def _get_mode_color() -> Tuple[int, str]:
    """Get current mode color and name"""
    boss = get_boss()
    active_window = boss.active_window

    if active_window:
        # Check if in prefix mode (kitty equivalent of tmux prefix)
        if hasattr(active_window, "is_key_pressed") and active_window.is_key_pressed(
            "ctrl"
        ):
            return MODE_PREFIX, "PREFIX"

        # Check if in copy mode
        if hasattr(active_window, "in_copy_mode") and active_window.in_copy_mode:
            return MODE_COPY, "COPY"

        # Check if zoomed
        if hasattr(active_window, "is_zoomed") and active_window.is_zoomed:
            return MODE_ZOOM, "ZOOM"

    return MODE_NORMAL, "NORMAL"


def _draw_mode_indicator(screen: Screen, index: int, tab=None, draw_data=None) -> int:
    """Draw mode indicator like tmux lualine"""
    try:
        if index != 1:
            return 0

        fg, bg = screen.cursor.fg, screen.cursor.bg
        mode_color, mode_name = _get_mode_color()

        # Draw mode indicator with icon
        screen.cursor.fg = CRUST
        screen.cursor.bg = mode_color

        mode_icons = {
            "PREFIX": "󰘳",
            "COPY": "",
            "ZOOM": "",
            "NORMAL": "",
        }

        icon = mode_icons.get(mode_name, "")
        screen.draw(f" {icon} {mode_name} ")

        # Draw separator to session section
        screen.cursor.fg = mode_color
        screen.cursor.bg = SURFACE0
        screen.draw(SEPARATOR_SYMBOL)

        screen.cursor.fg, screen.cursor.bg = fg, bg
        return screen.cursor.x
    except Exception:
        # Silently fail to avoid stderr output that could show as red text
        return 0


def _get_git_branch() -> str:
    """Get current git branch name"""
    try:
        # Get current working directory
        boss = get_boss()
        if boss and boss.active_tab and boss.active_tab.active_window:
            cwd = boss.active_tab.active_window.cwd_of_child or ""
        else:
            cwd = os.getcwd()

        # Check if we're in a git repo
        git_dir = os.path.join(cwd, ".git")
        if not os.path.exists(git_dir):
            return ""

        # Try to get branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch and branch != "HEAD" else ""
        return ""
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return ""


def _get_process_name() -> str:
    """Get current process name"""
    try:
        boss = get_boss()
        if boss and boss.active_tab and boss.active_tab.active_window:
            # Try to get the foreground process name
            cwd = boss.active_tab.active_window.cwd_of_child or ""
            if cwd:
                # Get the current shell or process from environment
                shell = os.getenv("SHELL", "")
                if "zsh" in shell:
                    return "zsh"
                elif "bash" in shell:
                    return "bash"
                elif "fish" in shell:
                    return "fish"
                else:
                    return os.path.basename(shell) if shell else "shell"
        return "shell"
    except Exception:
        return "shell"


def _draw_session_info(screen: Screen, index: int, tab=None, draw_data=None) -> int:
    """Draw git branch and process name with powerline separators"""
    try:
        # Only draw once for the first tab
        if index != 1:
            return 0

        fg, bg = screen.cursor.fg, screen.cursor.bg
        mode_color, _ = _get_mode_color()

        # Get git branch and process name
        git_branch = _get_git_branch()
        process_name = _get_process_name()

        # Truncate git branch to prevent it from taking too much space
        MAX_BRANCH_LEN = 25
        if git_branch and wcswidth(git_branch) > MAX_BRANCH_LEN:
            while wcswidth(git_branch) > MAX_BRANCH_LEN - 1:
                git_branch = git_branch[:-1]
            git_branch = git_branch + "…"

        # Background colors for sections
        GIT_BG = SURFACE0
        GIT_FG = MAUVE  # Mauve for git like lualine
        PROCESS_BG = BASE
        PROCESS_FG = BLUE  # Blue for processes

        # Draw git section if we have a branch
        if git_branch:
            # Git icon and branch
            screen.cursor.fg = GIT_FG
            screen.cursor.bg = GIT_BG
            screen.draw(f"  {git_branch} ")

            # Separator from git to process
            screen.cursor.fg = GIT_BG
            screen.cursor.bg = PROCESS_BG
            screen.draw(SEPARATOR_SYMBOL)
        else:
            # No git, just process section - draw separator from Mode to Process
            # The mode indicator ends with: fg=mode_color, bg=SURFACE0 separator
            # So we need to transition from SURFACE0 to PROCESS_BG
            screen.cursor.fg = SURFACE0
            screen.cursor.bg = PROCESS_BG
            screen.draw(SEPARATOR_SYMBOL)

        # Draw process section
        screen.cursor.fg = PROCESS_FG
        screen.cursor.bg = PROCESS_BG

        # Process icons
        process_icons = {
            "zsh": "󰉋 ",
            "bash": " ",
            "fish": " ",
            "shell": " ",
            "nvim": " ",
            "vim": " ",
        }

        icon = process_icons.get(process_name, " ")
        screen.draw(f" {icon}{process_name} ")

        # Draw separator from Process to Tabs (Default BG)
        default_bg = as_rgb(int(draw_data.default_bg))

        # Always transition from PROCESS_BG to default_bg
        screen.cursor.fg = PROCESS_BG
        screen.cursor.bg = default_bg
        screen.draw(SEPARATOR_SYMBOL)

        # Add a space after
        screen.draw(" ")

        screen.cursor.fg, screen.cursor.bg = fg, bg
        return screen.cursor.x
    except Exception:
        # Silently fail to avoid stderr output that could show as red text
        return 0


def _calculate_tab_width(title: str, max_title_length: int) -> int:
    """Calculate the visual width of a tab including its separator"""
    # Truncate title if needed
    if wcswidth(title) > max_title_length:
        display_title = title[:max_title_length-1] + "…"
    else:
        display_title = title
    
    # Tab width = title + " 󰿟 " (space, separator, space)
    return wcswidth(display_title) + wcswidth(" " + SOFT_SEPARATOR_SYMBOL + " ")


def _draw_left_status(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
    reserved_right: int = 0,
) -> int:
    # For the first tab, cursor.x may have been advanced by mode/session drawing
    # For subsequent tabs, we need to check from the tab's starting position
    # Use 'before' as the starting position for this tab
    if index > 1:
        screen.cursor.x = before

    # Calculate available space
    available = screen.columns - screen.cursor.x
    
    # If we don't have enough space for this tab plus reserved right section, skip
    tab_width = _calculate_tab_width(tab.title, max_title_length)
    if available < tab_width + reserved_right:
        return screen.cursor.x

    # Save current colors
    fg, bg = screen.cursor.fg, screen.cursor.bg

    # Reset to default background for tabs
    default_bg = as_rgb(int(draw_data.default_bg))
    screen.cursor.bg = default_bg

    # Get and truncate title based on cell width using config value
    title = tab.title
    max_len = opts.tab_title_max_length
    if wcswidth(title) > max_len:
        while wcswidth(title) > max_len - 1:
            title = title[:-1]
        title = title + "…"

    # Tab styling and indicator
    if tab.is_active:
        screen.cursor.fg = SUBTEXT0
        screen.draw(title)
    else:
        screen.cursor.fg = OVERLAY0
        screen.draw(title)

    # Add separator to the right of every tab
    # The user's desired layout has "tab1 󰿟 tab2 󰿟 tab3 󰿟"
    # Reset color for separator so it doesn't inherit active tab color
    screen.cursor.fg = OVERLAY0
    screen.draw(" " + SOFT_SEPARATOR_SYMBOL + " ")

    # Restore original colors
    screen.cursor.fg, screen.cursor.bg = fg, bg

    end = screen.cursor.x
    return end


def _draw_right_status(screen: Screen, is_last: bool, cells: list) -> int:
    if not is_last:
        return 0
    draw_attributed_string(Formatter.reset, screen)

    # Ensure we don't position the right status off-screen
    # If right_status_length is too large, adjust it to fit
    if right_status_length > screen.columns:
        # Content is too wide, but we'll still try to draw what we can
        screen.cursor.x = 0
    else:
        screen.cursor.x = screen.columns - right_status_length

    # cells is a list of (fg, bg, text)
    # We iterate and draw.
    # Note: The 'cells' list must be prepared such that hard dividers are separate items
    # or we handle them here.
    # Given the complexity, let's assume 'cells' contains EVERYTHING to be drawn,
    # including separators as explicit items with their own fg/bg.

    for fg, bg, text in cells:
        screen.cursor.fg = fg
        screen.cursor.bg = bg
        screen.draw(text)

    screen.cursor.bg = 0
    return screen.cursor.x


def _redraw_tab_bar(_):
    tm = get_boss().active_tab_manager
    if tm is not None:
        tm.mark_tab_bar_dirty()


# Linux
def _battery_color(percent: int) -> int:
    # Gradient: red (<20), yellow (<40), cyan (<80), green (>=80)
    if percent < 20:
        return RED
    if percent < 40:
        return YELLOW
    if percent < 80:
        return SAPPHIRE
    return GREEN


def get_battery_cells() -> list:
    try:
        with open("/sys/class/power_supply/BAT0/status", "r") as f:
            status = f.read()
        with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
            percent = int(f.read())
        bat_color = _battery_color(percent)
        if status == "Discharging\n":
            icon = UNPLUGGED_ICONS[
                min(UNPLUGGED_ICONS.keys(), key=lambda x: abs(x - percent))
            ]
        elif status == "Not charging\n":
            icon = PLUGGED_ICONS[
                min(PLUGGED_ICONS.keys(), key=lambda x: abs(x - percent))
            ]
        else:
            icon = PLUGGED_ICONS[
                min(PLUGGED_ICONS.keys(), key=lambda x: abs(x - percent))
            ]
        return [(bat_color, f"{icon} {percent}%")]
    except FileNotFoundError:
        return []


_prev_cpu_total = None
_prev_cpu_idle = None
_cpu_cached: Optional[List[Tuple[int, str]]] = None
_cpu_last_update: float = 0.0


def _read_proc_stat():
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        if not line.startswith("cpu"):
            return None
        parts = line.split()
        values = list(map(int, parts[1:]))
        # user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values[:8])  # up to steal
        return total, idle
    except Exception:
        return None


def get_cpu_cells() -> List[Tuple[int, str]]:
    global _prev_cpu_total, _prev_cpu_idle, _cpu_cached, _cpu_last_update
    now = time.monotonic()
    # Throttle updates to avoid multi-tab race and flicker
    if now - _cpu_last_update >= 0.8:
        stats = _read_proc_stat()
        if stats:
            total, idle = stats
            if _prev_cpu_total is None:
                _prev_cpu_total, _prev_cpu_idle = total, idle
                # Initialize placeholder; compute real value next interval
                _cpu_cached = [(OVERLAY0, " --%")]
            else:
                dt_total = total - _prev_cpu_total
                dt_idle = idle - _prev_cpu_idle
                if dt_total > 0:
                    usage = max(0.0, min(1.0, (dt_total - dt_idle) / dt_total))
                    pct = int(round(usage * 100))
                    color = CPU_LOW if pct < 40 else CPU_MED if pct < 75 else CPU_HIGH
                    _cpu_cached = [(color, f" {pct}%")]
                _prev_cpu_total, _prev_cpu_idle = total, idle
        _cpu_last_update = now
    # Always return last cached to keep stable presence
    return _cpu_cached or [(OVERLAY0, " --%")]


def get_mem_cells() -> List[Tuple[int, str]]:
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, val = line.split(":", 1)
                meminfo[key] = int(val.strip().split()[0])
        total = meminfo.get("MemTotal")
        avail = meminfo.get("MemAvailable")
        if not total or not avail:
            return []
        used = total - avail
        pct = int(round(used * 100 / total))
        return [(MEM_CLR, f" {pct}%")]
    except Exception:
        return []


# Mac
# def get_battery_cells() -> list:
#     try:
#         result = subprocess.run(['pmset', '-g', 'batt'],
#                                 capture_output=True, text=True)
#         output = result.stdout
#         status_search = re.search(r'(\w+)\s*;', output)
#         percent_search = re.search(r'(\d+)%', output)
#
#         if status_search and percent_search:
#             status = status_search.group(1)
#             percent = int(percent_search.group(1))
#
#             if status == "discharging":
#                 icon_color = UNPLUGGED_COLORS[min(
#                     UNPLUGGED_COLORS.keys(), key=lambda x: abs(x - percent))]
#                 icon = UNPLUGGED_ICONS[min(
#                     UNPLUGGED_ICONS.keys(), key=lambda x: abs(x - percent))]
#             else:
#                 icon_color = PLUGGED_COLORS[min(
#                     PLUGGED_COLORS.keys(), key=lambda x: abs(x - percent))]
#                 icon = PLUGGED_ICONS[min(
#                     PLUGGED_ICONS.keys(), key=lambda x: abs(x - percent))]
#
#             percent_cell = (bat_text_color, str(percent) + "% ")
#             icon_cell = (icon_color, icon)
#             return [percent_cell, icon_cell]
#     except Exception as e:
#         print(f"Error: {e}")
#         return []


timer_id = None
right_status_length = 50  # Initial estimate, will be recalculated on first draw
_right_status_cells = []  # Cache for right status cells to avoid redundant computation


def _calculate_left_side_width(draw_data, extra_data, tabs) -> int:
    """Calculate the total width of left side (mode + session + all tabs)"""
    # Mode indicator: " 󰘳 MODE " ≈ 10 chars
    mode_width = 10
    
    # Session info: varies, estimate 30 chars for git + process + separators
    session_width = 30
    
    # Calculate width of all tabs
    tab_widths = 0
    max_len = opts.tab_title_max_length
    for tab in tabs:
        tab_widths += _calculate_tab_width(tab.title, max_len)
    
    return mode_width + session_width + tab_widths


def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    try:
        global timer_id
        global right_status_length
        global _right_status_cells
        if timer_id is None:
            timer_id = add_timer(_redraw_tab_bar, REFRESH_TIME, True)

        screen.cursor.x = before  # Initialize cursor position for this tab

        # Get all tabs to calculate actual left side width
        boss = get_boss()
        all_tabs = boss.active_tab_manager.tabs if boss and boss.active_tab_manager else []

        # Calculate right status cells for first tab (determines layout for all tabs)
        if index == 1:
            mode_color, _ = _get_mode_color()
            clock = datetime.now().strftime("%H:%M")

            # Colors
            BG_METRICS = CRUST
            BG_USER = SURFACE0
            BG_CLOCK = mode_color

            FG_METRICS = TEXT
            FG_USER = mode_color
            FG_CLOCK = CRUST

            default_bg = as_rgb(int(draw_data.default_bg))

            # Calculate essential width (user + clock only, without metrics)
            user_host = (
                f"{os.getenv('USER', 'user')}@{os.uname().nodename.split('.')[0]}"
            )
            essential_cells = [
                (BG_USER, default_bg, RIGHT_DIVIDER),
                (FG_USER, BG_USER, f" {user_host} "),
                (BG_CLOCK, BG_USER, RIGHT_DIVIDER),
                (FG_CLOCK, BG_CLOCK, f"  {clock} "),
            ]
            essential_width = sum(wcswidth(str(t)) for _, _, t in essential_cells)
            
            # Calculate actual left side width
            left_width = _calculate_left_side_width(draw_data, extra_data, all_tabs)
            
            # Calculate width if we include metrics
            metrics_width = wcswidth(RIGHT_SOFT_DIVIDER + " ") + 5 + 5 + 6 + wcswidth(RIGHT_DIVIDER)
            full_width = essential_width + metrics_width
            
            # Determine if we have space for metrics
            # We need: left_width + full_width < screen.columns - margin
            include_metrics = (left_width + full_width) < (screen.columns - 5)

            cells = []

            if include_metrics:
                # 1. Start with Soft Separator (backslash variant) and space
                cells.append((BG_METRICS, default_bg, RIGHT_SOFT_DIVIDER + " "))

                # Metrics content
                cpu = get_cpu_cells()
                mem = get_mem_cells()
                bat = get_battery_cells()

                # CPU - pad to fixed width
                for color, text in cpu:
                    padded_text = text.ljust(5)
                    cells.append((color, BG_METRICS, padded_text + " "))
                # Mem - pad to fixed width
                for color, text in mem:
                    padded_text = text.ljust(5)
                    cells.append((color, BG_METRICS, padded_text + " "))
                # Bat - pad to fixed width
                for color, text in bat:
                    padded_text = text.ljust(6)
                    cells.append((color, BG_METRICS, padded_text + " "))

                # 2. Transition to User
                cells.append((BG_USER, BG_METRICS, RIGHT_DIVIDER))
            else:
                # No space for metrics, just essential with soft separator
                cells.append((BG_USER, default_bg, RIGHT_SOFT_DIVIDER + " "))

            # 3. Add User and Clock (essential content)
            cells.append((FG_USER, BG_USER, f" {user_host} "))
            cells.append((BG_CLOCK, BG_USER, RIGHT_DIVIDER))
            cells.append((FG_CLOCK, BG_CLOCK, f"  {clock} "))

            # Cache cells and calculate length
            _right_status_cells = cells
            right_status_length = 0
            for _, _, text in cells:
                right_status_length += wcswidth(str(text))

        # Update cells for the last tab (to get fresh metrics/time for actual drawing)
        if is_last:
            mode_color, _ = _get_mode_color()
            clock = datetime.now().strftime("%H:%M")

            # Colors
            BG_METRICS = CRUST
            BG_USER = SURFACE0
            BG_CLOCK = mode_color

            FG_METRICS = TEXT
            FG_USER = mode_color
            FG_CLOCK = CRUST

            default_bg = as_rgb(int(draw_data.default_bg))

            # Re-check if we should include metrics (based on current left width)
            left_width = _calculate_left_side_width(draw_data, extra_data, all_tabs)
            user_host = (
                f"{os.getenv('USER', 'user')}@{os.uname().nodename.split('.')[0]}"
            )
            essential_cells = [
                (BG_USER, default_bg, RIGHT_DIVIDER),
                (FG_USER, BG_USER, f" {user_host} "),
                (BG_CLOCK, BG_USER, RIGHT_DIVIDER),
                (FG_CLOCK, BG_CLOCK, f"  {clock} "),
            ]
            essential_width = sum(wcswidth(str(t)) for _, _, t in essential_cells)
            metrics_width = wcswidth(RIGHT_SOFT_DIVIDER + " ") + 5 + 5 + 6 + wcswidth(RIGHT_DIVIDER)
            full_width = essential_width + metrics_width
            include_metrics = (left_width + full_width) < (screen.columns - 5)

            cells = []

            if include_metrics:
                # Fetch fresh metrics for drawing
                cpu = get_cpu_cells()
                mem = get_mem_cells()
                bat = get_battery_cells()

                cells.append((BG_METRICS, default_bg, RIGHT_SOFT_DIVIDER + " "))

                for color, text in cpu:
                    padded_text = text.ljust(5)
                    cells.append((color, BG_METRICS, padded_text + " "))
                for color, text in mem:
                    padded_text = text.ljust(5)
                    cells.append((color, BG_METRICS, padded_text + " "))
                for color, text in bat:
                    padded_text = text.ljust(6)
                    cells.append((color, BG_METRICS, padded_text + " "))

                cells.append((BG_USER, BG_METRICS, RIGHT_DIVIDER))
            else:
                cells.append((BG_USER, default_bg, RIGHT_SOFT_DIVIDER + " "))

            cells.append((FG_USER, BG_USER, f" {user_host} "))
            cells.append((BG_CLOCK, BG_USER, RIGHT_DIVIDER))
            cells.append((FG_CLOCK, BG_CLOCK, f"  {clock} "))

            # Recalculate right_status_length with fresh cells
            right_status_length = 0
            for _, _, text in cells:
                right_status_length += wcswidth(str(text))
        else:
            # Use cached cells for non-last tabs
            cells = _right_status_cells

        # Draw left side components - only for first tab to avoid duplicates
        if index == 1:
            orig_bold = screen.cursor.bold
            orig_italic = screen.cursor.italic

            screen.cursor.bold = True
            screen.cursor.italic = False

            _draw_mode_indicator(screen, index, tab=tab, draw_data=draw_data)
            _draw_session_info(screen, index, tab=tab, draw_data=draw_data)

            screen.cursor.bold = orig_bold
            screen.cursor.italic = orig_italic

        # Draw tab with reserved space for right status
        _draw_left_status(
            draw_data,
            screen,
            tab,
            before,
            max_title_length,
            index,
            is_last,
            extra_data,
            reserved_right=right_status_length,
        )
        
        # Only draw right status on last tab
        if is_last:
            _draw_right_status(screen, is_last, cells)
            
        return screen.cursor.x
    except Exception:
        # Silently fail to avoid stderr output that could show as red text
        return screen.cursor.x
