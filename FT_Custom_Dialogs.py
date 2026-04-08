# -*- coding: utf-8 -*-
#
# FT_Custom_Dialogs.py
#
# Reusable WinForms dialog classes for FlexTools modules.
# Supplements the built-in FTDialog* functions with larger,
# resizable dialogs suited to long strings or many items.
#
# Classes:
#   ListChooserDialog   -- scrollable ListBox chooser
#
# Functions (drop-in replacements / supplements for FTDialog*):
#   FTChooseFromList    -- replacement for FTDialogChoose
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
from System.Drawing import Size, Point, Color, Font

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MARGIN   = 10
_BTN_H    = 44   # height of the OK/Cancel panel
_BTN_W    = 80   # individual button width
_BTN_GAP  = 8    # gap between buttons / right edge

_MONO_FONT = None   # lazily created

def _mono_font():
    global _MONO_FONT
    if _MONO_FONT is None:
        _MONO_FONT = Font("Courier New", 9)
    return _MONO_FONT


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
