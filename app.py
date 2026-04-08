import streamlit as st
import pandas as pd
import re
from supabase import create_client, Client
from datetime import datetime

# ── Credenciales ───────────────────────────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

USUARIOS        = ['Matias', 'Administracion']
ESTADO_CONTACTO = ['Sin gestionar', 'Contactado', 'No se logró contacto', 'No se contactó']
ESTADO_CLIENTE  = ['No cliente', 'Potencial Cliente', 'Cliente', 'No le interesa']

# ── Supabase ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=300)
def load_crm():
    sb = get_sb()
    rows, limit, offset = [], 1000, 0
    while True:
        res = sb.table('crm_contactos').select('*').range(offset, offset+limit-1).execute()
        rows.extend(res.data)
        if len(res.data) < limit: break
        offset += limit
    df = pd.DataFrame(rows).fillna('')
    df['id'] = df['id'].astype(int)
    df['tiene_altura'] = df['direccion'].apply(
        lambda d: bool(re.search(r'\b\d{3,}\b', str(d))) if d else False)
    return df

@st.cache_data(ttl=20)
def load_tracking():
    res = get_sb().table('crm_seguimiento').select('*').execute()
    if res.data:
        df = pd.DataFrame(res.data).fillna('')
        df['id'] = df['id'].astype(int)
        return df
    return pd.DataFrame(columns=['id','estado_contacto','estado_cliente',
                                  'asignado_a','notas','actualizado_por',
                                  'ultima_actualizacion','vendedor'])

@st.cache_data(ttl=30)
def load_vendors():
    res = get_sb().table('vendedores').select('*').order('id').execute()
    return res.data if res.data else [{'id':i,'nombre':f'Vendedor {i}'} for i in range(1,6)]

def save_vendor(vid, nombre):
    get_sb().table('vendedores').upsert({'id': vid, 'nombre': nombre}).execute()
    load_vendors.clear()

def add_vendor(nombre):
    vendors = load_vendors()
    next_id = max(v['id'] for v in vendors) + 1 if vendors else 1
    get_sb().table('vendedores').insert({'id': next_id, 'nombre': nombre}).execute()
    load_vendors.clear()

def upsert_rows(rows):
    get_sb().table('crm_seguimiento').upsert(rows).execute()
    load_tracking.clear()

def merge_data(crm, tracking):
    df = crm.merge(tracking, on='id', how='left')
    for col, default in [('estado_contacto','Sin gestionar'),('estado_cliente','No cliente'),
                          ('asignado_a',''),('vendedor',''),('notas',''),
                          ('actualizado_por',''),('ultima_actualizacion','')]:
        df[col] = df[col].fillna(default)
    return df

def auto_save(cid, row_dict, usuario):
    """Guarda al instante y registra estado previo para deshacer."""
    ec   = st.session_state.get(f"ec_{cid}",  row_dict['estado_contacto'])
    ecl  = st.session_state.get(f"ecl_{cid}", row_dict['estado_cliente'])
    vend = st.session_state.get(f"vend_{cid}",row_dict['vendedor'])
    nota = st.session_state.get(f"nota_{cid}",row_dict['notas'])

    # Descripción del cambio para el undo bar
    empresa = row_dict.get('nombre_empresa', f'ID {cid}')
    changes = []
    if ec   != row_dict['estado_contacto']: changes.append(f"Contacto: **{row_dict['estado_contacto']}** → **{ec}**")
    if ecl  != row_dict['estado_cliente']:  changes.append(f"Cliente: **{row_dict['estado_cliente']}** → **{ecl}**")
    if vend != row_dict['vendedor']:         changes.append(f"Vendedor: **{row_dict['vendedor'] or 'ninguno'}** → **{vend or 'ninguno'}**")
    if nota != row_dict['notas']:            changes.append(f"Nota actualizada")
    mensaje = f"**{empresa}** — " + " · ".join(changes) if changes else f"**{empresa}** actualizado"

    # Guardar estado previo para undo
    st.session_state.last_action = {
        'mensaje':    mensaje,
        'prev_state': {
            'id':                   cid,
            'estado_contacto':      row_dict['estado_contacto'],
            'estado_cliente':       row_dict['estado_cliente'],
            'vendedor':             row_dict['vendedor'],
            'notas':                row_dict['notas'],
            'asignado_a':           row_dict.get('asignado_a',''),
            'actualizado_por':      row_dict.get('actualizado_por',''),
            'ultima_actualizacion': row_dict.get('ultima_actualizacion',''),
        }
    }

    upsert_rows([{
        'id':                   cid,
        'estado_contacto':      ec   or 'Sin gestionar',
        'estado_cliente':       ecl  or 'No cliente',
        'vendedor':             (vend if vend and vend != 'Sin asignar' else ''),
        'notas':                nota or '',
        'asignado_a':           row_dict.get('asignado_a',''),
        'actualizado_por':      usuario,
        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }])

