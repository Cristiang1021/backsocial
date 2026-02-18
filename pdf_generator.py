"""
Generador de PDF profesional para reportes de análisis de redes sociales.
Crea reportes con diseño similar al dashboard mostrado.
"""
import io
from datetime import datetime
from typing import Dict, List, Optional, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_agg import FigureCanvasAgg
import logging

logger = logging.getLogger(__name__)

# Colores del dashboard (como strings para matplotlib y objetos HexColor para reportlab)
COLOR_PRIMARY_HEX = '#1E88E5'  # Azul principal
COLOR_SUCCESS_HEX = '#4CAF50'  # Verde
COLOR_WARNING_HEX = '#FFC107'  # Amarillo
COLOR_DANGER_HEX = '#F44336'   # Rojo
COLOR_NEUTRAL_HEX = '#9E9E9E'  # Gris
COLOR_BG_HEX = '#F5F5F5'      # Fondo gris claro
COLOR_TEXT_HEX = '#212121'    # Texto oscuro
COLOR_HEADER_HEX = '#1976D2'  # Azul header

# Objetos HexColor para reportlab
COLOR_PRIMARY = HexColor(COLOR_PRIMARY_HEX)
COLOR_SUCCESS = HexColor(COLOR_SUCCESS_HEX)
COLOR_WARNING = HexColor(COLOR_WARNING_HEX)
COLOR_DANGER = HexColor(COLOR_DANGER_HEX)
COLOR_NEUTRAL = HexColor(COLOR_NEUTRAL_HEX)
COLOR_BG = HexColor(COLOR_BG_HEX)
COLOR_TEXT = HexColor(COLOR_TEXT_HEX)
COLOR_HEADER = HexColor(COLOR_HEADER_HEX)


