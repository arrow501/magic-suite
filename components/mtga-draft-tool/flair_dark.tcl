# MTGA Draft Tool - Custom Theme: "Gnome Rose"
# Neutral gray with desaturated brown undertones + muted pink-magenta accent (#D56199)

if {[lsearch [ttk::style theme names] flair_dark] == -1} {

    ttk::style theme create flair_dark -parent clam -settings {

        # --- 1. DEFINE COLORS ---
        set bg          "#222226"  ;# Main Background
        set fg          "#F8F8F2"  ;# Main Text (warm off-white)
        set fieldbg     "#28282C"  ;# Input/Table Background
        set raised      "#343437"  ;# Raised surfaces / hover
        set selectbg    "#D56199"  ;# Accent (muted pink-magenta)
        set selectfg    "#F8F8F2"  ;# Text on accent
        set disabledbg  "#28282C"  ;# Disabled Background
        set disabledfg  "#9B948E"  ;# Muted Text (desaturated brown-gray)
        set bordercol   "#343437"  ;# Standard border color

        # --- 2. FONTS ---
        font create FlairDarkTitleFont -family "Ubuntu" -size 11 -weight bold
        font create FlairDarkStandardFont -family "Ubuntu" -size 10
        font create FlairDarkSmallFont -family "Ubuntu" -size 9

        # --- 3. GLOBAL DEFAULTS (.) ---
        ttk::style configure . \
            -background $bg \
            -foreground $fg \
            -fieldbackground $fieldbg \
            -troughcolor $bg \
            -selectbackground $selectbg \
            -selectforeground $selectfg \
            -insertcolor $fg \
            -font FlairDarkStandardFont \
            -borderwidth 0 \
            -bordercolor $bordercol

        ttk::style map . \
            -foreground [list disabled $disabledfg] \
            -background [list disabled $disabledbg]

        # --- 4. SPECIFIC WIDGET OVERRIDES ---

        ttk::style configure TFrame -background $bg
        ttk::style configure Card.TFrame -background $fieldbg -relief flat -borderwidth 0

        ttk::style configure TLabel -background $bg -foreground $fg
        ttk::style configure Muted.TLabel -foreground $disabledfg -font FlairDarkSmallFont

        ttk::style configure TButton -padding {8 4} -relief flat -background $fieldbg -foreground $fg
        ttk::style map TButton \
            -background [list active $selectbg disabled $disabledbg] \
            -foreground [list active $selectfg disabled $disabledfg]

        ttk::style configure TCheckbutton -background $bg -foreground $fg -indicatorcolor $fieldbg
        ttk::style map TCheckbutton \
            -background [list active $bg] \
            -indicatorcolor [list selected $selectbg active $raised] \
            -foreground [list active $selectbg]

        ttk::style configure TMenubutton -background $fieldbg -foreground $fg -padding {5 2} -relief flat
        ttk::style map TMenubutton \
            -background [list active $selectbg disabled $disabledbg] \
            -foreground [list active $selectfg disabled $disabledfg]

        ttk::style configure TEntry -fieldbackground $fieldbg -foreground $fg -padding 4
        ttk::style configure TCombobox -fieldbackground $fieldbg -background $bg -foreground $fg -arrowcolor $selectbg
        ttk::style map TCombobox \
            -fieldbackground [list active $fieldbg focus $fieldbg] \
            -selectbackground [list active $selectbg focus $selectbg] \
            -selectforeground [list active $selectfg focus $selectfg]

        ttk::style configure Treeview -background $fieldbg -fieldbackground $fieldbg -foreground $fg -borderwidth 0 -font FlairDarkStandardFont
        ttk::style map Treeview \
            -background [list selected $selectbg] \
            -foreground [list selected $selectfg]

        ttk::style configure Treeview.Heading -background $bg -foreground $selectbg -font FlairDarkTitleFont -relief flat -padding 5
        ttk::style map Treeview.Heading \
            -background [list active $raised] \
            -foreground [list active $fg]

        ttk::style configure TNotebook -background $bg -tabmargins {0 0 0 0}
        ttk::style configure TNotebook.Tab -background $bg -foreground $fg -padding {12 6} -font FlairDarkTitleFont -borderwidth 0
        ttk::style map TNotebook.Tab \
            -background [list selected $fieldbg active $raised] \
            -foreground [list selected $selectbg active $fg]

        ttk::style configure TProgressbar -background $selectbg -troughcolor $fieldbg -borderwidth 0

        ttk::style configure TScrollbar -background $fieldbg -troughcolor $bg -arrowcolor $selectbg -relief flat
        ttk::style map TScrollbar -background [list active $selectbg]

        ttk::style configure TPanedwindow -background $bg
        ttk::style configure Sash \
            -background $bg \
            -bordercolor $bg \
            -lightcolor $bg \
            -darkcolor $bg \
            -sashthickness 8 \
            -sashrelief flat

        ttk::style map Sash \
            -background [list active $selectbg]
    }
}

