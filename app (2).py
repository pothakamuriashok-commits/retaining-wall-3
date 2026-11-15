import math
import html
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='Retaining Wall Design Calculator', page_icon='🏗️', layout='wide')

# ============================================================
# GENERAL RETAINING WALL DESIGN CALCULATOR
# Streamlit-only version: no numpy, pandas or matplotlib.
# Based on the supplied Example 14.9 methodology.
# Units: kN, m, MPa, mm
# ============================================================


def rankine_coeff(phi_deg):
    s = math.sin(math.radians(phi_deg))
    ka = (1.0 - s) / (1.0 + s)
    return ka, 1.0 / ka


def calc_rebar(Mu_kNm, d_mm, fck, fy, bar_dia, min_pct=0.12):
    b = 1000.0
    d = max(1.0, d_mm)
    M = max(0.0, Mu_kNm) * 1e6
    xu_max = 0.48 * d
    Mu_lim = 0.36 * fck * b * xu_max * (d - 0.42 * xu_max) / 1e6

    def mu_from_ast(ast):
        xu = 0.87 * fy * ast / (0.36 * fck * b)
        return 0.87 * fy * ast * (d - 0.42 * xu) / 1e6

    if Mu_kNm <= Mu_lim:
        lo, hi = 0.0, 20000.0
        for _ in range(80):
            mid = (lo + hi) / 2.0
            if mu_from_ast(mid) < M:
                lo = mid
            else:
                hi = mid
        ast = hi
    else:
        ast = 0.87 * fy * b * d / fy

    ast_min = min_pct / 100.0 * b * d
    ast_req = max(ast, ast_min)
    area_bar = math.pi * bar_dia**2 / 4.0
    raw_spacing = area_bar * 1000.0 / ast_req
    spacing = max(75.0, min(300.0, math.floor(raw_spacing / 5.0) * 5.0))
    ast_prov = area_bar * 1000.0 / spacing
    return ast_req, ast_prov, spacing, Mu_lim


def lineload_end_actions(length, w_free, w_fixed):
    # Signed linearly varying load; positive = upward for slab diagrams.
    if length <= 0:
        return 0.0, 0.0
    V = (w_free + w_fixed) * length / 2.0
    M = length**2 * (w_free / 2.0 + (w_fixed - w_free) / 6.0)
    return V, M