# ── Branding ───────────────────────────────────────────────────────────────────
MILESI_TEAL   = '#00838F'
MILESI_ORANGE = '#E8772E'

MILESI_LOGO = f"""
<div style="display:flex;align-items:center;gap:16px;padding:8px 0 4px 0">
  <div style="border:3px solid {MILESI_TEAL};border-radius:50%/50%;
              padding:10px 22px;background:white;line-height:1.2;text-align:center;
              box-shadow:0 2px 8px rgba(0,131,143,0.15)">
    <div style="font-size:20px;font-weight:800;letter-spacing:-0.5px">
      <span style="color:#222">Mile<span style="font-size:22px">SI</span></span>
      <span style="color:{MILESI_ORANGE}"> Hogar</span>
    </div>
    <div style="font-size:8px;color:#666;letter-spacing:0.3px;margin-top:1px">
      La atención que estabas esperando
    </div>
  </div>
  <div>
    <div style="font-size:20px;font-weight:700;color:#ffffff">CRM — Seguimiento de Clientes</div>
    <div style="font-size:13px;color:#aaaaaa">Gestión comercial y asignación de vendedores</div>
  </div>
</div>
"""

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title='CRM · Milesi Hogar', layout='wide', page_icon='🏠')
st.markdown(f"""
<style>
div[data-testid="metric-container"]{{
    background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:10px}}
div[data-testid="stVerticalBlockBorderWrapper"]{{border-radius:12px}}
.filter-bar{{background:#f1f3f5;border-radius:10px;padding:10px 16px;margin-bottom:12px}}
/* Botón primario con color Milesi */
div[data-testid="stButton"] button[kind="primary"]{{
    background:{MILESI_TEAL} !important;border-color:{MILESI_TEAL} !important}}
/* Pills activas */
div[data-testid="stPills"] span[aria-selected="true"]{{
    background:{MILESI_TEAL} !important}}
</style>""", unsafe_allow_html=True)

# ── Login ──────────────────────────────────────────────────────────────────────
if 'usuario'     not in st.session_state: st.session_state.usuario     = None
if 'page'        not in st.session_state: st.session_state.page        = 0
if 'last_action' not in st.session_state: st.session_state.last_action = None

if st.session_state.usuario is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1,2,1])
    with col:
        st.markdown("## 📋 CRM — Local Electrodomésticos")
        st.markdown("#### ¿Quién sos?")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button('👤  Matias',        use_container_width=True, type='primary'):
            st.session_state.usuario = 'Matias';        st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button('🏢  Administracion', use_container_width=True):
            st.session_state.usuario = 'Administracion'; st.rerun()
    st.stop()

