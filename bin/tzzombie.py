#!/usr/bin/env python3
# TOKEN ZOMBIE dashboard mascot: one layered SVG (gradients, soft shadows, glow) of a zombie sitting on the
# dashboard's top edge, both hands gripping it, legs dangling in front. CSS-only animation (the dashboard CSP
# allows inline style, no script). No external assets, no network.
# Visual states: idle | working | excited | alert | sleep  (see visual_state()).
import time

VSTATES = ('idle', 'working', 'excited', 'alert', 'sleep')
EDGE_Y, VB_W, VB_H = 170, 260, 320  # the card's top edge sits at y=170 of the viewBox

DEFS = """<defs>
<radialGradient id="tzSkin" cx="38%" cy="28%" r="78%"><stop offset="0" stop-color="#c8ec8a"/><stop offset=".42" stop-color="#86b851"/><stop offset=".78" stop-color="#4f7d2f"/><stop offset="1" stop-color="#2c4a1b"/></radialGradient>
<radialGradient id="tzSkinB" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="#a9d870"/><stop offset=".6" stop-color="#6b9c40"/><stop offset="1" stop-color="#34561f"/></radialGradient>
<linearGradient id="tzShirt" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5d4b8c"/><stop offset=".55" stop-color="#3b2f60"/><stop offset="1" stop-color="#211a38"/></linearGradient>
<linearGradient id="tzPants" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#5a6f96"/><stop offset=".5" stop-color="#3d4c6b"/><stop offset="1" stop-color="#262f45"/></linearGradient>
<linearGradient id="tzShoe" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a372c"/><stop offset="1" stop-color="#1c130e"/></linearGradient>
<radialGradient id="tzEye" cx="45%" cy="45%" r="60%"><stop offset="0" stop-color="#fbffd0"/><stop offset=".3" stop-color="#d6ff5c"/><stop offset=".7" stop-color="#6fe81f"/><stop offset="1" stop-color="#2f9a0c"/></radialGradient>
<radialGradient id="tzHalo" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#9dff3a" stop-opacity=".55"/><stop offset="1" stop-color="#9dff3a" stop-opacity="0"/></radialGradient>
<radialGradient id="tzAO" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#0b1406" stop-opacity=".75"/><stop offset="1" stop-color="#0b1406" stop-opacity="0"/></radialGradient>
<radialGradient id="tzBruise" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#6b3f7a" stop-opacity=".45"/><stop offset="1" stop-color="#6b3f7a" stop-opacity="0"/></radialGradient>
<radialGradient id="tzMouth" cx="50%" cy="30%" r="70%"><stop offset="0" stop-color="#5a1420"/><stop offset="1" stop-color="#1a0508"/></radialGradient>
<filter id="tzGlow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="tzShadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="5" stdDeviation="4.5" flood-color="#000" flood-opacity=".55"/></filter>
<filter id="tzSoft"><feGaussianBlur stdDeviation="3"/></filter>
</defs>"""


def _leg(m):
    """m=False left leg, True right leg (mirrored about x=130)."""
    t = ' transform="translate(260 0) scale(-1 1)"' if m else ''
    tear = ('<path d="M100 226 Q108 220 116 228 L112 236 L117 244 Q108 250 100 244 L103 236 Z" fill="url(#tzSkinB)"/>'
            '<path d="M100 226 Q108 220 116 228 L112 236 L117 244 Q108 250 100 244 L103 236 Z" fill="none" stroke="#0e1320" stroke-width="1.8"/>'
            '<path d="M104 232 Q108 235 112 232" fill="none" stroke="#2c4a1b" stroke-width="1.1"/>') if m else ''
    return (f'<g class="tz-leg tz-leg{"R" if m else "L"}"><g{t}>'
            '<ellipse cx="106" cy="184" rx="25" ry="15" fill="url(#tzPants)"/><ellipse cx="101" cy="179" rx="12" ry="5" fill="#6d84aa" opacity=".35"/>'
            '<path d="M91 192 Q88 232 93 268 L119 268 Q124 232 124 192 Z" fill="url(#tzPants)" stroke="#8fa6d6" stroke-opacity=".55" stroke-width="2"/>'
            '<path d="M95 192 Q93 230 97 262" fill="none" stroke="#5b6e8f" stroke-width="2" opacity=".35"/>'
            + tear +
            '<path d="M91 266 L96 276 L100 267 L105 278 L110 267 L114 277 L119 266 Z" fill="#1a2132"/>'
            '<path d="M98 272 L114 272 L113 286 L99 286 Z" fill="url(#tzSkinB)"/>'
            '<path d="M88 288 Q86 301 103 303 Q123 305 126 294 Q124 284 113 284 L98 284 Q90 284 88 288 Z" fill="url(#tzShoe)"/>'
            '<path d="M92 290 Q100 286 112 287" fill="none" stroke="#8a6a52" stroke-width="1.6" opacity=".6"/>'
            '<path d="M88 296 Q104 304 125 296" fill="none" stroke="#0b0705" stroke-width="2"/>'
            '</g></g>')


