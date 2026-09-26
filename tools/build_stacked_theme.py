"""Build a stacked-accounts theme: one row per account, reset times on demand.

The classic theme puts providers side by side and prints the reset time next to
every percentage. This one gives every account its own row and keeps the reset
times in an overlay that a click reveals, because the theme engine has no hover
state to drive it.
"""

import io
import json
import os

SOURCE = os.path.join(os.path.expanduser('~'), 'QuotaBar', 'src', 'themes', 'classic-usage-widget.json')
TARGET_DIR = os.path.join(os.environ['APPDATA'], 'ClaudeCodeUsageMonitor', 'themes')
TARGET = os.path.join(TARGET_DIR, 'stacked-accounts.json')

# Rows, in display order: (object id suffix, context prefix, label, accent)
ROWS = [
    ('claude-default', 'accounts.claude.default', 'Geist', '#D97757FF'),
    ('claude-lab', 'accounts.claude.lab', 'Spielvogel', '#D97757FF'),
    ('claude-privat', 'accounts.claude.privat', 'Privat', '#D97757FF'),
    ('codex-default', 'accounts.codex.default', 'Codex', '#F5F5F5FF'),
]

ROW_HEIGHT = 15
ROW_GAP = 3
PAD_TOP = 5
PAD_LEFT = 8

LABEL_W = 62
BAR_W = 66
BAR_H = 11
VALUE_W = 34
GAP = 5

WINDOWS = [('session', '5h'), ('weekly', '7d')]

CARD_W = PAD_LEFT * 2 + LABEL_W + 2 * (BAR_W + GAP + VALUE_W) + GAP
# Rows collapse when an account has no data, so the card height follows along.
VISIBLE = ' + '.join(f'max({prefix}.available, {prefix}.has_error)' for _, prefix, _, _ in ROWS)
CARD_H = f'{PAD_TOP * 2 - ROW_GAP} + max(1, {VISIBLE}) * {ROW_HEIGHT + ROW_GAP}'

TEXT = {
    'font_family': 'Segoe UI',
    'font_size': '12',
    'weight': 'medium',
    'rendering': 'clear_type',
    'contrast': '1',
    'align': 'left',
}

# Text colours per system theme: the floating card is dark in dark mode and
# light in light mode, so every label exists once for each.
PALETTE = {
    'dark': {'label': '#9A9A9AFF', 'value': '#F0F0F0FF', 'track': '#4A4A4AFF', 'overlay_bg': '#1E1E1EFF', 'overlay': '#E8E8E8FF'},
    'light': {'label': '#5A5A5AFF', 'value': '#1F1F1FFF', 'track': '#B8B8B8FF', 'overlay_bg': '#FAFAFAFF', 'overlay': '#1F1F1FFF'},
}
RENDER = {'dark': 'system.dark', 'light': '1 - system.dark'}


def text_object(oid, name, parent, x, y, width, template, colour, render, align='left'):
    content = dict(TEXT, type='text', template=template, align=align, color={'color': colour})
    return {
        'id': oid,
        'name': name,
        'parent': parent,
        'render': render,
        'x': str(x),
        'y': str(y),
        'width': str(width),
        'height': '13',
        'content': content,
    }


def progress_object(oid, name, parent, x, y, value, fill, track, render):
    return {
        'id': oid,
        'name': name,
        'parent': parent,
        'render': render,
        'x': str(x),
        'y': str(y),
        'width': str(BAR_W),
        'height': str(BAR_H),
        'content': {
            'type': 'progress',
            'value': value,
            'direction': 'left_to_right',
            'fill': {'color': fill},
            'track': {'color': track},
            'corner_radius': '2',
            'segments': 6,
            'segment_gap': '1',
        },
    }