# --- 4b. TTKBOOTSTRAP BOOTSTYLE ALIASES ---
# The app uses ttkbootstrap bootstyles on some widgets (top bar buttons, labels).
# With a custom tcl theme those styles don't exist, so define them here.
        ttk::style configure primary.TButton -background $selectbg -foreground $selectfg -relief flat -padding {8 4}
        ttk::style map primary.TButton -background [list active $raised]
        ttk::style configure secondary.TButton -background $raised -foreground $fg -relief flat -padding {8 4}
        ttk::style map secondary.TButton -background [list active $selectbg]
        ttk::style configure success.TButton -background "#57A773" -foreground $selectfg -relief flat -padding {8 4}
        ttk::style configure info.TButton -background "#7B9EC7" -foreground $selectfg -relief flat -padding {8 4}
        ttk::style configure warning.TButton -background "#C9A227" -foreground $selectfg -relief flat -padding {8 4}
        ttk::style configure danger.TButton -background "#C6465A" -foreground $selectfg -relief flat -padding {8 4}

        foreach bs {primary secondary success info warning danger} {
            ttk::style configure ${bs}.Outline.TButton -background $fieldbg -foreground $fg -relief flat -padding {8 4}
            ttk::style map ${bs}.Outline.TButton \
                -background [list active $raised] \
                -foreground [list active $fg]
            ttk::style configure ${bs}.Link.TButton -background $bg -foreground $fg -relief flat -padding {8 4}
            ttk::style map ${bs}.Link.TButton \
                -background [list active $raised] \
                -foreground [list active $selectbg]
            ttk::style configure ${bs}.TFrame -background $bg
            ttk::style configure ${bs}.TLabel -background $bg -foreground $fg
            ttk::style configure ${bs}.TLabelframe -background $bg -foreground $fg
            ttk::style configure ${bs}.TLabelframe.Label -background $bg -foreground $fg
        }
        ttk::style configure secondary.TFrame -background $fieldbg
        ttk::style configure primary.TLabel -foreground $selectbg
        ttk::style configure secondary.TLabel -foreground $disabledfg

# --- 5. NATIVE OS MENU + CLASSIC TK WIDGET OVERRIDES ---
# Menus and classic (non-ttk) widgets ignore ttk styles, so set them globally.
option add *Menu.background "#28282C"
option add *Menu.foreground "#F8F8F2"
option add *Menu.activeBackground "#D56199"
option add *Menu.activeForeground "#F8F8F2"
option add *Menu.selectcolor "#D56199"
option add *Menu.font "Ubuntu 10"

option add *background "#222226"
option add *foreground "#F8F8F2"
option add *Button.background "#28282C"
option add *Button.foreground "#F8F8F2"
option add *Button.activeBackground "#D56199"
option add *Button.activeForeground "#F8F8F2"
option add *Button.highlightBackground "#222226"
option add *Entry.background "#28282C"
option add *Entry.foreground "#F8F8F2"
option add *Entry.insertBackground "#F8F8F2"
option add *Entry.selectBackground "#D56199"
option add *Entry.selectForeground "#F8F8F2"
option add *Text.background "#28282C"
option add *Text.foreground "#F8F8F2"
option add *Text.insertBackground "#F8F8F2"
option add *Text.selectBackground "#D56199"
option add *Text.selectForeground "#F8F8F2"
option add *Listbox.background "#28282C"
option add *Listbox.foreground "#F8F8F2"
option add *Listbox.selectBackground "#D56199"
option add *Listbox.selectForeground "#F8F8F2"
option add *Canvas.background "#222226"
option add *highlightBackground "#343437"
option add *highlightColor "#D56199"

# --- 6. ACTIVATE THE THEME ---
ttk::style theme use flair_dark
