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

def tiene_altura(direccion):
    """True si la dirección tiene un número de 3+ dígitos (altura real)."""
    return bool(re.search(r'\b\d{3,}\b', str(direccion))) if direccion else False

# ── Supabase ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=300)
def load_crm():
    sb = get_supabase()
    rows, limit, offset = [], 1000, 0
    while True:
        res = sb.table('crm_contactos').select('*').range(offset, offset + limit - 1).execute()
        rows.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
    df = pd.DataFrame(rows).fillna('')
    df['id'] = df['id'].astype(int)
    df['tiene_altura'] = df['direccion'].apply(tiene_altura)
    return df

@st.cache_data(ttl=20)
def load_tracking():
    sb = get_supabase()
    res = sb.table('crm_seguimiento').select('*').execute()
    if res.data:
        df = pd.DataFrame(res.data).fillna('')
        df['id'] = df['id'].astype(int)
        return df
    return pd.DataFrame(columns=[
        'id','estado_contacto','estado_cliente',
        'asignado_a','notas','actualizado_por',
        'ultima_actualizacion','vendedor'
    ])

@st.cache_data(ttl=30)
def load_vendors():
    sb = get_supabase()
    res = sb.table('vendedores').select('*').order('id').execute()
    return res.data if res.data else [{'id': i, 'nombre': f'Vendedor {i}'} for i in range(1, 6)]

def save_vendor(vid, nombre):
    get_supabase().table('vendedores').upsert({'id': vid, 'nombre': nombre}).execute()
    st.cache_data.clear()

def upsert_rows(rows):
    get_supabase().table('crm_seguimiento').upsert(rows).execute()
    st.cache_data.clear()

