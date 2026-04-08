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

COLOR_EC = {
    'Sin gestionar':        '#6c757d',
    'Contactado':           '#198754',
    'No se logró contacto': '#e67e00',
    'No se contactó':       '#dc3545',
}
COLOR_ECL = {
    'No cliente':       '#6c757d',
    'Potencial Cliente':'#0d6efd',
    'Cliente':          '#198754',
    'No le interesa':   '#dc3545',
}

def pill_html(texto, color_map):
    color = color_map.get(texto, '#6c757d')
    return (f'<span style="background:{color};color:#fff;padding:3px 12px;'
            f'border-radius:999px;font-size:11px;font-weight:700;'
            f'display:inline-block;margin:2px 0">{texto}</span>')

def tiene_altura(d):
    return bool(re.search(r'\b\d{3,}\b', str(d))) if d else False

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
    df['tiene_altura'] = df['direccion'].apply(tiene_altura)
    return df

@st.cache_data(ttl=20)
def load_tracking():
    sb = get_sb()
    res = sb.table('crm_seguimiento').select('*').execute()
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
    get_sb().table('vendedores').upsert({'id':vid,'nombre':nombre}).execute()
    st.cache_data.clear()

def upsert_rows(rows):
    get_sb().table('crm_seguimiento').upsert(rows).execute()
    load_tracking.clear()  # solo limpia tracking, no los contactos

def auto_save(cid, row_dict, usuario):
    """Callback: guarda el card apenas cambia cualquier widget."""
    ec   = st.session_state.get(f"ec_{cid}",   row_dict['estado_contacto'])
    ecl  = st.session_state.get(f"ecl_{cid}",  row_dict['estado_cliente'])
    vend = st.session_state.get(f"vend_{cid}",  row_dict['vendedor'])
    nota = st.session_state.get(f"nota_{cid}",  row_dict['notas'])
    upsert_rows([{
        'id':                   cid,
        'estado_contacto':      ec   or 'Sin gestionar',
        'estado_cliente':       ecl  or 'No cliente',
        'vendedor':             (vend if vend and vend != 'Sin asignar' else ''),
        'notas':                nota or '',
        'asignado_a':           row_dict.get('asignado_a', ''),
        'actualizado_por':      usuario,
        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }])
    st.toast("Guardado ✓")

def merge_data(crm, tracking):
    df = crm.merge(tracking, on='id', how='left')
    for col, default in [('estado_contacto','Sin gestionar'),('estado_cliente','No cliente'),
                          ('asignado_a',''),('vendedor',''),('notas',''),
                          ('actualizado_por',''),('ultima_actualizacion','')]:
        df[col] = df[col].fillna(default)
    return df

def make_row(row, ec, ecl, vend, nota, usuario):
    return {
        'id':                   int(row['id']),
        'estado_contacto':      ec  or 'Sin gestionar',
        'estado_cliente':       ecl or 'No cliente',
        'vendedor':             vend or '',
        'notas':                nota or '',
        'asignado_a':           row.get('asignado_a',''),
        'actualizado_por':      usuario,
        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title='CRM Milesi', layout='wide', page_icon='📋')
st.markdown("""
<style>
div[data-testid="metric-container"]{
    background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:12px}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px}
</style>""", unsafe_allow_html=True)

# ── Login ──────────────────────────────────────────────────────────────────────
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'page' not in st.session_state:
    st.session_state.page = 0

