"""
Analizador de temas para agrupar comentarios por asuntos/categorías.
Extrae palabras clave y agrupa comentarios similares por tema.
"""
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)

# Palabras clave por categoría (pueden expandirse)
TOPIC_KEYWORDS = {
    "Vialidad Abandonada": [
        "primavera", "roca fuerte", "rocafuerte", "polvo", "cráter", "crater", "inconcluso",
        "obra", "asfalto", "bache", "bacheo", "calle", "avenida", "carretera", "vía", "via",
        "pavimento", "hueco", "huecos", "abandonado", "abandonada", "dejaron", "dejaron botada"
    ],
    "Movilidad y Tránsito": [
        "cierre", "cierres", "vías", "vias", "domingo", "agentes", "caos", "carreras",
        "tránsito", "transito", "tráfico", "trafico", "semáforo", "semaforo", "semáforos",
        "peatones", "peatonal", "vehículos", "vehiculos", "estacionamiento"
    ],
    "Mala Planificación": [
        "plaza", "rastro", "empiezan", "terminan", "terminan", "gallinas", "culecas",
        "planificación", "planificacion", "proyecto", "proyectos", "inconcluso", "inconclusa",
        "dejaron a medias", "no terminan", "empiezan y no terminan"
    ],
    "Transparencia": [
        "vacunadores", "robar", "impuestos", "reelección", "reeleccion", "corrupción",
        "corrupcion", "transparencia", "gobierno", "alcalde", "municipio", "dinero público",
        "dinero publico", "malversación", "malversacion"
    ],
    "Bienestar Animal": [
        "perros", "gatos", "animales", "callejeros", "callejeras", "machos", "hembras",
        "esterilización", "esterilizacion", "veterinaria", "adopción", "adopcion",
        "refugio", "abandono", "maltrato"
    ],
    "Servicios Públicos": [
        "agua", "luz", "electricidad", "basura", "recolección", "recoleccion", "limpieza",
        "alcantarillado", "drenaje", "alumbrado", "parques", "jardines"
    ],
    "Seguridad": [
        "delincuencia", "robos", "robos", "inseguridad", "policía", "policia", "patrullaje",
        "vigilancia", "cámaras", "camaras", "seguridad"
    ]
}

# Palabras comunes a ignorar (stop words en español)
STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "al",
    "en", "por", "para", "con", "sin", "sobre", "bajo", "entre", "hasta", "desde",
    "que", "cual", "cuales", "quien", "quienes", "donde", "cuando", "como", "porque",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella",
    "aquellos", "aquellas", "todo", "toda", "todos", "todas", "otro", "otra", "otros",
    "otras", "muy", "mucho", "mucha", "muchos", "muchas", "poco", "poca", "pocos",
    "pocas", "mas", "menos", "tan", "tanto", "tanta", "tantos", "tantas", "si", "no",
    "tambien", "también", "tampoco", "ya", "aun", "aún", "solo", "sólo", "solo",
    "siempre", "nunca", "ahora", "antes", "despues", "después", "hoy", "ayer", "mañana",
    "aqui", "aquí", "alli", "allí", "alla", "allá", "asi", "así", "bien", "mal", "mejor",
    "peor", "mas", "más", "menos", "muy", "tan", "tanto", "tanta", "tantos", "tantas"
}


def normalize_text(text: str) -> str:
    """Normaliza texto para comparación."""
    if not text:
        return ""
    # Convertir a minúsculas, remover acentos básicos, remover puntuación
    text = text.lower()
    # Remover acentos (básico)
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Remover puntuación
    text = re.sub(r'[^\w\s]', ' ', text)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_keywords(text: str, min_length: int = 4, max_words: int = 10) -> List[str]:
    """
    Extrae palabras clave significativas de un texto.
    Prioriza palabras más largas y relevantes, evitando palabras comunes.
    """
    if not text:
        return []
    
    normalized = normalize_text(text)
    words = normalized.split()
    
    # Filtrar stop words y palabras muy cortas
    keywords = [
        w for w in words
        if len(w) >= min_length and w not in STOP_WORDS
    ]
    
    # Priorizar palabras más largas (más específicas)
    # Calcular score: longitud * frecuencia
    word_scores = {}
    for word in keywords:
        if word not in word_scores:
            word_scores[word] = 0
        word_scores[word] += len(word)  # Peso por longitud
    
    # Ordenar por score (frecuencia * longitud)
    sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
    top_words = [word for word, score in sorted_words[:max_words]]
    
    return top_words