def _arm(m):
    t = ' transform="translate(260 0) scale(-1 1)"' if m else ''
    return (f'<g{t}>'
            '<path d="M80 122 Q30 128 48 164" fill="none" stroke="#2c4a1b" stroke-width="20" stroke-linecap="round"/>'
            '<path d="M80 122 Q30 128 48 164" fill="none" stroke="url(#tzSkinB)" stroke-width="16" stroke-linecap="round"/>'
            '<path d="M58 126 Q44 136 46 150" fill="none" stroke="#d5f29b" stroke-width="2.4" stroke-linecap="round" opacity=".45"/>'
            '<path d="M88 114 Q60 116 50 134 L58 140 L62 132 L68 139 L71 130 L80 134 Q84 122 92 120 Z" fill="url(#tzShirt)"/>'
            '</g>')


def _hand(m):
    """Palm on top of the edge, four fingers curling over it toward the viewer."""
    t = ' transform="translate(260 0) scale(-1 1)"' if m else ''
    fingers = ''.join(
        f'<rect x="{x}" y="{EDGE_Y - 3}" width="7.2" height="{h}" rx="3.6" fill="url(#tzSkinB)" stroke="#2c4a1b" stroke-width="1"/>'
        f'<rect x="{x + 1.4}" y="{EDGE_Y - 3 + h - 5}" width="4.4" height="4" rx="1.6" fill="#d9dcb8" opacity=".85"/>'
        for x, h in ((42, 15), (49.5, 18), (57, 17), (64.5, 14)))
    return (f'<g class="tz-hand"><g{t}><g transform="translate(-8 0)">'
            f'<ellipse cx="56" cy="{EDGE_Y + 14}" rx="20" ry="5" fill="#000" opacity=".35" filter="url(#tzSoft)"/>'
            f'<ellipse cx="56" cy="{EDGE_Y - 6}" rx="17" ry="9.5" fill="url(#tzSkinB)" stroke="#2c4a1b" stroke-width="1.2"/>'
            f'<path d="M44 {EDGE_Y - 11} Q54 {EDGE_Y - 15} 66 {EDGE_Y - 11}" fill="none" stroke="#d5f29b" stroke-width="1.6" opacity=".5"/>'
            + fingers +
            f'<path d="M68 {EDGE_Y - 9} Q76 {EDGE_Y - 8} 74 {EDGE_Y - 1}" fill="none" stroke="#2c4a1b" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M68 {EDGE_Y - 9} Q76 {EDGE_Y - 8} 74 {EDGE_Y - 1}" fill="none" stroke="url(#tzSkinB)" stroke-width="3.4" stroke-linecap="round"/>'
            '</g></g></g>')


def _torso():
    return ('<g class="tz-torso">'
            '<path d="M86 174 Q80 142 70 120 Q98 100 130 100 Q162 100 190 120 Q180 142 174 174 Z" fill="url(#tzShirt)"/>'
            '<path d="M112 102 L130 128 L148 102 Q130 98 112 102 Z" fill="url(#tzSkinB)"/>'
            '<path d="M118 110 L130 124 L142 110" fill="none" stroke="#2c4a1b" stroke-width="1.4" opacity=".6"/>'
            '<path d="M100 140 Q108 134 116 141 L113 147 L118 152 Q110 160 102 156 L104 150 Z" fill="url(#tzSkinB)"/>'
            '<path d="M100 140 Q108 134 116 141 L113 147 L118 152 Q110 160 102 156 L104 150 Z" fill="none" stroke="#150f26" stroke-width="1.6"/>'
            '<path d="M104 146 Q109 148 113 145 M104 151 Q108 153 112 150" fill="none" stroke="#2c4a1b" stroke-width="1"/>'
            '<path d="M96 120 Q104 150 100 170 M164 112 Q160 146 166 168" fill="none" stroke="#7b68b0" stroke-width="2" opacity=".35"/>'
            '<path d="M86 172 L94 186 L101 174 L109 188 L117 175 L126 190 L134 175 L143 187 L151 174 L160 185 L167 173 L174 182 L174 172 Z" fill="#2a2147"/>'
            '<ellipse cx="130" cy="110" rx="46" ry="11" fill="url(#tzAO)" opacity=".85"/>'
            '</g>')


