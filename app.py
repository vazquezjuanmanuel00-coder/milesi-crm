import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# ── Credenciales ───────────────────────────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ── Constantes ─────────────────────────────────────────────────────────────────
USUARIOS = ['Matias', 'Administracion']

ESTADO_CONTACTO = [
    'Sin gestionar',
    'Contactado',
    'No se logró contacto',
    'No se contactó',
]
ESTADO_CLIENTE = [
    'No cliente',
    'Potencial Cliente',
    'Cliente',
    'No le interesa',
]

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title='CRM Seguimiento',
    layout='wide',
    page_icon='📋',
    initial_sidebar_state='expanded',
)

st.markdown("""
<style>
  div[data-testid="metric-container"] {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
  }
</style>
""", unsafe_allow_html=True)

# ── Supabase client ────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=120)
def load_crm():
    sb = get_supabase()
    rows = []
    limit = 1000
    offset = 0
    while True:
        res = sb.table('crm_contactos').select('*').range(offset, offset + limit - 1).execute()
        rows.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
    df = pd.DataFrame(rows).fillna('')
    df['id'] = df['id'].astype(int)
    return df


@st.cache_data(ttl=30)
def load_tracking():
    sb = get_supabase()
    res = sb.table('crm_seguimiento').select('*').execute()
    if res.data:
        df = pd.DataFrame(res.data).fillna('')
        df['id'] = df['id'].astype(int)
        return df
    cols = ['id','estado_contacto','estado_cliente',
            'asignado_a','notas','actualizado_por','ultima_actualizacion']
    return pd.DataFrame(columns=cols)


def upsert_seguimiento(rows: list[dict]):
    sb = get_supabase()
    sb.table('crm_seguimiento').upsert(rows).execute()
    st.cache_data.clear()


def merge_data(crm, tracking):
    df = crm.merge(tracking, on='id', how='left')
    df['estado_contacto']      = df['estado_contacto'].fillna('Sin gestionar')
    df['estado_cliente']       = df['estado_cliente'].fillna('No cliente')
    df['asignado_a']           = df['asignado_a'].fillna('')
    df['notas']                = df['notas'].fillna('')
    df['actualizado_por']      = df['actualizado_por'].fillna('')
    df['ultima_actualizacion'] = df['ultima_actualizacion'].fillna('')
    return df

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