class PDFGenerator:
    """Generador de PDF profesional para reportes de análisis."""
    
    def __init__(self, buffer: io.BytesIO):
        self.buffer = buffer
        # Usar formato horizontal (landscape)
        self.doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.story = []
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados."""
        # Título principal
        if 'CustomTitle' not in self.styles.byName:
            self.styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                textColor=COLOR_HEADER,
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            ))
        
        # Subtítulo
        if 'CustomSubtitle' not in self.styles.byName:
            self.styles.add(ParagraphStyle(
                name='CustomSubtitle',
                parent=self.styles['Heading2'],
                fontSize=18,
                textColor=COLOR_PRIMARY,
                spaceAfter=20,
                spaceBefore=20,
                fontName='Helvetica-Bold'
            ))
        
        # Sección
        if 'Section' not in self.styles.byName:
            self.styles.add(ParagraphStyle(
                name='Section',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=COLOR_TEXT,
                spaceAfter=12,
                spaceBefore=12,
                fontName='Helvetica-Bold'
            ))
        
        # Texto normal personalizado (usar nombre único)
        if 'CustomBodyText' not in self.styles.byName:
            self.styles.add(ParagraphStyle(
                name='CustomBodyText',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=COLOR_TEXT,
                spaceAfter=6,
                alignment=TA_JUSTIFY
            ))
        
        # Texto destacado
        if 'Highlight' not in self.styles.byName:
            self.styles.add(ParagraphStyle(
                name='Highlight',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=COLOR_PRIMARY,
                fontName='Helvetica-Bold'
            ))
    
    def _header_footer(self, canvas_obj, doc):
        """Agrega header y footer a cada página."""
        # Header
        canvas_obj.saveState()
        canvas_obj.setFillColor(COLOR_HEADER)
        canvas_obj.rect(0, doc.height + doc.topMargin, doc.width + doc.leftMargin + doc.rightMargin, 0.5*inch, fill=1)
        
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 12)
        canvas_obj.drawString(doc.leftMargin, doc.height + doc.topMargin + 0.15*inch, 
                            "DASHBOARD DE GESTIÓN ESTRATÉGICA DE COMUNICACIÓN")
        
        # Footer
        canvas_obj.setFillColor(COLOR_NEUTRAL)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(doc.leftMargin, 0.3*inch, 
                            f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        canvas_obj.drawRightString(doc.width + doc.leftMargin, 0.3*inch, 
                                  f"Página {canvas_obj.getPageNumber()}")
        canvas_obj.restoreState()
    
    def add_title(self, title: str, subtitle: Optional[str] = None):
        """Agrega título al documento."""
        self.story.append(Paragraph(title, self.styles['CustomTitle']))
        if subtitle:
            self.story.append(Paragraph(subtitle, self.styles['CustomSubtitle']))
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_section(self, title: str):
        """Agrega una nueva sección."""
        self.story.append(Spacer(1, 0.2*inch))
        self.story.append(Paragraph(title, self.styles['Section']))
        self.story.append(Spacer(1, 0.1*inch))
    
    def add_metric_card(self, title: str, value: str, subtitle: Optional[str] = None, color = None):
        """Agrega una tarjeta de métrica."""
        if color is None:
            color = COLOR_PRIMARY
        # Asegurar que color sea un objeto de color válido
        if isinstance(color, str):
            try:
                color = HexColor(color)
            except:
                color = COLOR_PRIMARY
        
        data = [[title, value]]
        if subtitle:
            data.append(['', subtitle])
        
        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG),
            ('TEXTCOLOR', (0, 0), (0, -1), COLOR_TEXT),
            ('TEXTCOLOR', (1, 0), (1, -1), color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTSIZE', (1, 0), (1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.1*inch))
    
    def add_sentiment_pie_data(self, stats: Dict[str, Any]):
        """Agrega datos de sentimiento en formato tabla."""
        counts = stats.get('counts', {})
        percentages = stats.get('percentages', {})
        total = stats.get('total', 0)
        
        data = [
            ['Sentimiento', 'Cantidad', 'Porcentaje']
        ]
        
        # Orden: Positivo, Neutral, Negativo
        for sentiment in ['POSITIVE', 'NEUTRAL', 'NEGATIVE']:
            count = counts.get(sentiment, 0)
            pct = percentages.get(sentiment, 0)
            color = COLOR_SUCCESS if sentiment == 'POSITIVE' else (COLOR_WARNING if sentiment == 'NEUTRAL' else COLOR_DANGER)
            
            data.append([
                sentiment.capitalize(),
                str(count),
                f"{pct:.1f}%"
            ])
        
        data.append(['TOTAL', str(total), '100%'])
        
        table = Table(data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (0, 1), COLOR_SUCCESS),
            ('BACKGROUND', (0, 2), (0, 2), COLOR_WARNING),
            ('BACKGROUND', (0, 3), (0, 3), COLOR_DANGER),
            ('TEXTCOLOR', (0, 1), (0, 3), colors.white),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_top_complaints_by_topic(self, complaints: List[Dict[str, Any]]):
        """Agrega sección de TOP 5 RECLAMOS agrupados por tema con formato profesional."""
        if not complaints:
            self.story.append(Paragraph("No se encontraron reclamos categorizados.", self.styles['CustomBodyText']))
            return
        
        # Crear tabla profesional para TOP 5 RECLAMOS
        data = [['#', 'Temática', 'Palabras Clave', 'Cantidad']]
        
        for idx, complaint in enumerate(complaints[:5], 1):
            topic = complaint.get('topic', 'Sin categoría')
            count = complaint.get('count', 0)
            keywords = complaint.get('keywords', [])
            
            # Formatear palabras clave
            keywords_text = ", ".join([f'"{kw}"' for kw in keywords[:5]]) if keywords else "N/A"
            
            data.append([
                str(idx),
                topic,
                keywords_text[:80] + ('...' if len(keywords_text) > 80 else ''),  # Limitar longitud
                f"{count} comentarios"
            ])
        
        # Crear tabla con mejor diseño
        table = Table(data, colWidths=[0.5*inch, 2.5*inch, 4*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG]),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_most_repeated_comments(self, comments: List[Dict[str, Any]]):
        """Agrega tabla de comentarios más repetidos."""
        if not comments:
            self.story.append(Paragraph("No se encontraron comentarios repetidos.", self.styles['CustomBodyText']))
            return
        
        data = [['#', 'Comentario', 'Repeticiones', 'Likes Totales', 'Sentimiento']]
        
        for idx, comment in enumerate(comments[:10], 1):
            text = comment.get('text', '')[:100] + ('...' if len(comment.get('text', '')) > 100 else '')
            count = comment.get('count', 0)
            total_likes = comment.get('total_likes', 0)
            sentiment = comment.get('most_common_sentiment', 'N/A')
            
            # Color según sentimiento
            sentiment_color = COLOR_SUCCESS if sentiment == 'POSITIVE' else (
                COLOR_WARNING if sentiment == 'NEUTRAL' else COLOR_DANGER
            )
            
            data.append([
                str(idx),
                text,
                str(count),
                str(total_likes),
                sentiment or 'N/A'
            ])
        
        table = Table(data, colWidths=[0.4*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (4, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG]),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_platform_stats(self, platforms: Dict[str, Dict[str, Any]]):
        """Agrega estadísticas por plataforma."""
        if not platforms:
            return
        
        data = [['Plataforma', 'Posts', 'Comentarios', 'Sentimiento Positivo', 'Sentimiento Negativo']]
        
        for platform_name, stats in platforms.items():
            posts = stats.get('posts', 0)
            comments = stats.get('comments', 0)
            sentiment = stats.get('sentiment', {})
            pos_pct = sentiment.get('POSITIVE', 0) if isinstance(sentiment, dict) else 0
            neg_pct = sentiment.get('NEGATIVE', 0) if isinstance(sentiment, dict) else 0
            
            data.append([
                platform_name.upper(),
                str(posts),
                str(comments),
                f"{pos_pct:.1f}%" if isinstance(pos_pct, (int, float)) else str(pos_pct),
                f"{neg_pct:.1f}%" if isinstance(neg_pct, (int, float)) else str(neg_pct)
            ])
        
        table = Table(data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG]),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_summary_text(self, text: str):
        """Agrega texto de resumen."""
        self.story.append(Paragraph(text, self.styles['CustomBodyText']))
        self.story.append(Spacer(1, 0.1*inch))
    
    def add_pie_chart(self, data: Dict[str, float], title: str, width: float = 5*inch, height: float = 4*inch):
        """Agrega un gráfico de pastel al PDF."""
        try:
            fig, ax = plt.subplots(figsize=(width/72, height/72))
            
            # Preparar datos
            labels = list(data.keys())
            sizes = list(data.values())
            colors_list = [COLOR_SUCCESS_HEX, COLOR_WARNING_HEX, COLOR_DANGER_HEX, COLOR_PRIMARY_HEX, COLOR_NEUTRAL_HEX]
            
            # Crear gráfico de pastel con mejor diseño
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%',
                colors=colors_list[:len(labels)],
                startangle=90,
                textprops={'fontsize': 11, 'color': 'white', 'weight': 'bold'},
                explode=[0.05] * len(labels)  # Separar ligeramente las porciones
            )
            
            ax.set_title(title, fontsize=14, fontweight='bold', pad=15, color='#212121')
            plt.tight_layout()
            
            # Guardar en buffer
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
            img_buffer.seek(0)
            plt.close(fig)
            
            # Agregar imagen al PDF
            img = Image(img_buffer, width=width, height=height)
            self.story.append(img)
            self.story.append(Spacer(1, 0.2*inch))
        except Exception as e:
            logger.error(f"Error creando gráfico de pastel: {e}", exc_info=True)
            self.story.append(Paragraph(f"Error al generar gráfico: {title}", self.styles['CustomBodyText']))
    
    def add_bar_chart(self, data: Dict[str, float], title: str, xlabel: str = "", ylabel: str = "", width: float = 7*inch, height: float = 4*inch, colors_map: Optional[Dict[str, str]] = None):
        """Agrega un gráfico de barras al PDF."""
        try:
            fig, ax = plt.subplots(figsize=(width/72, height/72))
            
            categories = list(data.keys())
            values = list(data.values())
            
            # Usar colores personalizados si se proporcionan
            if colors_map:
                bar_colors = [colors_map.get(cat, COLOR_PRIMARY_HEX) for cat in categories]
            else:
                # Colores alternados para mejor visualización
                color_palette = [COLOR_PRIMARY_HEX, COLOR_SUCCESS_HEX, COLOR_WARNING_HEX, COLOR_DANGER_HEX, COLOR_NEUTRAL_HEX]
                bar_colors = [color_palette[i % len(color_palette)] for i in range(len(categories))]
            
            bars = ax.bar(categories, values, color=bar_colors, alpha=0.85, edgecolor='white', linewidth=1.5)
            
            # Agregar valores en las barras
            for bar in bars:
                height_val = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height_val,
                       f'{int(height_val)}',
                       ha='center', va='bottom', fontsize=10, fontweight='bold', color='#212121')
            
            ax.set_title(title, fontsize=14, fontweight='bold', pad=15, color='#212121')
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=11, fontweight='bold')
            if ylabel:
                ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
            
            # Mejorar diseño
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            plt.xticks(rotation=45, ha='right', fontsize=10)
            plt.yticks(fontsize=9)
            plt.tight_layout()
            
            # Guardar en buffer
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
            img_buffer.seek(0)
            plt.close(fig)
            
            # Agregar imagen al PDF
            img = Image(img_buffer, width=width, height=height)
            self.story.append(img)
            self.story.append(Spacer(1, 0.2*inch))
        except Exception as e:
            logger.error(f"Error creando gráfico de barras: {e}", exc_info=True)
            self.story.append(Paragraph(f"Error al generar gráfico: {title}", self.styles['CustomBodyText']))
    
    def build(self):
        """Construye el PDF."""
        self.doc.build(self.story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return self.buffer.getvalue()


def generate_professional_report(
    profile_name: str,
    sentiment_stats: Dict[str, Any],
    platform_stats: Dict[str, Dict[str, Any]],
    most_repeated_comments: List[Dict[str, Any]],
    total_posts: int = 0,
    total_comments: int = 0,
    date_range: Optional[str] = None,
    top_complaints: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Genera un reporte PDF profesional.
    
    Args:
        profile_name: Nombre del perfil analizado
        sentiment_stats: Estadísticas de sentimiento
        platform_stats: Estadísticas por plataforma
        most_repeated_comments: Lista de comentarios más repetidos
        total_posts: Total de posts
        total_comments: Total de comentarios
        date_range: Rango de fechas (opcional)
    
    Returns:
        bytes: Contenido del PDF
    """
    buffer = io.BytesIO()
    pdf = PDFGenerator(buffer)
    
    # Título
    pdf.add_title(
        f"DASHBOARD DE GESTIÓN ESTRATÉGICA DE COMUNICACIÓN",
        f"{profile_name.upper()}"
    )
    
    if date_range:
        pdf.add_summary_text(f"<b>Período de análisis:</b> {date_range}")
    
    # TERMÓMETRO POLÍTICO - PERCEPCIÓN CIUDADANA
    pdf.add_section("TERMÓMETRO POLÍTICO - PERCEPCIÓN CIUDADANA")
    
    percentages = sentiment_stats.get('percentages', {})
    pos_pct = percentages.get('POSITIVE', 0)
    neu_pct = percentages.get('NEUTRAL', 0)
    neg_pct = percentages.get('NEGATIVE', 0)
    
    pdf.add_summary_text(
        f"La percepción ciudadana muestra una distribución de sentimientos: "
        f"<b>{pos_pct:.1f}% Positivo</b>, <b>{neu_pct:.1f}% Neutral</b>, y <b>{neg_pct:.1f}% Negativo</b>."
    )
    
    # Gráfico de pastel de sentimiento (más grande)
    sentiment_data = {
        'Positivo': pos_pct,
        'Neutral': neu_pct,
        'Negativo': neg_pct
    }
    pdf.add_pie_chart(sentiment_data, "Distribución de Sentimiento de Comentarios", width=6*inch, height=5*inch)
    
    pdf.add_sentiment_pie_data(sentiment_stats)
    
    # Métricas generales
    pdf.add_section("MÉTRICAS GENERALES")
    
    pdf.add_metric_card("Total de Publicaciones", str(total_posts), "Posts analizados", COLOR_PRIMARY)
    pdf.add_metric_card("Total de Comentarios", str(total_comments), "Comentarios procesados", COLOR_PRIMARY)
    
    counts = sentiment_stats.get('counts', {})
    pdf.add_metric_card("Comentarios Positivos", str(counts.get('POSITIVE', 0)), 
                        f"{pos_pct:.1f}% del total", COLOR_SUCCESS)
    pdf.add_metric_card("Comentarios Negativos", str(counts.get('NEGATIVE', 0)), 
                        f"{neg_pct:.1f}% del total", COLOR_DANGER)
    
    # Estadísticas por plataforma
    if platform_stats:
        pdf.add_section("ESTADÍSTICAS POR PLATAFORMA")
        
        # Gráfico de barras por plataforma (más grande)
        platform_posts_data = {platform: stats.get('posts', 0) for platform, stats in platform_stats.items()}
        if platform_posts_data:
            pdf.add_bar_chart(
                platform_posts_data,
                "Publicaciones por Plataforma",
                xlabel="Plataforma",
                ylabel="Cantidad de Posts",
                width=7*inch,
                height=4*inch
            )
        
        pdf.add_platform_stats(platform_stats)
    
    # TOP 5 RECLAMOS (por tema)
    if top_complaints:
        pdf.add_section("TOP 5 RECLAMOS")
        pdf.add_summary_text(
            "Los siguientes temas son los más recurrentes en los comentarios de los ciudadanos, "
            "agrupados por categoría con sus palabras clave principales."
        )
        
        # Gráfico de barras de top complaints (más grande)
        complaints_data = {complaint['topic']: complaint['count'] for complaint in top_complaints[:5]}
        pdf.add_bar_chart(
            complaints_data, 
            "Top 5 Reclamos por Cantidad de Comentarios",
            xlabel="Categoría",
            ylabel="Cantidad de Comentarios",
            width=7.5*inch,
            height=4.5*inch
        )
        
        pdf.add_top_complaints_by_topic(top_complaints)
    
    # Comentarios más repetidos (si no hay temas categorizados)
    if not top_complaints or len(top_complaints) == 0:
        pdf.add_section("COMENTARIOS MÁS REPETIDOS")
        pdf.add_summary_text(
            "Los siguientes comentarios aparecen con mayor frecuencia en las publicaciones analizadas, "
            "lo que indica temas recurrentes en la conversación ciudadana."
        )
        pdf.add_most_repeated_comments(most_repeated_comments)
    
    # Resumen ejecutivo
    pdf.add_section("RESUMEN EJECUTIVO")
    
    # Determinar sentimiento predominante
    predominant = 'POSITIVE' if pos_pct > neg_pct else ('NEGATIVE' if neg_pct > pos_pct else 'NEUTRAL')
    predominant_text = 'positivo' if predominant == 'POSITIVE' else ('negativo' if predominant == 'NEGATIVE' else 'neutral')
    
    summary = f"""
    El análisis de {profile_name} muestra un total de <b>{total_posts} publicaciones</b> y 
    <b>{total_comments} comentarios</b> analizados. La percepción general es <b>{predominant_text}</b> 
    con un {percentages.get(predominant, 0):.1f}% de los comentarios.
    
    Los comentarios más repetidos reflejan los temas principales de conversación entre los ciudadanos, 
    proporcionando insights valiosos sobre las preocupaciones y opiniones de la comunidad.
    """
    
    pdf.add_summary_text(summary)
    
    # Generar PDF
    return pdf.build()