# per-state face parts: (eyelids/brows, pupils offset, mouth, extras)
def _face(vs):
    brows = {
        'idle': ('M96 40 Q108 34 122 42', 'M138 38 Q152 30 166 36'),
        'working': ('M96 42 Q108 40 122 46', 'M138 44 Q152 38 166 40'),
        'excited': ('M96 34 Q108 24 122 32', 'M138 30 Q152 22 166 30'),
        'alert': ('M96 30 Q108 20 122 30', 'M138 28 Q152 18 166 28'),
        'sleep': ('M98 48 Q110 50 122 50', 'M138 48 Q150 50 164 46'),
    }[vs]
    eye_r = {'idle': (11, 10), 'working': (10, 8.5), 'excited': (13, 12.5), 'alert': (13.5, 13), 'sleep': (11, 10)}[vs]
    pupil = {'idle': 3.6, 'working': 3.4, 'excited': 5.0, 'alert': 2.2, 'sleep': 3.4}[vs]
    mouth = {
        'idle': ('<path d="M106 86 Q126 98 152 82 Q148 92 128 96 Q112 96 106 86 Z" fill="url(#tzMouth)"/>'
                 '<path d="M130 89 L134 96 L138 88 Z M118 88 L121 94 L124 89 Z" fill="#e8e4c6"/>'),
        'working': ('<path d="M110 88 Q128 92 148 86" fill="none" stroke="#1a0508" stroke-width="3.2" stroke-linecap="round"/>'
                    '<path d="M136 88 L139 94 L142 87 Z" fill="#e8e4c6"/>'),
        'excited': ('<path d="M102 82 Q128 116 158 80 Q130 90 102 82 Z" fill="url(#tzMouth)"/>'
                    '<path d="M106 84 L112 92 L118 86 L124 94 L130 87 L136 94 L142 86 L148 92 L154 83 Q128 89 106 84 Z" fill="#ecead0"/>'
                    '<ellipse cx="130" cy="102" rx="10" ry="5" fill="#c2405a"/>'),
        'alert': ('<ellipse cx="129" cy="92" rx="9" ry="11" fill="url(#tzMouth)"/>'
                  '<path d="M123 83 L126 88 L129 83 Z" fill="#e8e4c6"/>'),
        'sleep': ('<path d="M114 90 Q128 98 144 90 Q130 94 114 90 Z" fill="url(#tzMouth)"/>'
                  '<path d="M140 93 Q142 102 140 106" fill="none" stroke="#bfe9ff" stroke-width="2.2" stroke-linecap="round" opacity=".75"/>'),
    }[vs]
    lid = {'sleep': 0.78}.get(vs, 0)
    eyes = ''
    for cx, cy in ((110, 58), (150, 55)):
        rx, ry = eye_r
        eyes += (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx + 6}" ry="{ry + 5}" fill="url(#tzAO)"/>'
                 f'<ellipse cx="{cx}" cy="{cy}" rx="{rx + 9}" ry="{ry + 8}" fill="url(#tzHalo)" class="tz-halo"/>'
                 f'<g class="tz-eye"><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#tzEye)" filter="url(#tzGlow)"/>'
                 f'<g class="tz-pupil"><ellipse cx="{cx + 1}" cy="{cy + 1}" rx="{pupil}" ry="{pupil * 1.25}" fill="#0f2205"/>'
                 f'<circle cx="{cx - 3}" cy="{cy - 3}" r="1.8" fill="#fff" opacity=".9"/></g></g>'
                 f'<clipPath id="tzC{cx}"><ellipse cx="{cx}" cy="{cy}" rx="{rx + .6}" ry="{ry + .6}"/></clipPath>'
                 f'<g clip-path="url(#tzC{cx})"><rect class="tz-lid" x="{cx - rx - 2}" y="{cy - ry - 1}" width="{2 * rx + 4}" height="{2 * ry + 2}" '
                 f'fill="url(#tzSkin)" style="transform-origin:{cx}px {cy - ry - 1}px;transform:scaleY({lid})"/>'
                 f'<path d="M{cx - rx} {cy - ry + 2 * ry * lid} Q{cx} {cy - ry + 2 * ry * lid + 3} {cx + rx} {cy - ry + 2 * ry * lid}" fill="none" stroke="#1d3311" stroke-width="{1.8 if lid else 0}"/></g>')
    bl, br = brows
    face = (eyes +
            f'<path d="{bl}" fill="none" stroke="#1e2a14" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="{br}" fill="none" stroke="#1e2a14" stroke-width="5" stroke-linecap="round"/>'
            '<path d="M98 70 Q110 76 122 70 M140 67 Q151 73 162 66" fill="none" stroke="#2c4a1b" stroke-width="1.6" opacity=".55"/>'
            '<ellipse cx="104" cy="84" rx="9" ry="6" fill="#23401a" opacity=".25"/><ellipse cx="158" cy="81" rx="8" ry="6" fill="#23401a" opacity=".25"/>'
            '<path d="M128 64 Q125 74 127 77 M134 64 Q137 74 135 77" fill="none" stroke="#2c4a1b" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>'
            '<ellipse cx="127" cy="77" rx="2.2" ry="1.4" fill="#1d3311"/><ellipse cx="136" cy="77" rx="2.2" ry="1.4" fill="#1d3311"/>'
            + mouth +
            '<path d="M152 82 l4 -3 M154 86 l5 -1" stroke="#3a2a2a" stroke-width="1.3"/>')
    extras = {
        'excited': ('<g class="tz-spark"><path d="M44 30 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3 Z" fill="#d6ff5c"/>'
                    '<path d="M214 22 l2.4 6 6 2.4 -6 2.4 -2.4 6 -2.4 -6 -6 -2.4 6 -2.4 Z" fill="#9dff3a"/>'
                    '<path d="M206 70 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 Z" fill="#fbffd0"/></g>'),
        'alert': ('<g class="tz-bang"><circle cx="196" cy="22" r="13" fill="#ffb020" filter="url(#tzGlow)"/>'
                  '<rect x="193.6" y="12" width="4.8" height="12" rx="2.2" fill="#1a1205"/><circle cx="196" cy="29" r="2.6" fill="#1a1205"/></g>'),
        'sleep': ('<g class="tz-z"><text x="178" y="34" font-family="system-ui" font-weight="800" font-size="20" fill="#bfe9ff">Z</text>'
                  '<text x="196" y="18" font-family="system-ui" font-weight="800" font-size="13" fill="#bfe9ff" opacity=".8">z</text></g>'),
        'working': ('<g class="tz-think"><circle cx="190" cy="40" r="3" fill="#9dff3a" opacity=".8"/><circle cx="200" cy="30" r="4" fill="#9dff3a" opacity=".6"/>'
                    '<circle cx="212" cy="18" r="5.5" fill="#9dff3a" opacity=".4"/></g>'),
    }.get(vs, '')
    return face, extras


