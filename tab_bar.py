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


_cached_git_branch = ""
_last_git_check = 0.0

def _get_git_branch() -> str:
    """Get current git branch name with caching"""
    global _cached_git_branch, _last_git_check
    now = time.monotonic()
    if now - _last_git_check < 3.0:  # Cache for 3 seconds
        return _cached_git_branch

    try:
        # Get current working directory
        boss = get_boss()
        if boss and boss.active_tab and boss.active_tab.active_window:
            cwd = boss.active_tab.active_window.cwd_of_child or ""
        else:
            cwd = os.getcwd()

        if not cwd or not os.path.exists(cwd):
            _cached_git_branch = ""
            _last_git_check = now
            return ""

        # Check if we're in a git repo
        # Use git rev-parse instead of checking .git dir manually for robustness
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=0.5, # Very short timeout
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            _cached_git_branch = branch if branch and branch != "HEAD" else ""
        else:
            _cached_git_branch = ""
    except Exception:
        _cached_git_branch = ""
    
    _last_git_check = now
    return _cached_git_branch


_cached_process_name = "shell"
_last_process_check = 0.0

def _get_process_name() -> str:
    """Get current process name with caching"""
    global _cached_process_name, _last_process_check
    now = time.monotonic()
    if now - _last_process_check < 2.0:  # Cache for 2 seconds
        return _cached_process_name

    try:
        boss = get_boss()
        if boss and boss.active_tab and boss.active_tab.active_window:
            window = boss.active_tab.active_window
            # Try to get the foreground process name
            # Kitty windows have 'child_name' which is often the shell/process
            process = window.child_name
            if process:
                _cached_process_name = process
            else:
                # Fallback to shell from env
                shell = os.getenv("SHELL", "")
                _cached_process_name = os.path.basename(shell) if shell else "shell"
    except Exception:
        pass
    
    _last_process_check = now
    return _cached_process_name


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


def _wcsljust(s: str, width: int) -> str:
    """Left justify a string based on its visual width (wcswidth)"""
    w = wcswidth(s)
    if w >= width:
        return s
    return s + " " * (width - w)


def _calculate_tab_width(title: str, max_title_length: int) -> int:
    """Calculate the visual width of a tab including its separator"""
    # Truncate title if needed
    w = wcswidth(title)
    if w > max_title_length:
        display_title = title
        while wcswidth(display_title) > max(1, max_title_length - 1):
            display_title = display_title[:-1]
        display_title = display_title + "…"
    else:
        display_title = title
    
    # Tab width = title + " 󰿟 " (space, separator, space)
    return wcswidth(display_title) + wcswidth(" " + SOFT_SEPARATOR_SYMBOL + " ")


def _truncate_to_width(s: str, width: int) -> str:
    """Truncate a string to a specific visual width"""
    if width <= 0:
        return ""
    if wcswidth(s) <= width:
        return s
    res = ""
    curr_w = 0
    for char in s:
        w = wcswidth(char)
        if w < 0: w = 1 # Fallback for unknown chars
        if curr_w + w > width:
            break
        res += char
        curr_w += w
    return res


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
    # IMPORTANT: We ignore Kitty's 'before' entirely and use screen.cursor.x
    # which has been set by draw_tab to follow the previous element sequentially.

    # The maximum position we can draw to for the left side
    # We leave a buffer of 1 cell for safety
    max_x = max(0, screen.columns - reserved_right - 1)
    
    # If the cursor is already past the maximum allowed position, stop drawing
    if screen.cursor.x >= max_x:
        return screen.cursor.x

    # Calculate available space for this tab's title
    # We need room for: title + " 󰿟 " (3 cells)
    needed_for_separator = wcswidth(" " + SOFT_SEPARATOR_SYMBOL + " ")
    available_for_title = max_x - screen.cursor.x - needed_for_separator
    
    if available_for_title < 1:
        # Not even room for one character. Skip.
        return screen.cursor.x

    # Save current colors
    fg, bg = screen.cursor.fg, screen.cursor.bg

    # Reset to default background for tabs
    default_bg = as_rgb(int(draw_data.default_bg))
    screen.cursor.bg = default_bg

    # Get and truncate title
    title = tab.title
    trunc_len = min(max_title_length, available_for_title)
    
    if wcswidth(title) > trunc_len:
        title = _truncate_to_width(title, max(1, trunc_len - 1)) + "…"

    # Tab styling and indicator
    if tab.is_active:
        screen.cursor.fg = SUBTEXT0
        screen.draw(title)
    else:
        screen.cursor.fg = OVERLAY0
        screen.draw(title)

    # Add separator if we have room
    if screen.cursor.x + needed_for_separator <= max_x:
        screen.cursor.fg = OVERLAY0
        screen.draw(" " + SOFT_SEPARATOR_SYMBOL + " ")

    # Restore original colors
    screen.cursor.fg, screen.cursor.bg = fg, bg

    return screen.cursor.x