# ── Cargar datos ───────────────────────────────────────────────────────────────
crm      = load_crm()
tracking = load_tracking()
df       = merge_data(crm, tracking)
usuario  = st.session_state.usuario

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {usuario}")
    if st.button("🔄 Cambiar usuario", use_container_width=True):
        st.session_state.usuario = None
        st.rerun()
    if st.button("🔃 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("### 🔍 Filtros")

    ciudades = sorted(df['ciudad'].replace('', pd.NA).dropna().unique())
    filtro_ciudad      = st.multiselect("Ciudad", ciudades)
    filtro_estado_c    = st.multiselect("Estado Contacto", ESTADO_CONTACTO)
    filtro_estado_cl   = st.multiselect("Estado Cliente", ESTADO_CLIENTE)
    filtro_asignado    = st.multiselect("Asignado a", USUARIOS)
    filtro_texto       = st.text_input("🔎 Buscar empresa...")

    st.divider()
    if usuario == 'Administracion':
        vista = st.radio("Vista", ['Contactos', 'Comparativa Matias vs Admin'])
    else:
        vista = 'Contactos'

# ── Aplicar filtros ────────────────────────────────────────────────────────────
mask = pd.Series([True] * len(df), index=df.index)
if filtro_ciudad:
    mask &= df['ciudad'].isin(filtro_ciudad)
if filtro_estado_c:
    mask &= df['estado_contacto'].isin(filtro_estado_c)
if filtro_estado_cl:
    mask &= df['estado_cliente'].isin(filtro_estado_cl)
if filtro_asignado:
    mask &= df['asignado_a'].isin(filtro_asignado)
if filtro_texto:
    mask &= df['nombre_empresa'].str.contains(filtro_texto, case=False, na=False)

filtered = df[mask].reset_index(drop=True)

# ── Header y métricas ──────────────────────────────────────────────────────────
st.markdown("## 📋 CRM — Seguimiento de Clientes")
st.markdown(f"*Local Electrodomésticos · **{usuario}***")
st.divider()

total         = len(df)
sin_gestionar = len(df[df['estado_contacto'] == 'Sin gestionar'])
contactados   = len(df[df['estado_contacto'] == 'Contactado'])
potenciales   = len(df[df['estado_cliente']  == 'Potencial Cliente'])
clientes      = len(df[df['estado_cliente']  == 'Cliente'])
no_interesan  = len(df[df['estado_cliente']  == 'No le interesa'])

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total",           total)
c2.metric("Sin gestionar",   sin_gestionar)
c3.metric("Contactados",     contactados)
c4.metric("Potencial",       potenciales)
c5.metric("Clientes",        clientes)
c6.metric("No le interesa",  no_interesan)

st.divider()

# ── Vista comparativa (Admin) ──────────────────────────────────────────────────
if vista == 'Comparativa Matias vs Admin':
    st.markdown("### 📊 Comparativa Matias vs Administracion")
    cola, colb = st.columns(2)

    for user_name, col in [('Matias', cola), ('Administracion', colb)]:
        sub = df[df['asignado_a'] == user_name]
        with col:
            st.markdown(f"#### 👤 {user_name} — {len(sub)} asignados")
            if len(sub):
                for label, campo in [('Contacto', 'estado_contacto'), ('Cliente', 'estado_cliente')]:
                    st.markdown(f"**{label}**")
                    tbl = sub[campo].value_counts().reset_index()
                    tbl.columns = ['Estado', 'Cantidad']
                    st.dataframe(tbl, hide_index=True, use_container_width=True)
            else:
                st.info("Sin contactos asignados aún.")
    st.stop()

# ── Tabla editable ─────────────────────────────────────────────────────────────
st.markdown(f"### 📝 Contactos — {len(filtered)} de {total}")

SHOW_COLS = ['id','nombre_empresa','ciudad','telefono','tipo',
             'estado_contacto','estado_cliente','asignado_a','notas']

edited = st.data_editor(
    filtered[SHOW_COLS],
    column_config={
        'id': st.column_config.NumberColumn(
            'ID', disabled=True, width='small'),
        'nombre_empresa': st.column_config.TextColumn(
            'Empresa', disabled=True, width='large'),
        'ciudad': st.column_config.TextColumn(
            'Ciudad', disabled=True, width='medium'),
        'telefono': st.column_config.TextColumn(
            'Teléfono', disabled=True, width='medium'),
        'tipo': st.column_config.TextColumn(
            'Tipo', disabled=True, width='small'),
        'estado_contacto': st.column_config.SelectboxColumn(
            'Estado Contacto', options=ESTADO_CONTACTO,
            required=True, width='medium'),
        'estado_cliente': st.column_config.SelectboxColumn(
            'Estado Cliente', options=ESTADO_CLIENTE,
            required=True, width='medium'),
        'asignado_a': st.column_config.SelectboxColumn(
            'Asignado a', options=[''] + USUARIOS, width='small'),
        'notas': st.column_config.TextColumn(
            'Notas', width='large'),
    },
    hide_index=True,
    use_container_width=True,
    num_rows='fixed',
    key='tabla_editor',
)

# ── Guardar ────────────────────────────────────────────────────────────────────
col_btn, _ = st.columns([1, 5])
with col_btn:
    guardar = st.button('💾 Guardar cambios', type='primary', use_container_width=True)

if guardar:
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
    rows_to_upsert = []
    for _, row in edited.iterrows():
        rows_to_upsert.append({
            'id':                   int(row['id']),
            'estado_contacto':      row['estado_contacto'],
            'estado_cliente':       row['estado_cliente'],
            'asignado_a':           row['asignado_a'] or '',
            'notas':                row['notas'] or '',
            'actualizado_por':      usuario,
            'ultima_actualizacion': ahora,
        })
    upsert_seguimiento(rows_to_upsert)
    st.success(f'✅ {len(rows_to_upsert)} registros guardados · {usuario} · {ahora}')
    st.rerun()

st.divider()
st.caption("CRM Local Electrodomésticos · Grupo Yex")
