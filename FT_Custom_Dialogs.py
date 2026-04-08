# -*- coding: utf-8 -*-
#
# FT_Custom_Dialogs.py
#
# Reusable WinForms dialog classes for FlexTools modules.
# Supplements the built-in FTDialog* functions with larger,
# resizable dialogs suited to long strings or many items.
#
# Classes:
#   ListChooserDialog     -- scrollable ListBox chooser
#   AnalysisPickerDialog  -- sequential per-wordform analysis picker
#
# Functions (drop-in replacements / supplements for FTDialog*):
#   FTChooseFromList  -- replacement for FTDialogChoose
#   FTPickAnalysis    -- sequential analysis picker for Merge Analyses workflow
#

import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from System.Windows.Forms import (
    Form, Label, ListBox, Button, Panel,
    FormStartPosition, FormBorderStyle,
    DockStyle, AnchorStyles, DialogResult,
    SelectionMode,
)
from System.Drawing import Size, Point, Color, Font, FontStyle

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MARGIN   = 10
_BTN_H    = 44   # height of the OK/Cancel panel
_BTN_W    = 80   # individual button width
_BTN_GAP  = 8    # gap between buttons / right edge

_MONO_FONT = None   # lazily created
_BOLD_FONT = None

def _mono_font():
    global _MONO_FONT
    if _MONO_FONT is None:
        _MONO_FONT = Font("Courier New", 9)
    return _MONO_FONT

def _bold_font(size=13):
    global _BOLD_FONT
    if _BOLD_FONT is None:
        _BOLD_FONT = Font("Segoe UI", size, FontStyle.Bold)
    return _BOLD_FONT


def _apply_icon(dlg):
    """Apply the FlexTools application icon if available (safe no-op otherwise)."""
    try:
        from flextoolslib.code import UIGlobal
        dlg.Icon = UIGlobal.ApplicationIcon
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ListChooserDialog
# ---------------------------------------------------------------------------

class ListChooserDialog(Form):
    """
    Modal chooser dialog backed by a scrollable, resizable ListBox.

    Wider and more readable than the built-in FTDialogChoose (which uses a
    small 300px-wide ComboBox dropdown).  Supports double-click to confirm.

    Parameters
    ----------
    prompt      Full prompt / instruction text shown above the list.
                Newlines are supported.
    items       Iterable of strings to populate the list.
    width       Initial client width in pixels  (default 600).
    height      Initial client height in pixels (default 400).
    monospace   Use Courier New 9pt for the list items (default False).
                Useful when items are formatted in columns.

    Usage
    -----
        dlg = ListChooserDialog("Pick one:", items, monospace=True)
        result = dlg.Show()   # returns selected string, or None if cancelled
    """

    def __init__(self, prompt, items,
                 width=600, height=400, monospace=False):
        Form.__init__(self)

        # ---- Window chrome -----------------------------------------------
        # Use the first line of the prompt as the title-bar text.
        self.Text = prompt.split('\n')[0][:80]
        self.ClientSize = Size(width, height)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.MinimizeBox = False
        self.MaximizeBox = True
        self.MinimumSize = Size(400, 280)

        self.SelectedValue = None

        M = _MARGIN

        # ---- Prompt label ------------------------------------------------
        # Height scales with newline count so the text is never clipped.
        label_h = max(36, prompt.count('\n') * 18 + 22)
        label = Label()
        label.Text = prompt
        label.Location = Point(M, M)
        label.Size = Size(width - M * 2, label_h)
        label.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
        self.Controls.Add(label)

        # ---- ListBox -----------------------------------------------------
        lb_top = M + label_h + 4
        lb_h   = height - lb_top - _BTN_H - M
        self._listbox = ListBox()
        self._listbox.Location = Point(M, lb_top)
        self._listbox.Size = Size(width - M * 2, lb_h)
        self._listbox.Anchor = (AnchorStyles.Top    | AnchorStyles.Bottom |
                                AnchorStyles.Left   | AnchorStyles.Right)
        self._listbox.SelectionMode = SelectionMode.One
        self._listbox.HorizontalScrollbar = True
        self._listbox.IntegralHeight = False  # allows partial rows on resize

        if monospace:
            self._listbox.Font = _mono_font()

        for item in items:
            self._listbox.Items.Add(str(item))

        if self._listbox.Items.Count > 0:
            self._listbox.SelectedIndex = 0

        # Double-click confirms immediately
        self._listbox.DoubleClick += lambda s, e: self._confirm()
        self.Controls.Add(self._listbox)

        # ---- OK / Cancel panel -------------------------------------------
        btn_panel = Panel()
        btn_panel.Height = _BTN_H
        btn_panel.Dock = DockStyle.Bottom
        btn_panel.BackColor = Color.LightGray
        self.Controls.Add(btn_panel)

        right = width - _BTN_GAP
        ok_btn = Button()
        ok_btn.Text = "OK"
        ok_btn.Size = Size(_BTN_W, 26)
        ok_btn.Location = Point(right - (_BTN_W + _BTN_GAP) * 2 + _BTN_GAP, 9)
        ok_btn.Anchor = AnchorStyles.Right | AnchorStyles.Top
        ok_btn.DialogResult = DialogResult.OK
        btn_panel.Controls.Add(ok_btn)

        cancel_btn = Button()
        cancel_btn.Text = "Cancel"
        cancel_btn.Size = Size(_BTN_W, 26)
        cancel_btn.Location = Point(right - _BTN_W, 9)
        cancel_btn.Anchor = AnchorStyles.Right | AnchorStyles.Top
        cancel_btn.DialogResult = DialogResult.Cancel
        btn_panel.Controls.Add(cancel_btn)

        self.AcceptButton = ok_btn
        self.CancelButton = cancel_btn
        self.ActiveControl = self._listbox

    def _confirm(self):
        """Accept the current selection (called on double-click)."""
        if self._listbox.SelectedItem is not None:
            self.DialogResult = DialogResult.OK
            self.Close()

    def Show(self):
        """Display the dialog modally. Returns the selected string or None."""
        result = self.ShowDialog()
        if result == DialogResult.OK and self._listbox.SelectedItem is not None:
            self.SelectedValue = str(self._listbox.SelectedItem)
        return self.SelectedValue