# ── Datos ──────────────────────────────────────────────────────────────────────
crm     = load_crm()
tracking= load_tracking()
vendors = load_vendors()
vnames  = [v['nombre'] for v in vendors]
df      = merge_data(crm, tracking)
usuario = st.session_state.usuario

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:

    # Usuario
    st.markdown(f"### 👤 {usuario}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cambiar",    use_container_width=True):
            st.session_state.usuario = None; st.rerun()
    with c2:
        if st.button("Actualizar", use_container_width=True):
            load_crm.clear(); load_tracking.clear(); load_vendors.clear(); st.rerun()

    st.divider()

    # ── VENDEDORES ─────────────────────────────────────────────────────────────
    st.markdown("## 🧑‍💼 Vendedores")

    for v in vendors:
        sub      = df[df['vendedor'] == v['nombre']]
        total_v  = len(sub)
        contact  = len(sub[sub['estado_contacto'] == 'Contactado'])
        cliente  = len(sub[sub['estado_cliente']  == 'Cliente'])
        potencial= len(sub[sub['estado_cliente']  == 'Potencial Cliente'])

        label = f"{v['nombre']}  ·  {total_v} asignados"
        with st.expander(label):
            # Stats compactas
            s1, s2, s3 = st.columns(3)
            s1.metric("Contactados", contact)
            s2.metric("Potencial",   potencial)
            s3.metric("Clientes",    cliente)

            if total_v:
                st.markdown("**Contacto**")
                for ec in ESTADO_CONTACTO:
                    n = len(sub[sub['estado_contacto']==ec])
                    if n:
                        bar = "█" * min(n, 20)
                        st.caption(f"{ec}: {n}  {bar}")
                st.markdown("**Cliente**")
                for ecl in ESTADO_CLIENTE:
                    n = len(sub[sub['estado_cliente']==ecl])
                    if n:
                        bar = "█" * min(n, 20)
                        st.caption(f"{ecl}: {n}  {bar}")

            st.markdown("---")
            new_name = st.text_input("Renombrar", value=v['nombre'],
                                     key=f"vren_{v['id']}", label_visibility='collapsed',
                                     placeholder="Nuevo nombre...")
            if st.button("Guardar nombre", key=f"vsave_{v['id']}", use_container_width=True):
                save_vendor(v['id'], new_name)
                st.success("Actualizado")
                st.rerun()

    st.markdown("---")
    with st.expander("➕ Agregar vendedor"):
        with st.form("add_vend_form"):
            nuevo_nombre = st.text_input("Nombre del vendedor")
            if st.form_submit_button("Agregar", type='primary'):
                if nuevo_nombre.strip():
                    add_vendor(nuevo_nombre.strip())
                    st.success(f"'{nuevo_nombre}' agregado")
                    st.rerun()

    if usuario == 'Administracion':
        st.divider()
        vista = st.radio("Vista", ['Ficheros', 'Comparativa'])
    else:
        vista = 'Ficheros'

# ── HEADER ─────────────────────────────────────────────────────────────────────
st.markdown(MILESI_LOGO, unsafe_allow_html=True)
st.divider()

# ── BARRA DE FILTROS (arriba) ──────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    f1, f2, f3, f4, f5, f6 = st.columns([2, 2, 2, 2, 2, 1])
    with f1:
        filtro_texto    = st.text_input("", placeholder="🔎 Buscar empresa...", label_visibility='collapsed')
    with f2:
        ciudades        = sorted(df['ciudad'].replace('', pd.NA).dropna().unique())
        filtro_ciudad   = st.multiselect("", ciudades, placeholder="📍 Ciudad", label_visibility='collapsed')
    with f3:
        filtro_ec       = st.multiselect("", ESTADO_CONTACTO, placeholder="💬 Contacto", label_visibility='collapsed')
    with f4:
        filtro_ecl      = st.multiselect("", ESTADO_CLIENTE,  placeholder="🏷️ Cliente",  label_visibility='collapsed')
    with f5:
        filtro_vendedor = st.multiselect("", vnames, placeholder="👤 Vendedor", label_visibility='collapsed')
    with f6:
        solo_altura     = st.toggle("Dir. ✓", value=False, help="Solo contactos con dirección válida")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Filtros ────────────────────────────────────────────────────────────────────