def _head(vs):
    face, extras = _face(vs)
    return ('<g class="tz-head"><g transform="translate(130 70) scale(1.1) translate(-130 -58)">'
            '<ellipse cx="130" cy="108" rx="40" ry="9" fill="#000" opacity=".45" filter="url(#tzSoft)"/>'
            '<path d="M116 96 L118 112 L142 112 L144 96 Z" fill="url(#tzSkinB)"/>'
            # torn left ear, whole right ear
            '<path d="M88 56 Q74 52 76 66 Q78 76 90 76 L88 70 L82 68 L86 63 Z" fill="url(#tzSkinB)" stroke="#2c4a1b" stroke-width="1.2"/>'
            '<path d="M172 54 Q186 50 186 64 Q185 76 172 76 Z" fill="url(#tzSkinB)" stroke="#2c4a1b" stroke-width="1.2"/>'
            '<path d="M176 60 Q181 64 176 70" fill="none" stroke="#2c4a1b" stroke-width="1.4"/>'
            # skull: slightly lopsided, wider brow, narrow chin
            '<path d="M86 62 Q82 16 130 12 Q178 12 178 58 Q180 88 160 102 Q132 118 102 102 Q86 90 86 62 Z" fill="url(#tzSkin)" stroke="#23401a" stroke-width="1.6" filter="url(#tzShadow)"/>'
            '<path d="M92 50 Q94 22 126 16" fill="none" stroke="#e2f8b0" stroke-width="3" stroke-linecap="round" opacity=".45"/>'
            '<path d="M174 50 Q176 80 158 98" fill="none" stroke="#b6ff6a" stroke-width="2" stroke-linecap="round" opacity=".35"/>'
            '<ellipse cx="102" cy="80" rx="12" ry="8" fill="url(#tzBruise)"/><ellipse cx="164" cy="76" rx="9" ry="7" fill="url(#tzBruise)"/>'
            # stitched scar across the forehead
            '<path d="M136 20 Q154 26 162 42" fill="none" stroke="#3a2a2a" stroke-width="2"/>'
            '<path d="M139 18 l-2 6 M146 21 l-3 6 M153 25 l-4 5 M158 31 l-5 4 M161 37 l-5 3" stroke="#3a2a2a" stroke-width="1.4"/>'
            # hair tufts
            '<path d="M98 26 L92 10 L106 20 L108 4 L118 17 L124 2 L130 16 L140 6 L140 18 L152 10 L148 24 Q126 14 98 26 Z" fill="#1e2a14"/>'
            '<path d="M108 6 L112 16 M124 4 L126 14" stroke="#3d5428" stroke-width="1.4"/>'
            + face + '</g></g>' + extras)