def merge_data(crm, tracking):
    df = crm.merge(tracking, on='id', how='left')
    df['estado_contacto']      = df['estado_contacto'].fillna('Sin gestionar')
    df['estado_cliente']       = df['estado_cliente'].fillna('No cliente')
    df['asignado_a']           = df['asignado_a'].fillna('')
    df['vendedor']             = df['vendedor'].fillna('')
    df['notas']                = df['notas'].fillna('')
    df['actualizado_por']      = df['actualizado_por'].fillna('')
    df['ultima_actualizacion'] = df['ultima_actualizacion'].fillna('')
    return df

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title='CRM Milesi', layout='wide', page_icon='📋')
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background:#f8f9fa; border:1px solid #dee2e6;
    border-radius:8px; padding:12px;
}
</style>
""", unsafe_allow_html=True)

# ── Login ──────────────────────────────────────────────────────────────────────
if 'usuario' not in st.session_state:
    st.session_state.usuario = None

if st.session_state.usuario is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("## 📋 CRM — Local Electrodomésticos")
        st.markdown("#### ¿Quién sos?")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button('👤  Matias', use_container_width=True, type='primary'):
            st.session_state.usuario = 'Matias'
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button('🏢  Administracion', use_container_width=True):
            st.session_state.usuario = 'Administracion'
            st.rerun()
    st.stop()

# ── Datos ──────────────────────────────────────────────────────────────────────
crm     = load_crm()
tracking= load_tracking()
vendors = load_vendors()
vnames  = [''] + [v['nombre'] for v in vendors]
df      = merge_data(crm, tracking)
usuario = st.session_state.usuario

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {usuario}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cambiar usuario", use_container_width=True):
            st.session_state.usuario = None
            st.rerun()
    with c2:
        if st.button("Actualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🔍 Filtros")
    ciudades        = sorted(df['ciudad'].replace('', pd.NA).dropna().unique())
    filtro_ciudad   = st.multiselect("Ciudad / Zona", ciudades)
    filtro_ec       = st.multiselect("Estado Contacto", ESTADO_CONTACTO)
    filtro_ecl      = st.multiselect("Estado Cliente", ESTADO_CLIENTE)
    filtro_vendedor = st.multiselect("Vendedor", [v['nombre'] for v in vendors])
    filtro_texto    = st.text_input("🔎 Buscar empresa...")
    solo_altura     = st.toggle("Solo con dirección válida", value=False)

    st.divider()

    # Gestión de vendedores (solo Admin)
    if usuario == 'Administracion':
        with st.expander("⚙️ Gestionar Vendedores"):
            st.caption("Renombrá cada vendedor")
            with st.form("form_vendors"):
                nuevos = {}
                for v in vendors:
                    nuevos[v['id']] = st.text_input(
                        f"Vendedor {v['id']}", value=v['nombre'], key=f"vend_{v['id']}")
                if st.form_submit_button("Guardar nombres", type='primary'):
                    for vid, nombre in nuevos.items():
                        save_vendor(vid, nombre)
                    st.success("Nombres actualizados")
                    st.rerun()
        st.divider()
        vista = st.radio("Vista", ['Contactos', 'Comparativa por vendedor'])
    else:
        vista = 'Contactos'

# ── Aplicar filtros ────────────────────────────────────────────────────────────
mask = pd.Series([True] * len(df), index=df.index)
if filtro_ciudad:    mask &= df['ciudad'].isin(filtro_ciudad)
if filtro_ec:        mask &= df['estado_contacto'].isin(filtro_ec)
if filtro_ecl:       mask &= df['estado_cliente'].isin(filtro_ecl)
if filtro_vendedor:  mask &= df['vendedor'].isin(filtro_vendedor)
if filtro_texto:     mask &= df['nombre_empresa'].str.contains(filtro_texto, case=False, na=False)
if solo_altura:      mask &= df['tiene_altura']

filtered = df[mask].reset_index(drop=True)

# ── Header + métricas ──────────────────────────────────────────────────────────
st.markdown("## 📋 CRM — Local Electrodomésticos")
st.markdown(f"*Usuario: **{usuario}***")
st.divider()

total       = len(df)
con_altura  = int(df['tiene_altura'].sum())
sin_gest    = len(df[df['estado_contacto'] == 'Sin gestionar'])
contactados = len(df[df['estado_contacto'] == 'Contactado'])
potenciales = len(df[df['estado_cliente']  == 'Potencial Cliente'])
clientes    = len(df[df['estado_cliente']  == 'Cliente'])

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total",         total)
c2.metric("Con dirección", con_altura)
c3.metric("Sin gestionar", sin_gest)
c4.metric("Contactados",   contactados)
c5.metric("Potencial",     potenciales)
c6.metric("Clientes",      clientes)
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
                tbl.columns = ['Estado', 'N']
                st.dataframe(tbl, hide_index=True, use_container_width=True)
    st.stop()

# ── Asignación masiva ──────────────────────────────────────────────────────────
st.markdown(f"### 📝 Contactos — {len(filtered)} de {total}")

with st.expander(f"⚡ Asignación masiva — asignar los {len(filtered)} filtrados de una vez"):
    st.caption("Asigna todos los contactos del filtro actual a un vendedor.")
    colv, colb = st.columns([2, 1])
    with colv:
        vendedor_masivo = st.selectbox(
            "Vendedor:", [v['nombre'] for v in vendors], key='vend_masivo')
    with colb:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"Asignar {len(filtered)} contactos", type='primary', use_container_width=True):
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
            upsert_rows([{
                'id':                   int(r['id']),
                'estado_contacto':      r['estado_contacto'],
                'estado_cliente':       r['estado_cliente'],
                'asignado_a':           r.get('asignado_a', ''),
                'notas':                r['notas'],
                'vendedor':             vendedor_masivo,
                'actualizado_por':      usuario,
                'ultima_actualizacion': ahora,
            } for _, r in filtered.iterrows()])
            st.success(f"{len(filtered)} contactos asignados a {vendedor_masivo}")
            st.rerun()

# ── Tabla editable ─────────────────────────────────────────────────────────────
SHOW = ['_sel','id','tiene_altura','nombre_empresa','ciudad',
        'direccion','telefono','estado_contacto','estado_cliente','vendedor','notas']

tbl = filtered.copy()
tbl['_sel'] = False

edited = st.data_editor(
    tbl[[c for c in SHOW if c in tbl.columns]],
    column_config={
        '_sel': st.column_config.CheckboxColumn(
            '✓', width='small'),
        'id': st.column_config.NumberColumn(
            'ID', disabled=True, width='small'),
        'tiene_altura': st.column_config.CheckboxColumn(
            'Dir.✓', disabled=True, width='small',
            help='Tiene altura en la dirección'),
        'nombre_empresa': st.column_config.TextColumn(
            'Empresa', disabled=True, width='large'),
        'ciudad': st.column_config.TextColumn(
            'Ciudad', disabled=True, width='medium'),
        'direccion': st.column_config.TextColumn(
            'Dirección', disabled=True, width='large'),
        'telefono': st.column_config.TextColumn(
            'Teléfono', disabled=True, width='medium'),
        'estado_contacto': st.column_config.SelectboxColumn(
            'Contacto', options=ESTADO_CONTACTO, required=True, width='medium'),
        'estado_cliente': st.column_config.SelectboxColumn(
            'Cliente', options=ESTADO_CLIENTE, required=True, width='medium'),
        'vendedor': st.column_config.SelectboxColumn(
            'Vendedor', options=vnames, width='medium'),
        'notas': st.column_config.TextColumn('Notas', width='large'),
    },
    hide_index=True,
    use_container_width=True,
    num_rows='fixed',
    key='tabla_editor',
)

# ── Barra de acciones ──────────────────────────────────────────────────────────
selected = edited[edited['_sel'] == True]
n_sel    = len(selected)

colA, colB, colC, _ = st.columns([1.2, 1, 1.8, 2])

with colA:
    if st.button('💾 Guardar cambios', type='primary', use_container_width=True):
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
        upsert_rows([{
            'id':                   int(r['id']),
            'estado_contacto':      r['estado_contacto'],
            'estado_cliente':       r['estado_cliente'],
            'asignado_a':           r.get('asignado_a', ''),
            'notas':                r['notas'] or '',
            'vendedor':             r['vendedor'] or '',
            'actualizado_por':      usuario,
            'ultima_actualizacion': ahora,
        } for _, r in edited.iterrows()])
        st.success(f"Guardado — {len(edited)} registros")
        st.rerun()

if n_sel > 0:
    with colB:
        st.info(f"{n_sel} marcados")
    with colC:
        vend_sel = st.selectbox(
            "Asignar marcados a:",
            [v['nombre'] for v in vendors],
            key='vend_sel', label_visibility='collapsed')
        if st.button(f"Asignar {n_sel} marcados", use_container_width=True):
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
            upsert_rows([{
                'id':                   int(r['id']),
                'estado_contacto':      r['estado_contacto'],
                'estado_cliente':       r['estado_cliente'],
                'asignado_a':           r.get('asignado_a', ''),
                'notas':                r['notas'] or '',
                'vendedor':             vend_sel,
                'actualizado_por':      usuario,
                'ultima_actualizacion': ahora,
            } for _, r in selected.iterrows()])
            st.success(f"{n_sel} contactos asignados a {vend_sel}")
            st.rerun()

st.divider()
st.caption("CRM Local Electrodomésticos · Grupo Yex")