def svg_polyline(points, width, height, pad=55, stroke='black', fill='none', sw=2):
    if not points:
        return ''
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    dx = max(xmax - xmin, 1e-9)
    dy = max(ymax - ymin, 1e-9)
    coords = []
    for x, y in points:
        sx = pad + (x - xmin) / dx * (width - 2 * pad)
        sy = height - pad - (y - ymin) / dy * (height - 2 * pad)
        coords.append(f'{sx:.2f},{sy:.2f}')
    return f'<polyline points="{" ".join(coords)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def svg_chart(title, x_label, y_label, curves, width=900, height=430, zero=True):
    # curves = [(points, label)]
    all_points = [p for pts, _ in curves for p in pts]
    if not all_points:
        return ''
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if zero:
        ymin = min(ymin, 0.0)
        ymax = max(ymax, 0.0)
    dx = max(xmax - xmin, 1e-9)
    dy = max(ymax - ymin, 1e-9)
    pad = 58

    def sx(x): return pad + (x - xmin) / dx * (width - 2 * pad)
    def sy(y): return height - pad - (y - ymin) / dy * (height - 2 * pad)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {width} {height}" style="background:white;border:1px solid #ddd;border-radius:8px">']
    parts.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="18" font-family="Arial" font-weight="bold">{html.escape(title)}</text>')
    # grid
    for i in range(6):
        yv = ymin + i * dy / 5
        yy = sy(yv)
        parts.append(f'<line x1="{pad}" y1="{yy:.1f}" x2="{width-pad}" y2="{yy:.1f}" stroke="#e5e5e5"/>')
        parts.append(f'<text x="{pad-8}" y="{yy+4:.1f}" text-anchor="end" font-size="11" font-family="Arial">{yv:.2f}</text>')
    for i in range(6):
        xv = xmin + i * dx / 5
        xx = sx(xv)
        parts.append(f'<line x1="{xx:.1f}" y1="{pad}" x2="{xx:.1f}" y2="{height-pad}" stroke="#e5e5e5"/>')
        parts.append(f'<text x="{xx:.1f}" y="{height-pad+18}" text-anchor="middle" font-size="11" font-family="Arial">{xv:.2f}</text>')
    if ymin <= 0 <= ymax:
        yy = sy(0)
        parts.append(f'<line x1="{pad}" y1="{yy:.1f}" x2="{width-pad}" y2="{yy:.1f}" stroke="#777" stroke-width="1.2"/>')
    parts.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#333"/>')
    parts.append(f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#333"/>')
    # color palette is deliberately simple and browser-native
    colors = ['#1565c0', '#c62828', '#2e7d32', '#6a1b9a']
    for j, (pts, label) in enumerate(curves):
        color = colors[j % len(colors)]
        path = ' '.join(f'{sx(x):.1f},{sy(y):.1f}' for x, y in pts)
        parts.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        lx, ly = pts[-1]
        parts.append(f'<text x="{min(width-pad-5, sx(lx)+8):.1f}" y="{max(pad+12, sy(ly)-5):.1f}" font-size="12" font-family="Arial" fill="{color}">{html.escape(label)}</text>')
    parts.append(f'<text x="{width/2}" y="{height-10}" text-anchor="middle" font-size="12" font-family="Arial">{html.escape(x_label)}</text>')
    parts.append(f'<text x="16" y="{height/2}" text-anchor="middle" font-size="12" font-family="Arial" transform="rotate(-90 16 {height/2})">{html.escape(y_label)}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def pressure_svg(qmax, qmin, L, toe, stem_base):
    pts = [(0, qmax), (L, qmin)]
    svg = svg_chart('Base Soil Pressure Distribution', 'Distance from toe (m)', 'Pressure (kN/m²)', [(pts, 'q')], 900, 430)
    # add stem markers approximately by overlaying not necessary; chart itself is sufficient
    return svg


def wall_detail_svg(base_L, toe, stem_base, stem_top, base_thk, stem_h,
                     stem_d, stem_s, toe_d, toe_s, heel_d, heel_s):
    W, H = 1000, 650
    scale = 180
    x0 = 80
    y0 = 500
    base_px = base_L * scale
    toe_px = toe * scale
    stemb_px = stem_base * scale
    stemt_px = stem_top * scale
    h_px = stem_h * 75
    base_px = min(base_px, 820)
    scale_x = base_px / base_L
    toe_px = toe * scale_x
    stemb_px = stem_base * scale_x
    stemt_px = stem_top * scale_x
    h_px = min(stem_h * 72, 330)
    bt_px = max(28, base_thk * 45)
    x_toe = x0 + toe_px
    x_back = x_toe + stemb_px
    top_back = x_toe + stemt_px
    y_base = y0
    y_top = y_base - h_px
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" style="background:white;border:1px solid #ddd;border-radius:8px">']
    parts.append('<defs><pattern id="soil" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#999" stroke-width="1"/></pattern></defs>')
    # base
    parts.append(f'<rect x="{x0}" y="{y_base}" width="{base_px}" height="{bt_px}" fill="#d8d8d8" stroke="#222" stroke-width="2"/>')
    # stem
    stem_points = f'{x_toe},{y_base} {x_back},{y_base} {top_back},{y_top} {x_toe},{y_top}'
    parts.append(f'<polygon points="{stem_points}" fill="#e7e7e7" stroke="#222" stroke-width="2"/>')
    # backfill
    parts.append(f'<polygon points="{x_back},{y_top} {x0+base_px},{y_top} {x0+base_px},{y_top-90} {top_back},{y_top-90}" fill="url(#soil)" stroke="#888"/>')
    # main vertical bars
    for i in range(9):
        yy = y_base - 25 - i*(h_px-45)/8
        # front face follows vertical line
        parts.append(f'<circle cx="{x_toe+14}" cy="{yy:.1f}" r="4" fill="#111"/>')
    # horizontal bars
    for i in range(9):
        yy = y_base - 35 - i*(h_px-55)/8
        t = (y_base-yy)/h_px
        width = stemb_px*(1-t) + stemt_px*t
        parts.append(f'<line x1="{x_toe+10}" y1="{yy:.1f}" x2="{x_toe+width-8:.1f}" y2="{yy:.1f}" stroke="#333" stroke-width="1.5"/>')
    # toe and heel bars
    for i in range(12):
        xx = x0 + 12 + i*max(1,(toe_px-24)/11)
        parts.append(f'<circle cx="{xx:.1f}" cy="{y_base+bt_px-10}" r="3.5" fill="#111"/>')
    heel_start = x_back + 10
    heel_len = x0+base_px-heel_start-10
    for i in range(12):
        xx = heel_start + i*max(1,heel_len/11)
        parts.append(f'<circle cx="{xx:.1f}" cy="{y_base+10}" r="3.5" fill="#111"/>')
    # dimensions/labels
    parts.append(f'<text x="{W/2}" y="40" text-anchor="middle" font-size="20" font-family="Arial" font-weight="bold">Retaining Wall Reinforcement Detailing – Schematic</text>')
    labels = [
        (x0+20, y_base+bt_px+42, f'{toe_d}ϕ @ {toe_s:.0f} c/c BOTTOM TOE'),
        (x_back+20, y_base+bt_px+42, f'{heel_d}ϕ @ {heel_s:.0f} c/c TOP HEEL'),
        (x_toe+35, y_base-h_px*0.52, f'{stem_d}ϕ @ {stem_s:.0f} c/c MAIN VERTICAL'),
        (x_toe+40, y_base-h_px*0.18, '8ϕ horizontal – lower 1/3'),
        (x_toe+40, y_base-h_px*0.48, '8ϕ horizontal – middle 1/3'),
        (x_toe+40, y_base-h_px*0.80, '8ϕ horizontal – upper 1/3'),
    ]
    for x,y,t in labels:
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="13" font-family="Arial">{html.escape(t)}</text>')
    parts.append(f'<text x="{x0+base_px/2:.1f}" y="{y_base+bt_px+85}" text-anchor="middle" font-size="12" font-family="Arial">Base width = {base_L:.2f} m | Toe = {toe:.2f} m | Heel = {base_L-toe-stem_base:.2f} m</text>')
    parts.append('</svg>')
    return ''.join(parts)


def svg_bytes(svg):
    return svg.encode('utf-8')

# -----------------------------
# Inputs
# -----------------------------
st.sidebar.header('🏗️ Retaining Wall Inputs')
st.sidebar.caption('General cantilever retaining-wall calculator. Defaults follow the supplied Example 14.9.')

st.sidebar.subheader('Soil / loading')
h = st.sidebar.number_input('Retained height above front ground level (m)', 1.0, 20.0, 4.0, 0.01)
foundation_depth = st.sidebar.number_input('Foundation depth below front ground level (m)', 0.0, 5.0, 1.25, 0.01)
gamma = st.sidebar.number_input('Soil unit weight γ (kN/m³)', 10.0, 25.0, 16.0, 0.1)
phi = st.sidebar.number_input('Soil friction angle φ (°)', 5.0, 50.0, 30.0, 0.1)
surcharge = st.sidebar.number_input('Uniform surcharge q (kN/m²)', 0.0, 300.0, 40.0, 1.0)
qa = st.sidebar.number_input('Allowable bearing pressure qa (kN/m²)', 20.0, 500.0, 150.0, 1.0)
mu = st.sidebar.number_input('Base friction coefficient μ', 0.05, 1.0, 0.50, 0.01)

st.sidebar.subheader('Materials')
gamma_c = st.sidebar.number_input('Concrete unit weight (kN/m³)', 20.0, 30.0, 25.0, 0.1)
fck = st.sidebar.number_input('Concrete grade fck (MPa)', 15.0, 60.0, 20.0, 1.0)
fy = st.sidebar.number_input('Steel grade fy (MPa)', 250.0, 600.0, 415.0, 5.0)
cover_stem = st.sidebar.number_input('Stem clear cover (mm)', 25.0, 100.0, 50.0, 1.0)
cover_slab = st.sidebar.number_input('Base slab clear cover (mm)', 40.0, 120.0, 75.0, 1.0)

st.sidebar.subheader('Geometry')
base_L = st.sidebar.number_input('Base width L (m)', 1.5, 10.0, 3.90, 0.01)
toe = st.sidebar.number_input('Toe projection (m)', 0.20, 4.0, 1.30, 0.01)
stem_base = st.sidebar.number_input('Stem thickness at base (m)', 0.20, 1.50, 0.650, 0.01)
stem_top = st.sidebar.number_input('Stem thickness at top (m)', 0.10, 0.80, 0.200, 0.01)
base_thk = st.sidebar.number_input('Base slab thickness (m)', 0.25, 1.50, 0.620, 0.01)
key_b = st.sidebar.number_input('Shear key width (m)', 0.0, 0.80, 0.300, 0.01)
key_d = st.sidebar.number_input('Shear key depth (m)', 0.0, 0.80, 0.400, 0.01)
key_from_toe = st.sidebar.number_input('Shear key position from toe (m)', 0.0, 4.0, 1.60, 0.01)

st.sidebar.subheader('Design settings')
load_factor = st.sidebar.number_input('Ultimate load factor', 1.0, 2.0, 1.50, 0.05)
fs_req = st.sidebar.number_input('Required factor of safety', 1.0, 2.0, 1.40, 0.05)
stem_main_dia = st.sidebar.selectbox('Stem main bar diameter (mm)', [12,16,20,25], index=1)
toe_dia = st.sidebar.selectbox('Toe main bar diameter (mm)', [12,16,20,25], index=1)
heel_dia = st.sidebar.selectbox('Heel main bar diameter (mm)', [12,16,20,25], index=1)

# -----------------------------
# Geometry and calculations
# -----------------------------
stem_h = h + foundation_depth - base_thk
heel = base_L - toe - stem_base

if stem_h <= 0:
    st.error('Invalid geometry: stem height is not positive.')
    st.stop()
if heel <= 0:
    st.error('Invalid geometry: heel projection is not positive. Increase base width or reduce toe/stem thickness.')
    st.stop()
if toe <= 0 or toe >= base_L:
    st.error('Invalid geometry: toe must be positive and smaller than base width.')
    st.stop()

ka, kp = rankine_coeff(phi)
pa_soil = ka * gamma * h*h / 2.0
pa_surcharge = ka * surcharge * h
pa = pa_soil + pa_surcharge
Mo = pa_soil*h/3.0 + pa_surcharge*h/2.0

soil_heel = gamma * heel * h
base_weight = gamma_c * base_L * base_thk
stem_weight = gamma_c * stem_h * (stem_base + stem_top)/2.0
surcharge_vertical = surcharge * heel
W = soil_heel + base_weight + stem_weight + surcharge_vertical

x_soil = toe + stem_base + heel/2.0
x_base = base_L/2.0
x_stem = toe + (stem_base + stem_top)/2.0
x_surcharge = x_soil
Mr_toe = soil_heel*x_soil + base_weight*x_base + stem_weight*x_stem + surcharge_vertical*x_surcharge
FS_overturning = 0.9*Mr_toe/Mo if Mo > 0 else float('inf')

R = W
xR = (Mr_toe - Mo)/R if R else 0.0
e = xR - base_L/2.0
qavg = R/base_L
qmax = qavg*(1.0 + 6.0*e/base_L)
qmin = qavg*(1.0 - 6.0*e/base_L)

friction = mu*R
FS_slide_no_key = 0.9*friction/pa if pa else float('inf')
h1 = max(0.0, foundation_depth - 0.30)
h2 = h1 + key_d + max(0.0, key_from_toe-toe)*math.tan(math.radians(phi))
Pp = kp*gamma*max(0.0, h2*h2-h1*h1)/2.0 if key_d > 0 else 0.0
FS_slide_key = 0.9*(friction+Pp)/pa if pa else float('inf')

# Pressure values at stem faces
q_stem_front = qmax + (qmin-qmax)*(toe/base_L)
q_stem_back = qmax + (qmin-qmax)*((toe+stem_base)/base_L)
q_heel = qmin
q_toe = qmax

# Signed service-level net line loads
wt_base = gamma_c*base_thk
w_toe_free = q_toe - wt_base
w_toe_fixed = q_stem_front - wt_base
w_heel_free = q_heel - wt_base - gamma*h - surcharge
w_heel_fixed = q_stem_back - wt_base - gamma*h - surcharge

V_toe, M_toe_service = lineload_end_actions(toe, w_toe_free, w_toe_fixed)
V_heel, M_heel_service = lineload_end_actions(heel, w_heel_free, w_heel_fixed)
Vu_toe = abs(V_toe)*load_factor
Mu_toe = abs(M_toe_service)*load_factor
Vu_heel = abs(V_heel)*load_factor
Mu_heel = abs(M_heel_service)*load_factor

d_toe = base_thk*1000.0-cover_slab-toe_dia/2.0
d_heel = base_thk*1000.0-cover_slab-heel_dia/2.0

# Stem cantilever
V_stem_service = pa
M_stem_service = Mo
Vu_stem = pa*load_factor
Mu_stem = Mo*load_factor
d_stem = stem_base*1000.0-cover_stem-stem_main_dia/2.0

Ast_toe, Ast_toe_prov, s_toe, _ = calc_rebar(Mu_toe, d_toe, fck, fy, toe_dia)
Ast_heel, Ast_heel_prov, s_heel, _ = calc_rebar(Mu_heel, d_heel, fck, fy, heel_dia)
Ast_stem, Ast_stem_prov, s_stem, _ = calc_rebar(Mu_stem, d_stem, fck, fy, stem_main_dia)
v_toe = Vu_toe*1000.0/(1000.0*max(d_toe,1.0))
v_heel = Vu_heel*1000.0/(1000.0*max(d_heel,1.0))
v_stem = Vu_stem*1000.0/(1000.0*max(d_stem,1.0))

# -----------------------------
# Header
# -----------------------------
st.title('🏗️ Retaining Wall Design Calculator')
st.caption('General cantilever retaining-wall calculator using the terminology and workflow of the supplied Example 14.9.')

warns = []
if qmin < 0: warns.append('qmin is negative: the base resultant is outside the middle-third/full-contact assumption.')
if qmax > qa: warns.append('qmax exceeds the entered allowable bearing pressure.')
if FS_overturning < fs_req: warns.append('Overturning factor of safety is below the required value.')
if FS_slide_key < fs_req: warns.append('Sliding factor of safety with shear key is below the required value.')
for w in warns:
    st.warning(w)

# Tabs
t1,t2,t3,t4,t5,t6 = st.tabs(['📊 Summary','🧮 Calculations','📐 SFD / BMD','🔩 Reinforcement','📋 BBS','⬇️ Export'])

with t1:
    st.subheader('Design summary')
    c = st.columns(4)
    c[0].metric('Ka', f'{ka:.3f}')
    c[1].metric('Active force Pa', f'{pa:.1f} kN/m')
    c[2].metric('Overturning FS', f'{FS_overturning:.2f}')
    c[3].metric('Sliding FS + key', f'{FS_slide_key:.2f}')
    c = st.columns(4)
    c[0].metric('qmax', f'{qmax:.1f} kN/m²')
    c[1].metric('qmin', f'{qmin:.1f} kN/m²')
    c[2].metric('Stem Mu', f'{Mu_stem:.1f} kN·m/m')
    c[3].metric('Stem Ast provided', f'{Ast_stem_prov:.0f} mm²/m')

    checks = [
        {'Check':'Overturning','Value':round(FS_overturning,3),'Criterion':f'>= {fs_req:.2f}','OK':FS_overturning>=fs_req},
        {'Check':'Sliding without key','Value':round(FS_slide_no_key,3),'Criterion':f'>= {fs_req:.2f}','OK':FS_slide_no_key>=fs_req},
        {'Check':'Sliding with key','Value':round(FS_slide_key,3),'Criterion':f'>= {fs_req:.2f}','OK':FS_slide_key>=fs_req},
        {'Check':'Maximum bearing','Value':round(qmax,3),'Criterion':f'<= {qa:.1f}','OK':qmax<=qa},
        {'Check':'Minimum bearing','Value':round(qmin,3),'Criterion':'>= 0','OK':qmin>=0},
        {'Check':'Resultant in base','Value':round(xR,3),'Criterion':f'0 to {base_L:.2f} m from toe','OK':0<=xR<=base_L},
    ]
    st.dataframe(checks, use_container_width=True, hide_index=True)
    if all(x['OK'] for x in checks): st.success('All displayed stability checks satisfy the entered criteria.')
    else: st.error('One or more displayed checks do not satisfy the entered criteria.')

with t2:
    st.subheader('Earth pressure')
    st.table([
        ['Active coefficient Ka',f'{ka:.4f}','-'],
        ['Passive coefficient Kp',f'{kp:.4f}','-'],
        ['Equivalent surcharge height',f'{surcharge/gamma:.3f}','m'],
        ['Soil active force Pa1',f'{pa_soil:.2f}','kN/m'],
        ['Surcharge active force Pa2',f'{pa_surcharge:.2f}','kN/m'],
        ['Total active force Pa',f'{pa:.2f}','kN/m'],
        ['Overturning moment Mo',f'{Mo:.2f}','kN·m/m'],
    ])
    st.subheader('Vertical loads')
    st.table([
        ['Soil over heel',f'{soil_heel:.2f}',f'{x_soil:.3f}',f'{soil_heel*x_soil:.2f}'],
        ['Base slab',f'{base_weight:.2f}',f'{x_base:.3f}',f'{base_weight*x_base:.2f}'],
        ['Stem concrete',f'{stem_weight:.2f}',f'{x_stem:.3f}',f'{stem_weight*x_stem:.2f}'],
        ['Surcharge over heel',f'{surcharge_vertical:.2f}',f'{x_surcharge:.3f}',f'{surcharge_vertical*x_surcharge:.2f}'],
        ['TOTAL',f'{W:.2f}','-',f'{Mr_toe:.2f}'],
    ])
    st.write(f'**Stabilising moment:** {Mr_toe:.2f} kN·m/m')
    st.write(f'**Overturning FS:** {FS_overturning:.2f}')
    st.write(f'**Sliding resistance without key:** {friction:.2f} kN/m')
    st.write(f'**Passive resistance from key:** {Pp:.2f} kN/m')
    st.write(f'**Sliding FS with key:** {FS_slide_key:.2f}')

    st.subheader('Base pressure')
    st.write(f'Resultant from toe xR = **{xR:.3f} m**; eccentricity e = **{e:.3f} m**.')
    st.table([
        ['Average pressure',f'{qavg:.2f}','kN/m²'],
        ['Maximum pressure qmax',f'{qmax:.2f}','kN/m²'],
        ['Minimum pressure qmin',f'{qmin:.2f}','kN/m²'],
    ])

    st.subheader('RC design')
    st.table([
        ['Toe',f'{Vu_toe:.2f}',f'{Mu_toe:.2f}',f'{d_toe:.0f}',f'{Ast_toe:.0f}',toe_dia,f'{s_toe:.0f}',f'{v_toe:.3f}'],
        ['Heel',f'{Vu_heel:.2f}',f'{Mu_heel:.2f}',f'{d_heel:.0f}',f'{Ast_heel:.0f}',heel_dia,f'{s_heel:.0f}',f'{v_heel:.3f}'],
        ['Stem',f'{Vu_stem:.2f}',f'{Mu_stem:.2f}',f'{d_stem:.0f}',f'{Ast_stem:.0f}',stem_main_dia,f'{s_stem:.0f}',f'{v_stem:.3f}'],
    ])
    st.caption('Columns: Member | Vu kN/m | Mu kN·m/m | effective depth d mm | Ast required mm²/m | bar mm | spacing mm | nominal shear stress MPa')

with t3:
    st.subheader('SFD / BMD diagrams')
    n=60
    toe_pts_v=[]; toe_pts_m=[]; heel_pts_v=[]; heel_pts_m=[]
    for i in range(n+1):
        x=toe*i/n
        w=w_toe_free+(w_toe_fixed-w_toe_free)*(x/toe if toe else 0)
        # analytical integral from free end to x
        k=(w_toe_fixed-w_toe_free)/toe if toe else 0
        V=w_toe_free*x+0.5*k*x*x
        M=w_toe_free*x*x/2+k*x*x*x/6
        toe_pts_v.append((x,V)); toe_pts_m.append((x,M))
        x=heel*i/n
        k=(w_heel_fixed-w_heel_free)/heel if heel else 0
        V=w_heel_free*x+0.5*k*x*x
        M=w_heel_free*x*x/2+k*x*x*x/6
        heel_pts_v.append((x,V)); heel_pts_m.append((x,M))
    st.markdown(svg_chart('Toe Slab – SFD','Distance from free edge toward stem (m)','Shear V (kN/m)',[(toe_pts_v,'V')],900,420), unsafe_allow_html=True)
    st.markdown(svg_chart('Toe Slab – BMD','Distance from free edge toward stem (m)','Moment M (kN·m/m)',[(toe_pts_m,'M')],900,420), unsafe_allow_html=True)
    st.write(f'Toe ultimate design: **Vu = {Vu_toe:.2f} kN/m**, **Mu = {Mu_toe:.2f} kN·m/m**.')
    st.markdown(svg_chart('Heel Slab – SFD','Distance from free edge toward stem (m)','Shear V (kN/m)',[(heel_pts_v,'V')],900,420), unsafe_allow_html=True)
    st.markdown(svg_chart('Heel Slab – BMD','Distance from free edge toward stem (m)','Moment M (kN·m/m)',[(heel_pts_m,'M')],900,420), unsafe_allow_html=True)
    st.write(f'Heel ultimate design: **Vu = {Vu_heel:.2f} kN/m**, **Mu = {Mu_heel:.2f} kN·m/m**.')

    stem_p=[]; stem_v=[]; stem_m=[]
    for i in range(n+1):
        z=h*i/n
        depth=h-z
        p=ka*gamma*depth+ka*surcharge
        V=ka*gamma*depth*depth/2+ka*surcharge*depth
        M=ka*gamma*depth**3/6+ka*surcharge*depth**2/2
        stem_p.append((z,p)); stem_v.append((z,V)); stem_m.append((z,M))
    st.markdown(svg_chart('Stem Lateral Earth Pressure','Depth from top (m)','Pressure (kN/m²)',[(stem_p,'p')],900,420), unsafe_allow_html=True)
    st.markdown(svg_chart('Stem SFD','Depth from top (m)','Shear V (kN/m)',[(stem_v,'V')],900,420), unsafe_allow_html=True)
    st.markdown(svg_chart('Stem BMD','Depth from top (m)','Moment M (kN·m/m)',[(stem_m,'M')],900,420), unsafe_allow_html=True)
    st.write(f'Stem ultimate design: **Vu = {Vu_stem:.2f} kN/m**, **Mu = {Mu_stem:.2f} kN·m/m**.')
    st.markdown(pressure_svg(qmax,qmin,base_L,toe,stem_base), unsafe_allow_html=True)

with t4:
    st.subheader('Reinforcement detailing')
    detail = wall_detail_svg(base_L,toe,stem_base,stem_top,base_thk,stem_h,stem_main_dia,s_stem,toe_dia,s_toe,heel_dia,s_heel)
    st.markdown(detail, unsafe_allow_html=True)
    st.download_button('Download reinforcement detail SVG', svg_bytes(detail), 'retaining_wall_reinforcement_detail.svg', 'image/svg+xml')
    st.markdown('### Main reinforcement')
    st.write(f'**Stem main vertical:** {stem_main_dia}ϕ @ {s_stem:.0f} mm c/c near front face; Ast provided = {Ast_stem_prov:.0f} mm²/m.')
    st.write(f'**Toe main:** {toe_dia}ϕ @ {s_toe:.0f} mm c/c bottom; Ast provided = {Ast_toe_prov:.0f} mm²/m.')
    st.write(f'**Heel main:** {heel_dia}ϕ @ {s_heel:.0f} mm c/c top; Ast provided = {Ast_heel_prov:.0f} mm²/m.')
    st.write('**Stem horizontal:** lower 1/3 = 8ϕ @ 100 front / 200 rear; middle 1/3 = 8ϕ @ 200 front / 400 rear; upper 1/3 = 8ϕ @ 300 front / 600 rear, following the supplied Example 14.9 detailing.')
    st.info('Final reinforcement and detailing must be checked against the governing IS code, exposure, development length, crack-control and project-specific requirements.')

with t5:
    st.subheader('Bar Bending Schedule / BBS')
    bbs = [
        ['S1','Stem main vertical',stem_main_dia,f'{s_stem:.0f}','Front face',f'Ast provided {Ast_stem_prov:.0f} mm²/m'],
        ['S2','Stem nominal vertical',10,'300','Front face','Source-example nominal reinforcement'],
        ['S3','Stem horizontal',8,'100','Front face – lower 1/3','Temperature / shrinkage'],
        ['S4','Stem horizontal',8,'200','Rear face – lower 1/3','Temperature / shrinkage'],
        ['S5','Stem horizontal',8,'200','Front face – middle 1/3','Temperature / shrinkage'],
        ['S6','Stem horizontal',8,'400','Rear face – middle 1/3','Temperature / shrinkage'],
        ['S7','Stem horizontal',8,'300','Front face – upper 1/3','Temperature / shrinkage'],
        ['S8','Stem horizontal',8,'600','Rear face – upper 1/3','Temperature / shrinkage'],
        ['T1','Toe main',toe_dia,f'{s_toe:.0f}','Bottom',f'Ast provided {Ast_toe_prov:.0f} mm²/m'],
        ['H1','Heel main',heel_dia,f'{s_heel:.0f}','Top',f'Ast provided {Ast_heel_prov:.0f} mm²/m'],
        ['K1','Shear key / connection',stem_main_dia,f'{s_stem:.0f}','Key / stem connection','Detail anchorage as required'],
    ]
    st.table(bbs)
    csv='Mark,Bar description,Dia (mm),Spacing (mm),Location,Remarks\n'+'\n'.join(','.join(map(str,r)) for r in bbs)
    st.download_button('Download BBS CSV', csv.encode('utf-8'), 'retaining_wall_BBS.csv', 'text/csv')

with t6:
    st.subheader('Export')
    summary = [
        ['Ka',f'{ka:.4f}','-'],['Kp',f'{kp:.4f}','-'],['Pa',f'{pa:.2f}','kN/m'],['Mo',f'{Mo:.2f}','kN·m/m'],
        ['Total vertical load W',f'{W:.2f}','kN/m'],['Overturning FS',f'{FS_overturning:.3f}','-'],
        ['Sliding FS without key',f'{FS_slide_no_key:.3f}','-'],['Sliding FS with key',f'{FS_slide_key:.3f}','-'],
        ['qmax',f'{qmax:.2f}','kN/m²'],['qmin',f'{qmin:.2f}','kN/m²'],['Stem Mu',f'{Mu_stem:.2f}','kN·m/m'],
        ['Stem Ast required',f'{Ast_stem:.0f}','mm²/m'],['Stem Ast provided',f'{Ast_stem_prov:.0f}','mm²/m'],
        ['Toe Mu',f'{Mu_toe:.2f}','kN·m/m'],['Heel Mu',f'{Mu_heel:.2f}','kN·m/m']]
    st.table(summary)
    csv='Parameter,Value,Unit\n'+'\n'.join(','.join(r) for r in summary)
    st.download_button('Download Design Summary CSV', csv.encode('utf-8'), 'retaining_wall_design_summary.csv', 'text/csv')
    st.download_button('Download BBS CSV', csv.encode('utf-8'), 'retaining_wall_BBS.csv', 'text/csv')

st.divider()
st.caption('Design aid based on the supplied Example 14.9 workflow. Independent engineering review and governing-code verification are required before construction.')