def build_children():
    children = [
        {
            'id': 'rows',
            'name': 'Accounts',
            'x': str(PAD_LEFT),
            'y': str(PAD_TOP),
            'width': str(CARD_W - 2 * PAD_LEFT),
            'height': f'canvas.height - {PAD_TOP * 2}',
            'layout': 'column',
            'gap': str(ROW_GAP),
        }
    ]

    for suffix, prefix, label, accent in ROWS:
        row_id = f'row-{suffix}'
        children.append({
            'id': row_id,
            'name': f'{label} row',
            'parent': 'rows',
            # A row collapses only for an account that has nothing to say at
            # all. One that errors keeps its place and shows "!", so a expired
            # login is visible instead of silently missing.
            'render': f'max({prefix}.available, {prefix}.has_error)',
            'width': str(CARD_W - 2 * PAD_LEFT),
            'height': str(ROW_HEIGHT),
        })

        for mode, colours in PALETTE.items():
            render = RENDER[mode]
            children.append(text_object(
                f'{row_id}-label-{mode}', f'{label} label ({mode})', row_id,
                0, 1, LABEL_W, label, colours['label'], render))

            x = LABEL_W
            for window, _ in WINDOWS:
                children.append(progress_object(
                    f'{row_id}-{window}-bar-{mode}', f'{label} {window} bar ({mode})', row_id,
                    x, 2, f'{prefix}.{window}.display', accent, colours['track'], render))
                children.append(text_object(
                    f'{row_id}-{window}-value-{mode}', f'{label} {window} value ({mode})', row_id,
                    x + BAR_W + GAP, 1, VALUE_W,
                    '{' + f'{prefix}.{window}.display:usage_badge' + '}',
                    colours['value'], render))
                x += BAR_W + GAP + VALUE_W + GAP

    # The overlay: hidden until a click turns it on, then it covers the rows
    # with the reset time of every window. It repeats the same column layout so
    # its lines stay aligned with the rows they describe, including the ones
    # that collapse for accounts without data.
    children.append({
        'id': 'reset-overlay',
        'name': 'Reset times',
        'render': '0',
        'x': '0',
        'y': '0',
        'width': 'canvas.width',
        'height': 'canvas.height',
    })
    for mode, colours in PALETTE.items():
        children.append({
            'id': f'reset-overlay-backdrop-{mode}',
            'name': f'Reset backdrop ({mode})',
            'parent': 'reset-overlay',
            'render': RENDER[mode],
            'x': '0',
            'y': '0',
            'width': 'canvas.width',
            'height': 'canvas.height',
            'background': {'type': 'colour', 'colour': {'color': colours['overlay_bg']}},
            'corner_radius': '6',
        })
    children.append({
        'id': 'reset-rows',
        'name': 'Reset lines',
        'parent': 'reset-overlay',
        'x': str(PAD_LEFT),
        'y': str(PAD_TOP),
        'width': str(CARD_W - 2 * PAD_LEFT),
        'height': f'canvas.height - {PAD_TOP * 2}',
        'layout': 'column',
        'gap': str(ROW_GAP),
    })
    for suffix, prefix, label, _ in ROWS:
        row_id = f'reset-row-{suffix}'
        children.append({
            'id': row_id,
            'name': f'{label} reset row',
            'parent': 'reset-rows',
            'render': f'max({prefix}.available, {prefix}.has_error)',
            'width': str(CARD_W - 2 * PAD_LEFT),
            'height': str(ROW_HEIGHT),
        })
        for mode, colours in PALETTE.items():
            children.append(text_object(
                f'{row_id}-{mode}', f'{label} resets ({mode})', row_id,
                0, 1, CARD_W - 2 * PAD_LEFT,
                label + ':  5h ' + '{' + f'{prefix}.session.display:usage_reset_line' + '}'
                + '   7d ' + '{' + f'{prefix}.weekly.display:usage_reset_line' + '}',
                colours['overlay'], RENDER[mode]))
    return children


def main():
    document = json.load(io.open(SOURCE, encoding='utf-8'))
    document['id'] = 'stacked-accounts'
    document['name'] = 'Accounts untereinander'

    main_surface = next(surface for surface in document['surfaces'] if surface['id'] == 'main')
    main_surface['name'] = 'Accounts stacked'
    main_surface['width'] = str(CARD_W)
    main_surface['height'] = CARD_H
    main_surface['mouse_events'] = {
        'click': 'toggle("reset-overlay", render)',
        'right_click': 'show_context_menu("classic-v1")',
    }
    main_surface['children'] = build_children()

    os.makedirs(TARGET_DIR, exist_ok=True)
    io.open(TARGET, 'w', encoding='utf-8', newline='\n').write(json.dumps(document, indent=2) + '\n')
    print(f'{TARGET} geschrieben: {len(main_surface["children"])} Objekte, Karte {CARD_W}px breit')
    print('Höhe:', CARD_H)


if __name__ == '__main__':
    main()