# ---------------------------------------------------------------------------
# AnalysisPickerDialog
# ---------------------------------------------------------------------------

class AnalysisPickerDialog(Form):
    """
    Sequential per-wordform analysis picker for the Merge Analyses workflow.

    Shows one wordform at a time with all its analyses. The user picks
    which analysis to keep, skips the wordform, jumps to a different one
    via Browse All, or cancels entirely.

    Parameters
    ----------
    wordform        Vernacular string for the current wordform.
    analyses        List of strings describing each analysis (monospace).
    current_idx     0-based index of this wordform in the remaining list.
    total           Total number of remaining wordforms.
    all_wordforms   List of strings for all remaining wordforms (for Browse All).
    width / height  Initial dialog size.

    Usage
    -----
        action, value = AnalysisPickerDialog(...).Show()

    Return values
    -------------
        ('keep',   int)   -- keep the analysis at this index
        ('skip',   None)  -- skip this wordform
        ('jump',   int)   -- jump to the wordform at this index in all_wordforms
        ('cancel', None)  -- stop processing entirely
    """

    def __init__(self, wordform, analyses, current_idx, total, all_wordforms,
                 width=720, height=400):
        Form.__init__(self)

        self.Text = "Merge Analyses"
        self.ClientSize = Size(width, height)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.MinimizeBox = False
        self.MaximizeBox = True
        self.MinimumSize = Size(520, 320)

        self._result = ('cancel', None)
        self._all_wordforms = list(all_wordforms)

        M = _MARGIN

        # ---- Status: "Wordform 3 of 12:" --------------------------------
        status = Label()
        status.Text = "Wordform {0} of {1}:".format(current_idx + 1, total)
        status.Location = Point(M, M)
        status.Size = Size(width - M * 2, 18)
        status.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
        self.Controls.Add(status)

        # ---- Wordform name (large bold) ----------------------------------
        wf_label = Label()
        wf_label.Text = wordform
        wf_label.Location = Point(M, M + 20)
        wf_label.Size = Size(width - M * 2, 28)
        wf_label.Font = _bold_font(13)
        wf_label.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
        self.Controls.Add(wf_label)

        # ---- Instruction ------------------------------------------------
        instruction = Label()
        instruction.Text = "Select the analysis to KEEP, then click Keep Selected (or double-click):"
        instruction.Location = Point(M, M + 52)
        instruction.Size = Size(width - M * 2, 18)
        instruction.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
        self.Controls.Add(instruction)

        # ---- Analyses ListBox -------------------------------------------
        LB_TOP = M + 52 + 20 + 4
        LB_H = height - LB_TOP - _BTN_H - M
        self._listbox = ListBox()
        self._listbox.Location = Point(M, LB_TOP)
        self._listbox.Size = Size(width - M * 2, LB_H)
        self._listbox.Anchor = (AnchorStyles.Top    | AnchorStyles.Bottom |
                                AnchorStyles.Left   | AnchorStyles.Right)
        self._listbox.SelectionMode = SelectionMode.One
        self._listbox.HorizontalScrollbar = True
        self._listbox.IntegralHeight = False
        self._listbox.Font = _mono_font()

        for ana in analyses:
            self._listbox.Items.Add(str(ana))
        if self._listbox.Items.Count > 0:
            self._listbox.SelectedIndex = 0

        self._listbox.DoubleClick += lambda s, e: self._keep()
        self.Controls.Add(self._listbox)

        # ---- Button panel -----------------------------------------------
        # Right to left: Cancel | Browse All... | Skip | Keep Selected
        btn_panel = Panel()
        btn_panel.Height = _BTN_H
        btn_panel.Dock = DockStyle.Bottom
        btn_panel.BackColor = Color.LightGray
        self.Controls.Add(btn_panel)

        W_KEEP   = 120
        W_SKIP   = 80
        W_BROWSE = 110
        W_CANCEL = 80
        G = _BTN_GAP

        x = width - G
        for text, w, handler in [
            ("Cancel",       W_CANCEL, self._cancel),
            ("Browse All...", W_BROWSE, self._browse),
            ("Skip",         W_SKIP,   self._skip),
            ("Keep Selected", W_KEEP,  self._keep),
        ]:
            x -= w
            btn = Button()
            btn.Text = text
            btn.Size = Size(w, 26)
            btn.Location = Point(x, 9)
            btn.Anchor = AnchorStyles.Right | AnchorStyles.Top
            btn.Click += lambda s, e, h=handler: h()
            btn_panel.Controls.Add(btn)
            x -= G

            if text == "Keep Selected":
                self.AcceptButton = btn
            if text == "Cancel":
                self.CancelButton = btn

        self.ActiveControl = self._listbox

    # ---- Button handlers ------------------------------------------------

    def _keep(self):
        if self._listbox.SelectedIndex >= 0:
            self._result = ('keep', self._listbox.SelectedIndex)
            self.DialogResult = DialogResult.OK
            self.Close()

    def _skip(self):
        self._result = ('skip', None)
        self.DialogResult = DialogResult.OK
        self.Close()

    def _browse(self):
        chosen = FTChooseFromList(
            "Jump to a wordform:",
            self._all_wordforms,
            width=500, height=350,
        )
        if chosen and chosen in self._all_wordforms:
            self._result = ('jump', self._all_wordforms.index(chosen))
            self.DialogResult = DialogResult.OK
            self.Close()

    def _cancel(self):
        self._result = ('cancel', None)
        self.DialogResult = DialogResult.OK
        self.Close()

    def Show(self):
        """Display modally. Returns (action, value) — see class docstring."""
        self.ShowDialog()
        return self._result