mask = pd.Series([True]*len(df), index=df.index)
if filtro_texto:    mask &= df['nombre_empresa'].str.contains(filtro_texto, case=False, na=False)
if filtro_ciudad:   mask &= df['ciudad'].isin(filtro_ciudad)
if filtro_ec:       mask &= df['estado_contacto'].isin(filtro_ec)
if filtro_ecl:      mask &= df['estado_cliente'].isin(filtro_ecl)
if filtro_vendedor: mask &= df['vendedor'].isin(filtro_vendedor)
if solo_altura:     mask &= df['tiene_altura']

filtered = df[mask].reset_index(drop=True)

# ── Métricas ───────────────────────────────────────────────────────────────────
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total",          len(df))
c2.metric("Con dirección",  int(df['tiene_altura'].sum()))
c3.metric("Sin gestionar",  len(df[df['estado_contacto']=='Sin gestionar']))
c4.metric("Contactados",    len(df[df['estado_contacto']=='Contactado']))
c5.metric("Potencial",      len(df[df['estado_cliente']=='Potencial Cliente']))
c6.metric("Clientes",       len(df[df['estado_cliente']=='Cliente']))

# ── UNDO BAR ───────────────────────────────────────────────────────────────────
if st.session_state.last_action:
    action = st.session_state.last_action
    ua, ub, uc = st.columns([6, 1, 1])
    with ua:
        st.success(f"✓  {action['mensaje']}")
    with ub:
        if st.button("↩ Deshacer", use_container_width=True):
            upsert_rows([action['prev_state']])
            st.session_state.last_action = None
            st.rerun()
    with uc:
        if st.button("✕ Cerrar", use_container_width=True):
            st.session_state.last_action = None
            st.rerun()

st.divider()

# ── Vista comparativa ──────────────────────────────────────────────────────────
if vista == 'Comparativa':
    st.markdown("### 📊 Comparativa por vendedor")
    cols = st.columns(min(len(vendors), 4))
    for i, v in enumerate(vendors):
        sub = df[df['vendedor'] == v['nombre']]
        with cols[i % 4]:
            st.markdown(f"**{v['nombre']}**")
            st.metric("Asignados", len(sub))
            if len(sub):
                tbl = sub['estado_cliente'].value_counts().reset_index()
                tbl.columns = ['Estado','N']
                st.dataframe(tbl, hide_index=True, use_container_width=True)
    st.stop()

# ── Asignación masiva ──────────────────────────────────────────────────────────
st.markdown(f"### 📇 {len(filtered)} contactos")
with st.expander("⚡ Asignación masiva"):
    st.caption(f"Asigna todos los {len(filtered)} contactos filtrados a un vendedor.")
    cv, cb = st.columns([3,1])
    with cv:
        vend_masivo = st.selectbox("Vendedor:", vnames, key='vend_masivo')
    with cb:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"Asignar {len(filtered)}", type='primary', use_container_width=True):
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
            upsert_rows([{
                'id': int(r['id']), 'estado_contacto': r['estado_contacto'],
                'estado_cliente': r['estado_cliente'], 'vendedor': vend_masivo,
                'asignado_a': r.get('asignado_a',''), 'notas': r['notas'],
                'actualizado_por': usuario, 'ultima_actualizacion': ahora,
            } for _, r in filtered.iterrows()])
            st.session_state.last_action = {
                'mensaje': f"Asignación masiva: **{len(filtered)} contactos** → **{vend_masivo}**",
                'prev_state': None,
            }
            st.rerun()

