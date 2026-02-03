"""
Main Streamlit application for Social Media Analytics Dashboard.
Multi-page app with Configuration, Profiles, Analysis, and Dashboard sections.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from config import (
    ensure_database_initialized, get_all_config, set_apify_token, get_apify_token,
    set_huggingface_model, get_huggingface_model, set_keywords_positive, get_keywords_positive,
    set_keywords_negative, get_keywords_negative, set_actor_id, get_actor_id,
    set_default_limit_posts, get_default_limit_posts, set_default_limit_comments,
    get_default_limit_comments, set_auto_skip_recent, get_auto_skip_recent,
    set_date_from, get_date_from, set_date_to, get_date_to,
    set_last_days, get_last_days
)
from db_utils import (
    get_all_profiles, add_profile, delete_profile,
    get_posts_for_dashboard, get_comments_for_dashboard, get_sentiment_stats
)
from utils import normalize_username_or_url
from scraper import analyze_profiles
from analyzer import reload_analyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Social Media Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Social Media Analytics Dashboard - Análisis de sentimiento para Instagram, TikTok y Facebook"
    }
)

# Custom CSS for better UI
st.markdown("""
<style>
    /* Main container improvements */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Better headings */
    h1 {
        color: #1f77b4;
        border-bottom: 3px solid #1f77b4;
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem;
    }
    
    h2 {
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    h3 {
        color: #34495e;
        margin-top: 1.5rem;
    }
    
    /* Better cards/containers */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    
    /* Better buttons */
    .stButton > button {
        width: 100%;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Better input fields */
    .stTextInput > div > div > input {
        border-radius: 5px;
    }
    
    /* Sidebar improvements */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* Better info boxes */
    .stInfo {
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        border-radius: 5px;
    }
    
    .stSuccess {
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 5px;
    }
    
    .stWarning {
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 5px;
    }
    
    .stError {
        border-left: 4px solid #dc3545;
        padding: 1rem;
        border-radius: 5px;
    }
    
    /* Better spacing */
    .section-spacer {
        margin: 2rem 0;
    }
    
    /* Platform badges */
    .platform-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .platform-facebook {
        background-color: #1877f2;
        color: white;
    }
    
    .platform-instagram {
        background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
        color: white;
    }
    
    .platform-tiktok {
        background-color: #000000;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
ensure_database_initialized()


def main():
    """Main application entry point."""
    # Sidebar header with better styling
    st.sidebar.markdown("""
    <div style='text-align: center; padding: 1rem 0;'>
        <h1 style='color: #1f77b4; margin: 0; font-size: 1.8rem;'>📊 SocialPulse</h1>
        <p style='color: #7f8c8d; margin: 0.5rem 0; font-size: 0.9rem;'>Analytics Dashboard</p>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    # Navigation with better styling
    st.sidebar.markdown("### 🧭 Navegación")
    page = st.sidebar.radio(
        "Navegación",
        ["🏠 Dashboard", "⚙️ Configuración", "👥 Perfiles", "🔄 Análisis"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    
    # Quick stats in sidebar
    try:
        profiles = get_all_profiles()
        if profiles:
            st.sidebar.markdown("### 📈 Resumen Rápido")
            st.sidebar.metric("Perfiles", len(profiles))
            
            platforms_count = {}
            for p in profiles:
                platforms_count[p['platform']] = platforms_count.get(p['platform'], 0) + 1
            
            for platform, count in platforms_count.items():
                platform_emoji = {"facebook": "📘", "instagram": "📷", "tiktok": "🎵"}.get(platform.lower(), "📱")
                st.sidebar.metric(f"{platform_emoji} {platform.capitalize()}", count)
    except:
        pass
    
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "⚙️ Configuración":
        show_configuration()
    elif page == "👥 Perfiles":
        show_profiles()
    elif page == "🔄 Análisis":
        show_analysis()


def show_configuration():
    """Configuration page - edit all settings."""
    # Header
    st.title("⚙️ Configuración")
    st.markdown("Configura todos los parámetros del sistema desde aquí. Los cambios se guardan automáticamente.")
    st.markdown("---")
    
    config = get_all_config()
    
    # Organize in tabs for better UX
    tab1, tab2, tab3, tab4 = st.tabs(["🔑 API & Tokens", "🤖 Análisis", "📊 Límites", "📅 Filtros"])
    
    with tab1:
        st.subheader("🔑 Configuración de APIs")
        
        # Apify Token
        st.markdown("#### Token de Apify")
        apify_token = st.text_input(
            "Token de API de Apify",
            value=config["apify_token"],
            type="password",
            help="Obtén tu token en https://console.apify.com/account/integrations",
            key="apify_token_input"
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Guardar Token", key="save_apify_token"):
                set_apify_token(apify_token)
                st.success("✅ Token guardado correctamente")
        
        # Show usage info if token is configured
        if apify_token:
            try:
                from scraper import ApifyScraper
                scraper = ApifyScraper()
                usage_info = scraper.get_usage_info()
                
                if usage_info:
                    st.markdown("---")
                    st.markdown("#### 📊 Información de Uso de Apify")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Usuario:** {usage_info.get('username', 'N/A')}")
                    with col2:
                        st.info(f"**Plan:** {usage_info.get('plan', 'N/A')}")
                    
                    # Show link to usage dashboard
                    st.markdown("")
                    st.markdown(f"🔗 [Ver uso detallado en Apify Console]({usage_info.get('usage_url', 'https://console.apify.com/account/usage')})")
                    st.markdown("")
                    st.markdown("💡 **Nota:** El consumo detallado (tokens usados, límites, etc.) se muestra en el dashboard de Apify. Revisa regularmente para saber cuándo necesitas actualizar tu plan o token.")
            except Exception as e:
                st.warning(f"⚠️ No se pudo obtener información de uso: {str(e)}")
        
        st.markdown("---")
        
        # Actor IDs
        st.markdown("#### 🎭 IDs de Actores de Apify")
        st.markdown("Configura los IDs de los actores de Apify para cada plataforma.")
        
        platforms = ["instagram", "tiktok", "facebook"]
        actor_types = ["posts", "comments"]
        
        for platform in platforms:
            st.markdown(f"**{platform.upper()}**")
            cols = st.columns(2)
            for idx, actor_type in enumerate(actor_types):
                with cols[idx]:
                    current_id = get_actor_id(platform, actor_type)
                    new_id = st.text_input(
                        f"{actor_type.capitalize()} Actor ID",
                        value=current_id,
                        key=f"actor_{platform}_{actor_type}",
                        help=f"Actor ID para {platform} {actor_type}"
                    )
                    if st.button(f"💾 Guardar", key=f"save_{platform}_{actor_type}"):
                        set_actor_id(platform, actor_type, new_id)
                        st.success(f"✅ Actor ID guardado para {platform} {actor_type}")
    
    with tab2:
        st.subheader("🤖 Configuración de Análisis de Sentimiento")
        
        # HuggingFace Model
        st.markdown("#### Modelo de Sentimiento (HuggingFace)")
        hf_model = st.text_input(
            "Modelo de HuggingFace",
            value=config["huggingface_model"],
            help="Ejemplo: cardiffnlp/twitter-xlm-roberta-base-sentiment",
            key="hf_model_input"
        )
        if st.button("💾 Guardar Modelo", key="save_hf_model"):
            set_huggingface_model(hf_model)
            reload_analyzer()
            st.success("✅ Modelo guardado. El analizador se recargará automáticamente.")
        
        st.markdown("---")
        
        # Keywords
        st.markdown("#### Palabras Clave para Sentimiento")
        st.markdown("Estas palabras se usan junto con el modelo de IA para determinar el sentimiento.")
        
        # Positive keywords
        st.markdown("##### ✅ Palabras Clave Positivas")
        pos_keywords = config["keywords_positive"].copy()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_pos_keyword = st.text_input("Nueva palabra positiva", key="new_pos")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Agregar", key="add_pos"):
                if new_pos_keyword and new_pos_keyword.strip():
                    pos_keywords.append(new_pos_keyword.strip().lower())
                    set_keywords_positive(pos_keywords)
                    st.success(f"✅ Agregada: {new_pos_keyword}")
                    st.rerun()
        
        # Display and delete positive keywords
        if pos_keywords:
            st.markdown("**Palabras actuales:**")
            cols = st.columns(min(4, len(pos_keywords)))
            for idx, keyword in enumerate(pos_keywords):
                with cols[idx % len(cols)]:
                    if st.button(f"🗑️ {keyword}", key=f"del_pos_{idx}"):
                        pos_keywords.remove(keyword)
                        set_keywords_positive(pos_keywords)
                        st.success(f"✅ Eliminada: {keyword}")
                        st.rerun()
        else:
            st.info("No hay palabras clave positivas configuradas.")
        
        st.markdown("---")
        
        # Negative keywords
        st.markdown("##### ❌ Palabras Clave Negativas")
        neg_keywords = config["keywords_negative"].copy()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_neg_keyword = st.text_input("Nueva palabra negativa", key="new_neg")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Agregar", key="add_neg"):
                if new_neg_keyword and new_neg_keyword.strip():
                    neg_keywords.append(new_neg_keyword.strip().lower())
                    set_keywords_negative(neg_keywords)
                    st.success(f"✅ Agregada: {new_neg_keyword}")
                    st.rerun()
        
        # Display and delete negative keywords
        if neg_keywords:
            st.markdown("**Palabras actuales:**")
            cols = st.columns(min(4, len(neg_keywords)))
            for idx, keyword in enumerate(neg_keywords):
                with cols[idx % len(cols)]:
                    if st.button(f"🗑️ {keyword}", key=f"del_neg_{idx}"):
                        neg_keywords.remove(keyword)
                        set_keywords_negative(neg_keywords)
                        st.success(f"✅ Eliminada: {keyword}")
                        st.rerun()
        else:
            st.info("No hay palabras clave negativas configuradas.")
    
    with tab3:
        st.subheader("📊 Límites por Defecto")
        st.markdown("Configura los límites por defecto para el scraping.")
        
        col1, col2 = st.columns(2)
        with col1:
            limit_posts = st.number_input(
                "Límite de Posts",
                min_value=1,
                max_value=1000,
                value=config["default_limit_posts"],
                key="limit_posts",
                help="Número máximo de posts a analizar por perfil"
            )
            if st.button("💾 Guardar Límite Posts", key="save_limit_posts"):
                set_default_limit_posts(int(limit_posts))
                st.success("✅ Límite de posts guardado")
        
        with col2:
            limit_comments = st.number_input(
                "Límite de Comentarios por Post",
                min_value=1,
                max_value=1000,
                value=config["default_limit_comments"],
                key="limit_comments",
                help="Número máximo de comentarios a analizar por post"
            )
            if st.button("💾 Guardar Límite Comentarios", key="save_limit_comments"):
                set_default_limit_comments(int(limit_comments))
                st.success("✅ Límite de comentarios guardado")
        
        st.markdown("---")
        
        # Auto-skip option
        st.markdown("#### ⏭️ Opciones de Análisis")
        auto_skip = st.checkbox(
            "Saltar perfiles analizados recientemente (últimos 7 días)",
            value=config["auto_skip_recent"],
            help="Si está activado, los perfiles analizados en los últimos 7 días se saltarán automáticamente"
        )
        if st.button("💾 Guardar Opción", key="save_auto_skip"):
            set_auto_skip_recent(auto_skip)
            st.success("✅ Opción guardada")
    
    with tab4:
        st.subheader("📅 Filtros de Fecha para TikTok")
        st.markdown("Configura el rango de fechas para analizar videos de TikTok.")
        
        # Option 1: Last N days
        st.markdown("#### Opción 1: Últimos N días")
        last_days = st.number_input(
            "Analizar posts de los últimos N días (0 = sin filtro)",
            min_value=0,
            max_value=365,
            value=config.get("last_days", 7),
            key="last_days",
            help="Si configuras 7, solo analizará posts de los últimos 7 días"
        )
        if st.button("💾 Guardar Días", key="save_last_days"):
            days_value = int(last_days)
            set_last_days(days_value)
            saved_value = get_last_days()
            if saved_value == days_value:
                st.success(f"✅ Configurado para analizar últimos {last_days} días" if last_days > 0 else "✅ Filtro de días desactivado")
            else:
                st.error(f"⚠️ Error: Se intentó guardar {days_value} pero se leyó {saved_value}. Por favor, intenta de nuevo.")
        
        st.markdown("---")
        
        # Option 2: Date range
        st.markdown("#### Opción 2: Rango de fechas específico")
        st.markdown("**O** configura un rango de fechas específico:")
        
        col1, col2 = st.columns(2)
        with col1:
            date_from_str = config.get("date_from")
            try:
                date_from_default = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else None
            except:
                date_from_default = None
            date_from = st.date_input(
                "Fecha desde (opcional)",
                value=date_from_default,
                key="date_from",
                help="Fecha de inicio del análisis"
            )
        with col2:
            date_to_str = config.get("date_to")
            try:
                date_to_default = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else None
            except:
                date_to_default = None
            date_to = st.date_input(
                "Fecha hasta (opcional)",
                value=date_to_default,
                key="date_to",
                help="Fecha de fin del análisis"
            )
        
        if st.button("💾 Guardar Rango de Fechas", key="save_dates"):
            date_from_val = date_from.strftime("%Y-%m-%d") if date_from else None
            date_to_val = date_to.strftime("%Y-%m-%d") if date_to else None
            set_date_from(date_from_val)
            set_date_to(date_to_val)
            st.success("✅ Rango de fechas guardado")
        
        st.info("💡 **Nota:** Si configuras 'últimos N días', ese filtro tiene prioridad sobre el rango de fechas específico.")


def show_profiles():
    """Profiles management page."""
    st.title("👥 Perfiles")
    
    # Add new profile
    st.subheader("➕ Agregar Nuevo Perfil")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        profile_input = st.text_input(
            "URL o @username",
            placeholder="Ej: @username o https://instagram.com/username",
            key="new_profile_input"
        )
    with col2:
        platform = st.selectbox(
            "Plataforma",
            ["instagram", "tiktok", "facebook"],
            key="new_profile_platform"
        )
    
        if st.button("➕ Agregar Perfil", key="add_profile_btn", width='stretch'):
            if profile_input:
                username, detected_platform = normalize_username_or_url(profile_input)
                if not detected_platform:
                    detected_platform = platform
                
                try:
                    profile_id = add_profile(detected_platform, username)
                    st.success(f"✅ Perfil agregado: {username} ({detected_platform})")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al agregar perfil: {e}")
            else:
                st.warning("⚠️ Por favor ingresa una URL o username")
    
    st.markdown("---")
    
    # List existing profiles with better cards
    st.markdown("## 📋 Perfiles Guardados")
    profiles = get_all_profiles()
    
    if not profiles:
        st.info("ℹ️ No hay perfiles guardados. Agrega uno arriba para comenzar.")
    else:
        # Group by platform
        platforms = {}
        for profile in profiles:
            platform = profile['platform'].lower()
            if platform not in platforms:
                platforms[platform] = []
            platforms[platform].append(profile)
        
        # Display by platform
        for platform, platform_profiles in platforms.items():
            platform_emoji = {"facebook": "📘", "instagram": "📷", "tiktok": "🎵"}.get(platform, "📱")
            st.markdown(f"### {platform_emoji} {platform.upper()} ({len(platform_profiles)} perfil{'es' if len(platform_profiles) > 1 else ''})")
            
            # Display profiles in a grid
            cols = st.columns(min(3, len(platform_profiles)))
            for idx, profile in enumerate(platform_profiles):
                with cols[idx % len(cols)]:
                    with st.container():
                        st.markdown(f"""
                        <div style='padding: 1rem; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 1rem; background: #f8f9fa;'>
                            <h4 style='margin: 0; color: #2c3e50;'>{profile['username_or_url']}</h4>
                            <p style='margin: 0.5rem 0; color: #7f8c8d; font-size: 0.9rem;'>
                                <strong>Plataforma:</strong> {profile['platform']}<br>
                                <strong>Último análisis:</strong> {profile['last_analyzed'][:10] if profile['last_analyzed'] else 'Nunca'}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("🗑️ Eliminar", key=f"delete_{profile['id']}", width='stretch'):
                            if delete_profile(profile['id']):
                                st.success(f"✅ Perfil eliminado: {profile['username_or_url']}")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar perfil")
            
            st.markdown("---")


def show_analysis():
    """Analysis execution page."""
    st.title("🔄 Análisis")
    
    profiles = get_all_profiles()
    
    if not profiles:
        st.warning("⚠️ No hay perfiles configurados. Ve a la página 'Perfiles' para agregar algunos.")
        return
    
    st.subheader("Seleccionar Perfiles para Analizar")
    
    # Profile selection checkboxes
    selected_profiles = []
    for profile in profiles:
        if st.checkbox(
            f"{profile['username_or_url']} ({profile['platform']})",
            key=f"select_{profile['id']}"
        ):
            selected_profiles.append(profile['id'])
    
    if not selected_profiles:
        st.info("Selecciona al menos un perfil para analizar.")
        return
    
    st.markdown("---")
    
    # Analysis options
    col1, col2 = st.columns(2)
    with col1:
        force_analysis = st.checkbox(
            "Forzar análisis (ignorar fecha de último análisis)",
            value=False
        )
    
    with col2:
        st.markdown("")
        st.markdown("")
    
    # Run analysis button
    if st.button("🚀 Correr Análisis Fresco", type="primary", width='stretch'):
        if not get_apify_token():
            st.error("❌ Token de Apify no configurado. Ve a 'Configuración' para configurarlo.")
            return
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("Iniciando análisis...")
            progress_bar.progress(10)
            
            results = analyze_profiles(selected_profiles, force=force_analysis)
            progress_bar.progress(50)
            
            status_text.text("Procesando resultados...")
            progress_bar.progress(90)
            
            # Display results with better cards
            st.markdown("### 📊 Resultados del Análisis")
            
            for profile_id, result in results.items():
                profile = next((p for p in profiles if p['id'] == profile_id), None)
                if not profile:
                    continue
                
                platform_emoji = {"facebook": "📘", "instagram": "📷", "tiktok": "🎵"}.get(profile['platform'].lower(), "📱")
                
                with st.expander(f"{platform_emoji} {profile['username_or_url']} ({profile['platform']})", expanded=True):
                    if "error" in result:
                        st.error(f"❌ **Error:** {result['error']}")
                    elif result.get("skipped"):
                        st.info(f"⏭️ **Saltado:** {result.get('reason', 'unknown')}")
                    else:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("📝 Posts Analizados", result.get('posts_scraped', 0))
                        with col2:
                            st.metric("💬 Comentarios Analizados", result.get('comments_scraped', 0))
                        
                        if result.get('errors'):
                            st.warning(f"⚠️ **Errores encontrados:** {len(result['errors'])}")
                            with st.expander("Ver detalles de errores"):
                                for error in result['errors']:
                                    st.caption(f"  • {error}")
            
            progress_bar.progress(100)
            status_text.text("✅ Análisis completado!")
            st.success("🎉 Análisis completado exitosamente!")
            
        except Exception as e:
            st.error(f"❌ Error durante el análisis: {e}")
            logger.error(f"Analysis error: {e}", exc_info=True)
        finally:
            progress_bar.empty()
    
    st.markdown("---")
    st.subheader("📅 Actualización Semanal Automática")
    st.info("""
    Para configurar actualizaciones automáticas semanales, puedes usar un cron job o tarea programada:
    
    **Linux/Mac (cron):**
    ```bash
    0 0 * * 0 cd /ruta/al/proyecto && streamlit run app.py --server.headless true
    ```
    
    **Windows (Task Scheduler):**
    - Crea una tarea programada que ejecute: `streamlit run app.py`
    - Configura para ejecutarse semanalmente
    
    **Nota:** Asegúrate de que el análisis se ejecute en modo headless o automatizado.
    """)


def show_dashboard():
    """Main dashboard with metrics and visualizations."""
    # Header with better styling
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("📊 Dashboard de Análisis")
        st.markdown("Visualiza métricas y estadísticas de tus redes sociales")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Actualizar Datos", width='stretch'):
            st.rerun()
    
    profiles = get_all_profiles()
    
    if not profiles:
        st.warning("⚠️ No hay perfiles configurados. Ve a 'Perfiles' para agregar algunos y luego a 'Análisis' para procesarlos.")
        return
    
    # Filters in sidebar with better organization
    st.sidebar.markdown("### 🔍 Filtros de Visualización")
    
    # Platform filter
    platforms = ["Todos"] + list(set(p["platform"] for p in profiles))
    selected_platform = st.sidebar.selectbox("Plataforma", platforms)
    platform_filter = None if selected_platform == "Todos" else selected_platform
    
    # Profile filter
    profile_options = ["Todos"] + [f"{p['username_or_url']} ({p['platform']})" for p in profiles]
    selected_profile = st.sidebar.selectbox("Perfil", profile_options)
    profile_filter = None
    if selected_profile != "Todos":
        profile_name = selected_profile.split(" (")[0]
        profile = next((p for p in profiles if p['username_or_url'] == profile_name), None)
        if profile:
            profile_filter = profile['id']
    
    # Date range filter
    date_range = st.sidebar.date_input(
        "Rango de Fechas",
        value=(datetime.now() - timedelta(days=30), datetime.now()),
        key="date_range"
    )
    date_from = datetime.combine(date_range[0], datetime.min.time()) if len(date_range) > 0 else None
    date_to = datetime.combine(date_range[1], datetime.max.time()) if len(date_range) > 1 else None
    
    # Min interactions filter
    min_interactions = st.sidebar.number_input(
        "Interacciones Mínimas",
        min_value=0,
        value=0,
        key="min_interactions"
    )
    
    # Get filtered data
    posts = get_posts_for_dashboard(
        platform=platform_filter,
        profile_id=profile_filter,
        min_interactions=min_interactions,
        date_from=date_from,
        date_to=date_to
    )
    
    if not posts:
        st.info("No hay datos para mostrar con los filtros seleccionados.")
        return
    
    # Convert to DataFrame
    df_posts = pd.DataFrame(posts)
    
    # Metrics with better styling
    st.markdown("### 📈 Métricas Generales")
    
    # Calculate metrics
    total_interactions = df_posts['interactions_total'].sum()
    avg_interactions = df_posts['interactions_total'].mean()
    platforms_count = df_posts['platform'].nunique()
    total_comments = get_sentiment_stats(profile_id=profile_filter, platform=platform_filter)['total']
    
    # Display metrics in cards
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📝 Total Posts", len(df_posts), help="Número total de posts analizados")
    with col2:
        st.metric("💬 Total Comentarios", total_comments, help="Número total de comentarios analizados")
    with col3:
        st.metric("🔥 Total Interacciones", f"{total_interactions:,}", help="Suma de todas las interacciones (likes, comentarios, shares)")
    with col4:
        st.metric("📊 Promedio", f"{avg_interactions:.0f}", help="Promedio de interacciones por post")
    with col5:
        st.metric("📱 Plataformas", platforms_count, help="Número de plataformas diferentes")
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Interacciones por Plataforma")
        platform_interactions = df_posts.groupby('platform')['interactions_total'].sum().reset_index()
        fig_platform = px.bar(
            platform_interactions,
            x='platform',
            y='interactions_total',
            labels={'platform': 'Plataforma', 'interactions_total': 'Interacciones Totales'},
            color='platform'
        )
        st.plotly_chart(fig_platform, width='stretch')
    
    with col2:
        st.subheader("📈 Evolución Temporal")
        if 'posted_at' in df_posts.columns and df_posts['posted_at'].notna().any():
            df_posts['posted_at'] = pd.to_datetime(df_posts['posted_at'], errors='coerce')
            df_temporal = df_posts.groupby(df_posts['posted_at'].dt.date)['interactions_total'].sum().reset_index()
            df_temporal.columns = ['fecha', 'interacciones']
            fig_temporal = px.line(
                df_temporal,
                x='fecha',
                y='interacciones',
                labels={'fecha': 'Fecha', 'interacciones': 'Interacciones'},
                markers=True
            )
            st.plotly_chart(fig_temporal, width='stretch')
        else:
            st.info("No hay datos de fechas disponibles.")
    
    # Sentiment analysis
    st.subheader("😊 Análisis de Sentimiento")
    
    sentiment_stats = get_sentiment_stats(
        profile_id=profile_filter,
        platform=platform_filter
    )
    
    if sentiment_stats['total'] > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie chart
            sentiment_df = pd.DataFrame({
                'Sentimiento': list(sentiment_stats['counts'].keys()),
                'Cantidad': list(sentiment_stats['counts'].values())
            })
            fig_sentiment = px.pie(
                sentiment_df,
                values='Cantidad',
                names='Sentimiento',
                title="Distribución de Sentimiento",
                color='Sentimiento',
                color_discrete_map={
                    'POSITIVE': 'green',
                    'NEGATIVE': 'red',
                    'NEUTRAL': 'gray'
                }
            )
            st.plotly_chart(fig_sentiment, width='stretch')
        
        with col2:
            # Percentages
            st.markdown("### Porcentajes")
            for label, pct in sentiment_stats['percentages'].items():
                st.metric(
                    label,
                    f"{pct:.1f}%",
                    delta=f"{sentiment_stats['counts'][label]} comentarios"
                )
    else:
        st.info("No hay datos de sentimiento disponibles. Ejecuta un análisis primero.")
    
    st.markdown("---")
    
    # Top Posts Table
    st.subheader("🏆 Top Posts")
    
    top_posts = df_posts.nlargest(10, 'interactions_total')[
        ['username_or_url', 'platform', 'text', 'likes', 'comments_count', 'shares', 'interactions_total', 'posted_at']
    ]
    
    # Truncate text for display
    top_posts['text'] = top_posts['text'].apply(
        lambda x: (x[:100] + '...') if x and len(str(x)) > 100 else x
    )
    
    st.dataframe(
        top_posts,
        width='stretch',
        hide_index=True
    )
    
    # Comments table
    st.markdown("---")
    st.subheader("💬 Comentarios")
    
    # Comment filters
    comment_sentiment = st.selectbox(
        "Filtrar por Sentimiento",
        ["Todos", "POSITIVE", "NEGATIVE", "NEUTRAL"],
        key="comment_sentiment_filter"
    )
    
    min_comment_likes = st.number_input(
        "Likes Mínimos",
        min_value=0,
        value=0,
        key="min_comment_likes"
    )
    
    # Get comments
    comments = get_comments_for_dashboard(
        post_id=None,
        sentiment_label=None if comment_sentiment == "Todos" else comment_sentiment,
        min_likes=min_comment_likes
    )
    
    if comments:
        df_comments = pd.DataFrame(comments)
        
        # Filter by selected post if needed
        if profile_filter:
            # Get post IDs for selected profile
            post_ids_for_profile = [p['id'] for p in posts if p.get('profile_id') == profile_filter]
            df_comments = df_comments[df_comments['post_id'].isin(post_ids_for_profile)]
        
        # Display table
        display_cols = ['text', 'author', 'likes', 'sentiment_label', 'sentiment_score', 'posted_at']
        df_display = df_comments[display_cols].copy()
        df_display['text'] = df_display['text'].apply(
            lambda x: (x[:150] + '...') if x and len(str(x)) > 150 else x
        )
        
        st.dataframe(df_display, width='stretch', hide_index=True)
        
        # Export button
        csv = df_comments.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Comentarios (CSV)",
            data=csv,
            file_name=f"comments_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No hay comentarios para mostrar con los filtros seleccionados.")


if __name__ == "__main__":
    main()