if st.session_state.usuario is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1,2,1])
    with col:
        st.markdown("## 📋 CRM — Local Electrodomésticos")
        st.markdown("#### ¿Quién sos?")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button('👤  Matias', use_container_width=True, type='primary'):
            st.session_state.usuario = 'Matias'; st.rerun()
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {usuario}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cambiar", use_container_width=True):
            st.session_state.usuario = None; st.rerun()
    with c2:
        if st.button("Actualizar", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    st.divider()
    st.markdown("### 🔍 Filtros")
    ciudades        = sorted(df['ciudad'].replace('', pd.NA).dropna().unique())
    filtro_ciudad   = st.multiselect("Ciudad / Zona", ciudades)
    filtro_ec       = st.multiselect("Estado Contacto", ESTADO_CONTACTO)
    filtro_ecl      = st.multiselect("Estado Cliente", ESTADO_CLIENTE)
    filtro_vendedor = st.multiselect("Vendedor", vnames)
    filtro_texto    = st.text_input("🔎 Buscar empresa...")
    solo_altura     = st.toggle("Solo con dirección válida", value=False)

    st.divider()
    if usuario == 'Administracion':
        with st.expander("⚙️ Gestionar Vendedores"):
            with st.form("form_vendors"):
                nuevos = {v['id']: st.text_input(f"Vendedor {v['id']}", value=v['nombre'],
                          key=f"vend_cfg_{v['id']}") for v in vendors}
                if st.form_submit_button("Guardar nombres", type='primary'):
                    for vid, nombre in nuevos.items():
                        save_vendor(vid, nombre)
                    st.success("Actualizado"); st.rerun()
        st.divider()
        vista = st.radio("Vista", ['Ficheros', 'Comparativa por vendedor'])
    else:
        vista = 'Ficheros'

# ── Filtros ────────────────────────────────────────────────────────────────────
mask = pd.Series([True]*len(df), index=df.index)
if filtro_ciudad:   mask &= df['ciudad'].isin(filtro_ciudad)
if filtro_ec:       mask &= df['estado_contacto'].isin(filtro_ec)
if filtro_ecl:      mask &= df['estado_cliente'].isin(filtro_ecl)
if filtro_vendedor: mask &= df['vendedor'].isin(filtro_vendedor)
if filtro_texto:    mask &= df['nombre_empresa'].str.contains(filtro_texto, case=False, na=False)
if solo_altura:     mask &= df['tiene_altura']

filtered = df[mask].reset_index(drop=True)

# Reset página si cambió el filtro
total_pages = max(1, (len(filtered)-1)//12+1)
if st.session_state.page >= total_pages:
    st.session_state.page = 0

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 📋 CRM — Local Electrodomésticos")
st.markdown(f"*Usuario: **{usuario}***")
st.divider()

# Métricas
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total",         len(df))
c2.metric("Con dirección", int(df['tiene_altura'].sum()))
c3.metric("Sin gestionar", len(df[df['estado_contacto']=='Sin gestionar']))
c4.metric("Contactados",   len(df[df['estado_contacto']=='Contactado']))
c5.metric("Potencial",     len(df[df['estado_cliente']=='Potencial Cliente']))
c6.metric("Clientes",      len(df[df['estado_cliente']=='Cliente']))
st.divider()

# ── Vista comparativa ──────────────────────────────────────────────────────────
if vista == 'Comparativa por vendedor':
    st.markdown("### 📊 Distribución por vendedor")
    cols = st.columns(min(len(vendors), 5))
    for i, v in enumerate(vendors):
        sub = df[df['vendedor'] == v['nombre']]
        with cols[i % 5]:
            st.markdown(f"**{v['nombre']}**")
            st.metric("Asignados", len(sub))
            if len(sub):
                tbl = sub['estado_cliente'].value_counts().reset_index()
                tbl.columns = ['Estado','N']
                st.dataframe(tbl, hide_index=True, use_container_width=True)
    st.stop()

# ── Asignación masiva ──────────────────────────────────────────────────────────
st.markdown(f"### 📇 {len(filtered)} contactos")
with st.expander(f"⚡ Asignación masiva"):
    st.caption(f"Asigna todos los {len(filtered)} contactos del filtro actual a un vendedor.")
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
            st.success(f"{len(filtered)} contactos → {vend_masivo}")
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Paginación ─────────────────────────────────────────────────────────────────
PER_PAGE  = 12
start     = st.session_state.page * PER_PAGE
end       = min(start + PER_PAGE, len(filtered))
page_data = filtered.iloc[start:end]

pA, pB, pC = st.columns([1,3,1])
with pA:
    if st.button("← Anterior", disabled=st.session_state.page==0, use_container_width=True):
        st.session_state.page -= 1; st.rerun()
with pB:
    st.markdown(f"<div style='text-align:center;padding-top:6px'>Página <b>{st.session_state.page+1}</b> de <b>{total_pages}</b></div>",
                unsafe_allow_html=True)
with pC:
    if st.button("Siguiente →", disabled=st.session_state.page>=total_pages-1, use_container_width=True):
        st.session_state.page += 1; st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Ficheros (cards) ───────────────────────────────────────────────────────────
cols = st.columns(2)
for i, (_, row) in enumerate(page_data.iterrows()):
    cid = int(row['id'])
    with cols[i % 2]:
        with st.container(border=True):

            # ── Cabecera del fichero ───────────────────────────────────────────
            h1, h2 = st.columns([5,1])
            with h1:
                st.markdown(f"**{row['nombre_empresa']}**")
            with h2:
                if row['tipo']:
                    st.markdown(f"`{row['tipo']}`")

            # Dirección + teléfono
            dir_icon = "✅" if row['tiene_altura'] else "⚠️"
            dir_txt  = row['direccion'] if row['direccion'] else "*sin dirección*"
            tel_txt  = f"📞 {row['telefono']}" if row['telefono'] else ""
            st.caption(f"📍 {row['ciudad']}  ·  {dir_icon} {dir_txt}  {tel_txt}")

            # ── Edición instantánea — guarda solo al tocar ────────────────────
            row_dict = row.to_dict()
            cb_args  = (cid, row_dict, usuario)

            ec_idx  = ESTADO_CONTACTO.index(row['estado_contacto']) if row['estado_contacto'] in ESTADO_CONTACTO else 0
            ecl_idx = ESTADO_CLIENTE.index(row['estado_cliente'])   if row['estado_cliente']  in ESTADO_CLIENTE  else 0

            st.pills(
                "Contacto", ESTADO_CONTACTO,
                default=ESTADO_CONTACTO[ec_idx],
                key=f"ec_{cid}", label_visibility='collapsed',
                on_change=auto_save, args=cb_args)

            st.pills(
                "Cliente", ESTADO_CLIENTE,
                default=ESTADO_CLIENTE[ecl_idx],
                key=f"ecl_{cid}", label_visibility='collapsed',
                on_change=auto_save, args=cb_args)

            va, vb = st.columns([3, 1])
            with va:
                vend_idx = (vnames.index(row['vendedor'])+1) if row['vendedor'] in vnames else 0
                st.selectbox(
                    "Vendedor", ['Sin asignar']+vnames,
                    index=vend_idx,
                    key=f"vend_{cid}", label_visibility='collapsed',
                    on_change=auto_save, args=cb_args)
            with vb:
                st.text_input(
                    "Nota", value=row['notas'],
                    placeholder="nota...",
                    key=f"nota_{cid}", label_visibility='collapsed',
                    on_change=auto_save, args=cb_args)

st.divider()
st.caption("CRM Local Electrodomésticos · Grupo Yex")