def svg_zombie(vs='idle'):
    vs = vs if vs in VSTATES else 'idle'
    return (f'<svg class="tz-zombie tz-{vs}" viewBox="0 0 {VB_W} {VB_H}" role="img" aria-label="TOKEN ZOMBIE mascot: {vs}">'
            + DEFS +
            f'<ellipse cx="130" cy="{EDGE_Y + 8}" rx="100" ry="10" fill="#000" opacity=".5" filter="url(#tzSoft)"/>'
            f'<path d="M8 {EDGE_Y} H252" stroke="#9dff3a" stroke-opacity=".22" stroke-width="1.2"/>'
            + _leg(False) + _leg(True) + _torso() + _arm(False) + _arm(True) + _head(vs) + _hand(False) + _hand(True)
            + '</svg>')


CSS = """
.tz-zombie{width:100%;height:100%;overflow:visible;display:block}
.tz-zombie *{transform-box:view-box}
.tz-torso,.tz-head{transform-origin:130px 172px}
.tz-legL{transform-origin:108px 178px}.tz-legR{transform-origin:152px 178px}
@keyframes tzBreath{0%,100%{transform:scale(1,1)}50%{transform:scale(1.012,1.03)}}
@keyframes tzHeadBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-1.6px)}}
@keyframes tzBlink{0%,92%,100%{transform:scaleY(0)}95%{transform:scaleY(1)}}
@keyframes tzSwingL{0%,100%{transform:rotate(0)}50%{transform:rotate(7deg)}}
@keyframes tzSwingR{0%,100%{transform:rotate(0)}50%{transform:rotate(-6deg)}}
@keyframes tzLook{0%,100%{transform:rotate(0) translateX(0)}20%{transform:rotate(-7deg) translateX(-4px)}45%{transform:rotate(-6deg) translateX(-4px)}65%{transform:rotate(6deg) translateX(4px)}85%{transform:rotate(5deg) translateX(4px)}}
@keyframes tzPupil{0%,100%{transform:translateX(0)}20%,45%{transform:translateX(-3.5px)}65%,85%{transform:translateX(3.5px)}}
@keyframes tzBounce{0%,100%{transform:translateY(0) scale(1)}30%{transform:translateY(-9px) scale(1.02,.98)}55%{transform:translateY(0) scale(1.03,.96)}}
@keyframes tzKick{0%,100%{transform:rotate(0)}30%{transform:rotate(-22deg)}60%{transform:rotate(10deg)}}
@keyframes tzKickR{0%,100%{transform:rotate(0)}30%{transform:rotate(22deg)}60%{transform:rotate(-10deg)}}
@keyframes tzSpark{0%,100%{opacity:0;transform:scale(.6)}50%{opacity:1;transform:scale(1.15)}}
@keyframes tzShake{0%,100%{transform:translateX(0)}20%{transform:translateX(-2px) rotate(-1.5deg)}40%{transform:translateX(2px) rotate(1.5deg)}60%{transform:translateX(-1.5px)}80%{transform:translateX(1.5px)}}
@keyframes tzPulse{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes tzNod{0%,100%{transform:rotate(6deg) translateY(4px)}50%{transform:rotate(9deg) translateY(7px)}}
@keyframes tzZ{0%{opacity:0;transform:translate(0,6px)}30%{opacity:1}100%{opacity:0;transform:translate(10px,-14px)}}
@keyframes tzThink{0%,100%{opacity:.3}50%{opacity:1}}
.tz-idle .tz-torso{animation:tzBreath 4.2s ease-in-out infinite}
.tz-idle .tz-head{animation:tzHeadBob 4.2s ease-in-out infinite}
.tz-idle .tz-lid,.tz-working .tz-lid,.tz-excited .tz-lid{animation:tzBlink 5.5s infinite}
.tz-idle .tz-legL{animation:tzSwingL 6s ease-in-out infinite}.tz-idle .tz-legR{animation:tzSwingR 6s ease-in-out infinite 1.2s}
.tz-working .tz-torso{animation:tzBreath 3s ease-in-out infinite}
.tz-working .tz-head{animation:tzLook 4.8s ease-in-out infinite}
.tz-working .tz-pupil{animation:tzPupil 4.8s ease-in-out infinite}
.tz-working .tz-think{animation:tzThink 1.6s ease-in-out infinite}
.tz-working .tz-legL{animation:tzSwingL 2.4s ease-in-out infinite}.tz-working .tz-legR{animation:tzSwingR 2.4s ease-in-out infinite .6s}
.tz-excited .tz-torso,.tz-excited .tz-head{animation:tzBounce .9s ease-in-out infinite}
.tz-excited .tz-legL{animation:tzKick .9s ease-in-out infinite}.tz-excited .tz-legR{animation:tzKickR .9s ease-in-out infinite .15s}
.tz-excited .tz-spark{animation:tzSpark 1.2s ease-in-out infinite;transform-origin:130px 60px}
.tz-excited .tz-halo{animation:tzPulse .9s ease-in-out infinite}
.tz-alert .tz-head{animation:tzShake .5s ease-in-out infinite}
.tz-alert .tz-bang{animation:tzPulse .7s ease-in-out infinite}
.tz-alert .tz-halo{animation:tzPulse .5s ease-in-out infinite}
.tz-sleep .tz-head{animation:tzNod 5s ease-in-out infinite}
.tz-sleep .tz-torso{animation:tzBreath 6s ease-in-out infinite}
.tz-sleep .tz-halo{opacity:.25}
.tz-sleep .tz-z text{animation:tzZ 3.2s ease-in-out infinite}.tz-sleep .tz-z text+text{animation-delay:1.6s}
@media (prefers-reduced-motion:reduce){.tz-zombie *{animation:none!important}}
"""