def classify_topic(text: str) -> Optional[str]:
    """Clasifica un comentario en una categoría de tema."""
    if not text:
        return None
    
    normalized = normalize_text(text)
    text_words = set(normalized.split())
    
    # Contar coincidencias por tema
    topic_scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            keyword_normalized = normalize_text(keyword)
            if keyword_normalized in normalized:
                # Peso mayor si la palabra clave completa está presente
                score += 2
            elif any(kw in normalized for kw in keyword_normalized.split()):
                # Peso menor si solo parte de la palabra clave está presente
                score += 1
        if score > 0:
            topic_scores[topic] = score
    
    if not topic_scores:
        return None
    
    # Retornar el tema con mayor puntuación
    return max(topic_scores.items(), key=lambda x: x[1])[0]


def group_comments_by_topic(comments: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Agrupa comentarios por tema/categoría.
    
    Args:
        comments: Lista de comentarios con al menos 'text'
    
    Returns:
        Diccionario con temas como keys y listas de comentarios como values
    """
    topics = defaultdict(list)
    
    for comment in comments:
        text = comment.get('text', '')
        if not text:
            continue
        
        topic = classify_topic(text)
        if topic:
            topics[topic].append(comment)
        else:
            # Si no se puede clasificar, poner en "Otros"
            topics["Otros"].append(comment)
    
    return dict(topics)


def get_top_complaints_by_topic(
    comments: List[Dict],
    top_n: int = 5
) -> List[Dict[str, any]]:
    """
    Obtiene los top N reclamos agrupados por tema con sus palabras clave.
    
    Args:
        comments: Lista de comentarios
        top_n: Número de temas a retornar
    
    Returns:
        Lista de diccionarios con:
        - topic: Nombre del tema
        - count: Número de comentarios en este tema
        - keywords: Lista de palabras clave más comunes
        - comments: Lista de comentarios (opcional, limitada)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Procesando {len(comments)} comentarios para análisis de temas...")
    
    # Agrupar por tema
    topics = group_comments_by_topic(comments)
    logger.info(f"Temas encontrados: {list(topics.keys())}")
    
    # Para cada tema, extraer palabras clave de todos los comentarios
    topic_data = []
    for topic, topic_comments in topics.items():
        if topic == "Otros" and len(topic_comments) < 3:
            # Ignorar "Otros" si tiene muy pocos comentarios
            continue
        
        logger.debug(f"Procesando tema '{topic}' con {len(topic_comments)} comentarios")
        
        # Extraer todas las palabras clave de los comentarios de este tema
        # Optimizar: procesar solo una muestra si hay muchos comentarios
        sample_size = min(500, len(topic_comments))  # Procesar máximo 500 comentarios por tema
        comments_sample = topic_comments[:sample_size] if len(topic_comments) > sample_size else topic_comments
        
        all_keywords = []
        for comment in comments_sample:
            keywords = extract_keywords(comment.get('text', ''), max_words=15)
            all_keywords.extend(keywords)
        
        # Obtener las palabras clave más comunes
        keyword_counts = Counter(all_keywords)
        top_keywords = [word for word, count in keyword_counts.most_common(10)]
        
        topic_data.append({
            "topic": topic,
            "count": len(topic_comments),  # Usar el count total, no solo la muestra
            "keywords": top_keywords[:5],  # Top 5 palabras clave
            "comments": topic_comments[:3]  # Primeros 3 comentarios como ejemplo
        })
    
    # Ordenar por cantidad de comentarios (descendente)
    topic_data.sort(key=lambda x: x["count"], reverse=True)
    
    logger.info(f"Retornando {len(topic_data[:top_n])} temas principales")
    
    return topic_data[:top_n]