# ── Paginación ─────────────────────────────────────────────────────────────────
PER_PAGE   = 12
total_pages= max(1, (len(filtered)-1)//PER_PAGE+1)
if st.session_state.page >= total_pages: st.session_state.page = 0

start     = st.session_state.page * PER_PAGE
end       = min(start + PER_PAGE, len(filtered))
page_data = filtered.iloc[start:end]

pA, pB, pC = st.columns([1,3,1])
with pA:
    if st.button("← Anterior", disabled=st.session_state.page==0, use_container_width=True):
        st.session_state.page -= 1; st.rerun()
with pB:
    st.markdown(
        f"<div style='text-align:center;padding-top:6px'>Página <b>{st.session_state.page+1}</b> de <b>{total_pages}</b></div>",
        unsafe_allow_html=True)
with pC:
    if st.button("Siguiente →", disabled=st.session_state.page>=total_pages-1, use_container_width=True):
        st.session_state.page += 1; st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Ficheros (cards) ───────────────────────────────────────────────────────────
cols = st.columns(2)
for i, (_, row) in enumerate(page_data.iterrows()):
    cid      = int(row['id'])
    row_dict = row.to_dict()
    cb_args  = (cid, row_dict, usuario)

    with cols[i % 2]:
        with st.container(border=True):

            # Cabecera con indicador de estado (se actualiza con cada cambio)
            COLOR_CARD = {
                'No cliente':       '#6c757d',
                'Potencial Cliente':'#0d6efd',
                'Cliente':          '#198754',
                'No le interesa':   '#dc3545',
            }
            ecl_actual = st.session_state.get(f"ecl_{cid}", row['estado_cliente'])
            ec_actual  = st.session_state.get(f"ec_{cid}",  row['estado_contacto'])
            dot_color  = COLOR_CARD.get(ecl_actual, '#6c757d')
            tipo_txt   = f"<small style='color:#888'>{row['tipo']}</small>" if row['tipo'] else ""
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<b>{row["nombre_empresa"]}</b>'
                f'<span>{tipo_txt} &nbsp;'
                f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
                f'background:{dot_color};vertical-align:middle;margin-left:4px" '
                f'title="{ecl_actual}"></span></span></div>',
                unsafe_allow_html=True)

            dir_icon = "✅" if row['tiene_altura'] else "⚠️"
            dir_txt  = row['direccion'] if row['direccion'] else "*sin dirección*"
            tel_txt  = f"📞 {row['telefono']}" if row['telefono'] else ""
            st.caption(f"📍 {row['ciudad']}  ·  {dir_icon} {dir_txt}  {tel_txt}")

            if row['vendedor']:
                st.caption(f"👤 {row['vendedor']}")

            st.markdown("<br>", unsafe_allow_html=True)

            # Pills de estado — auto-guardan al tocar
            ec_idx  = ESTADO_CONTACTO.index(row['estado_contacto']) if row['estado_contacto'] in ESTADO_CONTACTO else 0
            ecl_idx = ESTADO_CLIENTE.index(row['estado_cliente'])   if row['estado_cliente']  in ESTADO_CLIENTE  else 0

            st.pills("Contacto", ESTADO_CONTACTO,
                     default=ESTADO_CONTACTO[ec_idx],
                     key=f"ec_{cid}", label_visibility='collapsed',
                     on_change=auto_save, args=cb_args)

            st.pills("Cliente", ESTADO_CLIENTE,
                     default=ESTADO_CLIENTE[ecl_idx],
                     key=f"ecl_{cid}", label_visibility='collapsed',
                     on_change=auto_save, args=cb_args)

            va, vb = st.columns([3,1])
            with va:
                vend_idx = (vnames.index(row['vendedor'])+1) if row['vendedor'] in vnames else 0
                st.selectbox("Vendedor", ['Sin asignar']+vnames,
                             index=vend_idx, key=f"vend_{cid}",
                             label_visibility='collapsed',
                             on_change=auto_save, args=cb_args)
            with vb:
                st.text_input("Nota", value=row['notas'], placeholder="nota...",
                              key=f"nota_{cid}", label_visibility='collapsed',
                              on_change=auto_save, args=cb_args)

st.divider()

# ── FOOTER ─────────────────────────────────────────────────────────────────────
import os, base64
_logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo_grupoyex.png')
if os.path.exists(_logo_path):
    with open(_logo_path, 'rb') as f:
        _b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:flex-end;'
        f'gap:10px;opacity:0.6;padding:4px 0">'
        f'<span style="font-size:11px;color:#888">Desarrollado por</span>'
        f'<img src="data:image/png;base64,{_b64}" style="height:28px">'
        f'</div>',
        unsafe_allow_html=True
    )
else:
    st.caption("Desarrollado por Grupo Yex")