def _draw_right_status(screen: Screen, is_last: bool, cells: list) -> int:
    if not is_last:
        return 0
    
    # Reset formatting
    draw_attributed_string(Formatter.reset, screen)

    # Note: Cursor position is already set by caller to ensure forward movement

    # Draw each cell defensively
    for fg, bg, text in cells:
        try:
            # Only draw if we are still on screen
            if screen.cursor.x < screen.columns:
                screen.cursor.fg = fg
                screen.cursor.bg = bg
                
                # Truncate text if it would go off-screen
                avail = screen.columns - screen.cursor.x
                if wcswidth(text) > avail:
                    text = _truncate_to_width(text, avail)
                
                if text:
                    screen.draw(text)
        except:
            continue

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
right_status_length = 0  # Initial estimate, will be recalculated on first draw
_tab_bar_current_x = 0  # Global tracker for sequential drawing
_right_status_cells = []  # Cache for right status cells to avoid redundant computation
_right_status_len_cache = 0  # Global stable width for a draw cycle


def _calculate_left_side_width(draw_data, extra_data, tabs) -> int:
    """Calculate the total width of left side (mode + session + all tabs)"""
    # Get current mode for width
    _, mode_name = _get_mode_color()
    # " {icon} {mode_name} " + SEPARATOR_SYMBOL
    mode_width = wcswidth(f"  {mode_name} ") + wcswidth(SEPARATOR_SYMBOL)
    
    # Session info: git branch + process name
    git_branch = _get_git_branch()
    process_name = _get_process_name()
    
    session_width = 0
    if git_branch:
        # Truncate git branch like in _draw_session_info
        MAX_BRANCH_LEN = 25
        if wcswidth(git_branch) > MAX_BRANCH_LEN:
            display_branch = git_branch[:MAX_BRANCH_LEN-1] + "…"
        else:
            display_branch = git_branch
        # "  {branch} " + SEPARATOR_SYMBOL
        session_width += wcswidth(f"  {display_branch} ") + wcswidth(SEPARATOR_SYMBOL)
    else:
        # Just separator from Mode to Process
        session_width += wcswidth(SEPARATOR_SYMBOL)
        
    # " {icon}{process_name} " + SEPARATOR_SYMBOL + " "
    session_width += wcswidth(f"  {process_name} ") + wcswidth(SEPARATOR_SYMBOL) + 1
    
    # If we only want the fixed header width
    if not tabs:
        return mode_width + session_width
        
    # Calculate width of all tabs
    tab_widths = 0
    # Use a conservative max length if not provided
    max_len = getattr(opts, "tab_title_max_length", 32)
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
        global _right_status_len_cache
        global _tab_bar_current_x

        if timer_id is None:
            timer_id = add_timer(_redraw_tab_bar, REFRESH_TIME, True)

        # Initialize or update sequential tracker
        if index == 1:
            _tab_bar_current_x = 0
            right_status_length = 0
        
        # Always set cursor to where we finished the last element
        screen.cursor.x = _tab_bar_current_x

        # Get all tabs to calculate actual left side width
        boss = get_boss()
        if not boss or not boss.active_tab_manager:
            return screen.cursor.x
            
        all_tabs = boss.active_tab_manager.tabs

        # Calculate right status cells for first tab (determines layout for all tabs)
        if index == 1 or not _right_status_cells:
            try:
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

                # Calculate header width (mode + session)
                header_width = _calculate_left_side_width(draw_data, extra_data, [])
                
                # Calculate user/host and clock essential width
                user_host = f"{os.getenv('USER', 'user')}@{os.uname().nodename.split('.')[0]}"
                
                essential_width = (
                    wcswidth(RIGHT_SOFT_DIVIDER + " ") + 
                    wcswidth(f" {user_host} ") + 
                    wcswidth(RIGHT_DIVIDER) + 
                    wcswidth(f"  {clock} ")
                )
                
                # Metrics estimate
                metrics_width = 5 + 5 + 6 + 3 # 3 spaces between them
                full_width = essential_width + metrics_width + wcswidth(RIGHT_DIVIDER)
                
                # Determine if we have space for metrics
                include_metrics = (header_width + full_width + (len(all_tabs) * 5)) < (screen.columns - 2)

                cells = []

                if include_metrics:
                    cells.append((BG_METRICS, default_bg, RIGHT_SOFT_DIVIDER + " "))
                    cpu = get_cpu_cells()
                    mem = get_mem_cells()
                    bat = get_battery_cells()

                    for color, text in cpu:
                        cells.append((color, BG_METRICS, _wcsljust(text, 5) + " "))
                    for color, text in mem:
                        cells.append((color, BG_METRICS, _wcsljust(text, 5) + " "))
                    for color, text in bat:
                        cells.append((color, BG_METRICS, _wcsljust(text, 6) + " "))

                    cells.append((BG_USER, BG_METRICS, RIGHT_DIVIDER))
                else:
                    cells.append((BG_USER, default_bg, RIGHT_SOFT_DIVIDER + " "))

                cells.append((FG_USER, BG_USER, f" {user_host} "))
                cells.append((BG_CLOCK, BG_USER, RIGHT_DIVIDER))
                cells.append((FG_CLOCK, BG_CLOCK, f"  {clock} "))

                _right_status_cells = cells
                _right_status_len_cache = 0
                for _, _, text in cells:
                    _right_status_len_cache += wcswidth(str(text))
                
                right_status_length = _right_status_len_cache
            except Exception:
                # If calculation fails, fall back to safe empty state
                _right_status_cells = []
                _right_status_len_cache = 0
                right_status_length = 0
        else:
            cells = _right_status_cells
            right_status_length = _right_status_len_cache

        # Draw components
        if index == 1:
            orig_bold = screen.cursor.bold
            orig_italic = screen.cursor.italic
            screen.cursor.bold = True
            screen.cursor.italic = False
            _tab_bar_current_x = _draw_mode_indicator(screen, index, tab=tab, draw_data=draw_data)
            screen.cursor.x = _tab_bar_current_x
            _tab_bar_current_x = _draw_session_info(screen, index, tab=tab, draw_data=draw_data)
            screen.cursor.bold = orig_bold
            screen.cursor.italic = orig_italic

        # Recalculate max_title_length to account for our custom left/right sections
        num_tabs = len(all_tabs)
        if num_tabs > 0:
            # Estimate available space for tabs
            header_width = _calculate_left_side_width(draw_data, extra_data, [])
            available_for_tabs = screen.columns - header_width - right_status_length - 2
            
            # Divide available space equally among tabs
            custom_max_title_len = max(1, (available_for_tabs // num_tabs) - 3)
            effective_max_len = min(max_title_length, custom_max_title_len)
        else:
            effective_max_len = max_title_length

        # Sync cursor to current tracker before drawing tab
        screen.cursor.x = _tab_bar_current_x

        # The end position of the left status (tabs)
        _tab_bar_current_x = _draw_left_status(
            draw_data,
            screen,
            tab,
            before,
            effective_max_len,
            index,
            is_last,
            extra_data,
            reserved_right=right_status_length,
        )
        
        # Only draw right status on last tab
        if is_last:
            # Explicitly set background color for the spacer and right status
            screen.cursor.bg = as_rgb(int(draw_data.default_bg))
            
            # Ensure we only move forward or stay put
            right_start_x = max(_tab_bar_current_x, screen.columns - right_status_length)
            
            # Fill the gap if any
            if right_start_x > _tab_bar_current_x:
                screen.cursor.x = _tab_bar_current_x
                screen.draw(" " * (right_start_x - _tab_bar_current_x))
            
            screen.cursor.x = right_start_x
            _tab_bar_current_x = _draw_right_status(screen, is_last, cells)
            
        return screen.cursor.x
    except Exception:
        return screen.cursor.x
