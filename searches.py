"""
Bank of search queries grouped by topic category.
The autoclicker picks randomly from these to generate varied, natural-looking searches.
"""

import random

QUERIES: dict[str, list[str]] = {
    "noticias": [
        "últimas noticias de hoy",
        "noticias de economía mundial",
        "noticias política España",
        "resumen noticias internacionales",
        "noticias medioambiente hoy",
        "titulares periódicos hoy",
        "noticias salud últimas horas",
        "noticias ciencia descubrimientos recientes",
        "conflictos internacionales noticias",
        "noticias clima extremo 2025",
    ],
    "deportes": [
        "resultados fútbol hoy",
        "últimas noticias de fútbol",
        "clasificación liga española",
        "Champions League resultados",
        "NBA últimos partidos",
        "Fórmula 1 próxima carrera",
        "tenis Grand Slam resultados",
        "fichajes fútbol últimas noticias",
        "baloncesto europeo resultados",
        "atletismo record mundial",
    ],
    "tecnología": [
        "tendencias inteligencia artificial",
        "novedades smartphones 2025",
        "mejores laptops del año",
        "noticias ciberseguridad",
        "nuevas actualizaciones Windows",
        "ChatGPT últimas novedades",
        "coches eléctricos avances",
        "tecnología cuántica noticias",
        "metaverso últimas noticias",
        "redes sociales nuevas funciones",
        "satélites SpaceX lanzamiento",
        "videojuegos más vendidos",
    ],
    "cultura": [
        "películas estrenos cine 2025",
        "series populares streaming",
        "libros más vendidos 2025",
        "exposiciones arte Madrid",
        "música nueva lanzamientos",
        "festivales verano 2025",
        "historia curiosidades interesantes",
        "gastronomía recetas tendencias",
        "viajes destinos populares",
        "moda tendencias temporada",
    ],
    "ciencia": [
        "descubrimientos científicos recientes",
        "exploración espacial noticias",
        "cambio climático últimas investigaciones",
        "biología avances medicina",
        "física cuántica explicación",
        "paleontología nuevos fósiles",
        "astronomía planetas sistema solar",
        "ingeniería genética noticias",
        "oceanografía descubrimientos",
        "inteligencia artificial ética",
    ],
    "salud": [
        "dieta saludable consejos",
        "ejercicio físico beneficios",
        "meditación mindfulness técnicas",
        "enfermedades raras tratamientos",
        "vacunas novedades 2025",
        "salud mental consejos",
        "nutrición superalimentos",
        "dormir bien consejos",
        "diabetes tratamientos avances",
        "cáncer investigaciones recientes",
    ],
    "economia": [
        "bolsa de valores hoy",
        "precio Bitcoin 2025",
        "criptomonedas noticias",
        "inflación economía mundial",
        "empleo estadísticas España",
        "startup tecnología inversión",
        "banco central europeo decisiones",
        "precio petróleo hoy",
        "economía verde sostenibilidad",
        "finanzas personales consejos",
    ],
}

ALL_QUERIES: list[str] = [q for queries in QUERIES.values() for q in queries]


def get_random_query() -> str:
    """Return a single random search query from any category."""
    return random.choice(ALL_QUERIES)


def get_random_queries(n: int) -> list[str]:
    """
    Return *n* distinct random queries, cycling through categories so that
    topics are spread evenly across the session.
    """
    categories = list(QUERIES.keys())
    result: list[str] = []
    used: set[str] = set()

    for i in range(n):
        category = categories[i % len(categories)]
        pool = [q for q in QUERIES[category] if q not in used]
        if not pool:
            pool = [q for q in ALL_QUERIES if q not in used]
        if not pool:
            pool = ALL_QUERIES  # fallback: allow repeats only if exhausted
        query = random.choice(pool)
        used.add(query)
        result.append(query)

    random.shuffle(result)
    return result