# ---------------------------------------------------------------------------
# Public functional wrappers
# ---------------------------------------------------------------------------

def FTChooseFromList(prompt, items,
                     width=600, height=400, monospace=False):
    """
    Drop-in replacement for FTDialogChoose that uses a scrollable, resizable
    ListBox instead of a small ComboBox dropdown.

    Parameters
    ----------
    prompt      Instruction text shown above the list (newlines supported).
    items       Iterable of strings to display.
    width       Initial dialog width  (default 600).
    height      Initial dialog height (default 400).
    monospace   Use a monospace font for list items (default False).

    Returns
    -------
    The selected string, or None if the user cancelled.
    """
    dlg = ListChooserDialog(prompt, items,
                            width=width, height=height, monospace=monospace)
    _apply_icon(dlg)
    return dlg.Show()


def FTPickAnalysis(wordform, analyses, current_idx, total, all_wordforms,
                   width=720, height=400):
    """
    Show a sequential analysis picker for the Merge Analyses workflow.

    Parameters
    ----------
    wordform        Vernacular string for the current wordform.
    analyses        List of strings describing each analysis.
    current_idx     0-based position in the remaining wordform list.
    total           Total remaining wordforms.
    all_wordforms   Full list of remaining wordform labels (for Browse All).
    width / height  Initial dialog size.

    Returns
    -------
    (action, value) tuple:
        ('keep',   int)   keep analysis at this index
        ('skip',   None)  skip this wordform
        ('jump',   int)   jump to wordform at this index in all_wordforms
        ('cancel', None)  stop entirely
    """
    dlg = AnalysisPickerDialog(wordform, analyses, current_idx, total,
                               all_wordforms, width=width, height=height)
    _apply_icon(dlg)
    return dlg.Show()