def visual_state(bus, mascot_state, agents_running=0, saved_recent=False, now=None):
    """Map the status bus + measured extras to a visual state. ALERT wins, then excited, working, sleep, idle."""
    now = now or time.time()
    if mascot_state == 'ALERT':
        return 'alert'
    if mascot_state == 'CELEBRATE' or saved_recent:
        return 'excited'
    if mascot_state == 'CHOMP' or agents_running:
        return 'working'
    ts = bus.get('ts') if isinstance(bus, dict) else None
    if mascot_state == 'SLEEP' or not isinstance(ts, (int, float)) or now - ts > 1800:
        return 'sleep'
    return 'idle'


# Mod band crop: transparent room above the head so the grip line (EDGE_Y) lands BAND_EDGE px below the
# image top at BAND_W px wide. The band places the image 2 cells above the bar's border (~19 px/cell).
BAND_W, BAND_EDGE = 42, 38
_k = BAND_W / VB_W
BAND_TOP = round(EDGE_Y - BAND_EDGE / _k)
BAND_VB = f'0 0 {VB_W} {VB_H - BAND_TOP}'  # content shifted down, not a negative viewBox: keeps CSS transform-origins right
BAND_H = round((VB_H - BAND_TOP) * _k)


def svg_file(vs='idle'):
    """Standalone SVG (xmlns + its own <style>) for surfaces that draw it as an image, e.g. the Mod's band."""
    s = svg_zombie(vs).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    s = s.replace(f'viewBox="0 0 {VB_W} {VB_H}"', f'viewBox="{BAND_VB}" width="{BAND_W}" height="{BAND_H}"', 1)
    i = s.index('</defs>') + len('</defs>')
    s = s[:i] + f'<g transform="translate(0 {-BAND_TOP})">' + s[i:].replace('</svg>', '</g></svg>')
    return s.replace(DEFS, DEFS + '<style>' + CSS.replace('\n', '') + '</style>', 1)


if __name__ == '__main__':  # python3 bin/tzzombie.py assets/  -> writes zombie-<state>.svg for the Mod
    import os, sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'assets'
    os.makedirs(out, exist_ok=True)
    for v in VSTATES:
        open(os.path.join(out, f'zombie-{v}.svg'), 'w').write(svg_file(v))
