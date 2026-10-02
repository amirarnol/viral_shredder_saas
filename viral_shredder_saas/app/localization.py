"""Tone & target-language matrix for the content generators.

Every generated string the shredder emits lives here, in four languages and
three tones. The generators never hardcode prose - they ask `resolve()` for a
key and format it with the current selection.

Structure
---------
``L10N[language][key]``        the base, professional-voice string table
``TONE_OVERRIDES[tone][lang]`` optional rewrites of the high-impact voice keys
``resolve(key, lang, tone)``   tone layer wins over the base table

Tone is layered *on top of* language, so "viral + Arabic" is Arabic prose with
viral energy, not English fragments pasted into an Arabic article.

If a key is missing from a language table the English fallback is used, which
keeps the app from ever emitting an empty section.
"""

from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "en": "English",
    "ar": "العربية",
    "es": "Español",
    "fr": "Français",
}

# Used by the UI for the little badge next to a generated asset.
TONES: dict[str, dict[str, str]] = {
    "professional": {
        "label": "Professional",
        "blurb": "Measured, authoritative, quote-friendly.",
    },
    "viral": {
        "label": "Viral",
        "blurb": "Punchy, hook-first, built to be screenshotted.",
    },
    "storytelling": {
        "label": "Storytelling",
        "blurb": "Second-person, scene-setting, narrative pull.",
    },
}

DEFAULT_TONE = "professional"
DEFAULT_LANGUAGE = "en"

RTL_LANGUAGES = {"ar"}


# Topic niches come out of shredder.TOPIC_HASHTAGS in English. When a generator
# interpolates a niche into a non-English template, it is looked up here so the
# sentence stays fully in the target language. Unknown niches fall back to English.
NICHE_L10N: dict[str, dict[str, str]] = {
    "fitness": {"ar": "اللياقة", "es": "fitness", "fr": "fitness"},
    "marketing": {"ar": "التسويق", "es": "marketing", "fr": "marketing"},
    "artificial intelligence": {"ar": "الذكاء الاصطناعي", "es": "inteligencia artificial", "fr": "intelligence artificielle"},
    "technology": {"ar": "التكنولوجيا", "es": "tecnología", "fr": "technologie"},
    "programming": {"ar": "البرمجة", "es": "programación", "fr": "programmation"},
    "finance": {"ar": "التمويل", "es": "finanzas", "fr": "finance"},
    "cryptocurrency": {"ar": "العملات الرقمية", "es": "criptomonedas", "fr": "cryptomonnaie"},
    "business": {"ar": "ريادة الأعمال", "es": "negocios", "fr": "business"},
    "food": {"ar": "الطعام", "es": "gastronomía", "fr": "cuisine"},
    "travel": {"ar": "السفر", "es": "viajes", "fr": "voyage"},
    "fashion": {"ar": "الموضة", "es": "moda", "fr": "mode"},
    "beauty": {"ar": "الجمال", "es": "belleza", "fr": "beauté"},
    "gaming": {"ar": "الألعاب", "es": "videojuegos", "fr": "gaming"},
    "music": {"ar": "الموسيقى", "es": "música", "fr": "musique"},
    "education": {"ar": "التعليم", "es": "educación", "fr": "éducation"},
    "self-improvement": {"ar": "تطوير الذات", "es": "desarrollo personal", "fr": "développement personnel"},
    "health": {"ar": "الصحة", "es": "salud", "fr": "santé"},
    "short-form": {"ar": "القصير", "es": "formato corto", "fr": "au format court"},
}


def localize_niche(niche: str, language: str) -> str:
    """Translate a topic niche into the target language, English if unknown."""
    return NICHE_L10N.get(niche, {}).get(language, niche)


def headline_niche(niche: str, language: str) -> str:
    """Niche as it should appear inside a headline.

    English headlines use title case; Spanish and French keep sentence case,
    and Arabic has no case to change.
    """
    if language == "en":
        return niche.title()
    return niche.lower() if language in ("es", "fr") else niche


def is_rtl(language: str) -> bool:
    return language in RTL_LANGUAGES


# ---------------------------------------------------------------------------
# Base string tables (professional voice)
# ---------------------------------------------------------------------------
L10N: dict[str, dict[str, str]] = {
    "en": {
        "title_playbook": "The {niche} Playbook: Full Breakdown of This Viral Video",
        "title_breakdown": "{topic}: The Complete Breakdown of This {niche} Video",
        "fallback_body": "This {niche} breakdown takes a single short-form clip and turns it into a full written resource.",
        "fallback_core": "Everything in the clip orbits one idea: {primary}.",
        "sec_standout": "What makes this {niche} video stand out",
        "sec_core": "The core idea, explained",
        "sec_takeaways": "Key takeaways",
        "sec_apply": "How to apply this to your own content",
        "sec_transcript": "The full transcript, cleaned up",
        "sec_faq": "Frequently asked questions",
        "sec_bottom": "The bottom line",
        "intro_p1": "There is a specific reason this {niche} clip stops the scroll, and it is not luck. {body0}",
        "intro_p2": "The original video by {author} runs under a minute, but the ideas inside it are worth expanding into something you can actually reference, quote and reuse. That is what this article does: the full script, the reasoning behind each point, and how to apply it to your own content without spending another hour writing from a blank page.",
        "apply_p1": "Start from the same hook. Lead with the {primary} claim in the first two seconds, before the viewer has a chance to scroll - the clip does exactly this and it is the single most copyable move in it.",
        "apply_p2": "Write to one idea per beat, then expand each beat once instead of re-pitching it: a paragraph for the article, a tweet for the thread, a paragraph for the post. The thinking only has to happen one time.",
        "apply_p3": "Repurpose deliberately rather than re-uploading. One clip should come out the other side as three assets in three different formats, each tuned for the platform it is going to rather than cross-posted verbatim.",
        "take1": "- **{Primary}** is the thread that holds the whole clip together.",
        "take2": "- **{Secondary}** is what makes it repeatable rather than a one-off.",
        "take3": "- The format matters as much as the message: tight pacing, one idea per beat.",
        "take_source": " As the clip puts it: \"{sentence}\".",
        "faq_q": "**What does the video say about {kw}?**",
        "faq_a_none": "It treats {kw} as one of the load-bearing pieces of the argument rather than a side detail.",
        "meta_desc": "Full breakdown of the {niche} video by {author} covering {primary}{rest}. Key takeaways, tactics and how to apply them.",
        "bottom_p1": "The clip works because it is built on {primary}, and that same structure is available to anyone willing to script for it. Take the hook, keep one idea per beat, and let one video become an article, a thread and a post instead of a single post that disappears in an hour.",
        "thread_hook": "I shredded a {niche} video into a full article + this thread.\n\nThe core idea: {primary}.\n\nHere's the whole breakdown in {n} tweets.",
        "thread_steal": "What to steal:\n\n- One idea per beat\n- Hook leads with {primary}\n- Every clip becomes 3 assets, not 1 re-upload",
        "thread_cta": "If you make {niche} content, this is your repurposing system.\n\nShred your own link and get the article, this thread and a LinkedIn post: Viral Shredder.",
        "li_opener": "I shredded a {niche} clip into a full SEO article, an X thread and this post.",
        "li_body_intro": "Here is what was actually in it:",
        "li_fallback": "The clip is under 60 seconds, but the idea behind it - {primary} - is worth a full page.",
        "li_close": "The point is not the clip. It is that a single 45-second video already contains enough substance for a week of content - if you have a system to extract it instead of just re-uploading it.",
        "li_link": "Link to the full breakdown in the comments.",
        "and": "and",
    },
    "ar": {
        "title_playbook": "دليل {niche}: تحليل كامل لهذا الفيديو الفيروسي",
        "title_breakdown": "{topic}: التحليل الكامل لفيديو {niche} هذا",
        "fallback_body": "يأخذ هذا التحليل الخاص بـ{niche} مقطعًا قصيرًا واحدًا ويحوّله إلى مورد مكتوب متكامل.",
        "fallback_core": "كل ما في المقطع يدور حول فكرة واحدة: {primary}.",
        "sec_standout": "ما الذي يجعل فيديو {niche} هذا مميزًا",
        "sec_core": "الفكرة الأساسية، مشروحة",
        "sec_takeaways": "أبرز النقاط المستفادة",
        "sec_apply": "كيف تطبّق هذا على محتواك الخاص",
        "sec_transcript": "النص الكامل، منظّم",
        "sec_faq": "الأسئلة الشائعة",
        "sec_bottom": "الخلاصة",
        "intro_p1": "هناك سبب محدد يجعل مقطع {niche} هذا يوقف التمرير، وليس صدفة. {body0}",
        "intro_p2": "الفيديو الأصلي لـ{author} يستغرق أقل من دقيقة، لكن الأفكار بداخله تستحق أن تتحول إلى شيء يمكنك الرجوع إليه ونقله وإعادة استخدامه. وهذا ما يفعله هذا المقال: النص الكامل، والسبب وراء كل نقطة، وكيف تطبّقها على محتواك دون قضاء ساعة أخرى في الكتابة من صفحة بيضاء.",
        "apply_p1": "ابدأ من نفس الخطاف. قدّم ادعاء {primary} في أول ثانيتين، قبل أن تتاح للجمهور فرصة التمرير - وهذا بالضبط ما يفعله المقطع، وهو الحركة الوحيدة الأكثر قابلية للاستعارة فيه.",
        "apply_p2": "اكتب فكرة واحدة في كل حقة، ثم وسّع كل حقة مرة واحدة بدل إعادة طرحها: فقرة للمقال، وتغريدة للتقرير، وفقرة للمنشور. التفكير يحدث مرة واحدة فقط.",
        "apply_p3": "أعد استخدام المحتوى بوعي بدل إعادة رفعه. يجب أن يخرج المقطع الواحد كأصول ثلاثة في صيغ ثلاث مختلفة، كل واحدة مُعدّلة للمنصة التي تتجه إليها بدل النسخ الحرفي.",
        "take1": "- **{Primary}** هو الخيط الذي يربط المقطع كله ببعضه.",
        "take2": "- **{Secondary}** هو ما يجعله قابلًا للتكرار بدل أن يكون مرة واحدة.",
        "take3": "- الشكل يهم بقدر الرسالة: إيقاع محكم وفكرة واحدة في كل حقة.",
        "take_source": " كما يقول المقطع: «{sentence}».",
        "faq_q": "**ماذا يقول الفيديو عن {kw}؟**",
        "faq_a_none": "يتعامل مع {kw} كأحد الأعمدة الحاملة للحجة بدل تفصيل ثانوي.",
        "meta_desc": "تحليل كامل لفيديو {niche} لـ{author} يغطي {primary}{rest}. أبرز النقاط والتكتيكات وكيفية تطبيقها.",
        "bottom_p1": "يعمل المقطع لأنه مبني على {primary}، والهيكل نفسه متاح لأي شخص مستعد لكتابته مسبقًا. خذ الخطاف، وابقَ على فكرة واحدة في كل حقة، ودع فيديو واحدًا يصبح مقالًا وتقريرًا ومنشورًا بدل منشور واحد يختفي في ساعة.",
        "thread_hook": "حلّلت فيديو {niche} إلى مقال كامل + هذا التقرير.\n\nالفكرة الأساسية: {primary}.\n\nإليك التحليل كاملًا في {n} تغريدات.",
        "thread_steal": "ماذا تستفيد منه:\n\n- فكرة واحدة في كل حقة\n- الخطاف يبدأ بـ{primary}\n- كل مقطع يصبح 3 أصول، لا رفعًا واحدًا",
        "thread_cta": "إذا تصنع محتوى {niche}، فهذا نظام إعادة الاستخدام الخاص بك.\n\nحلّل الرابط الخاص بك واحصل على المقال وهذا التقرير ومنشور لينكدإن: Viral Shredder.",
        "li_opener": "حلّلت مقطع {niche} إلى مقال SEO كامل وتقرير وهذا المشاركة.",
        "li_body_intro": "هذا ما كان فيه فعلًا:",
        "li_fallback": "المقطع أقل من 60 ثانية، لكن الفكرة وراءه - {primary} - تستحق صفحة كاملة.",
        "li_close": "النقطة ليست المقطع. بل أن فيديو واحدًا مدته 45 ثانية يحتوي بالفعل على ما يكفي لأسبوع من المحتوى - إذا كان لديك نظام لاستخراجه بدل مجرد إعادة رفعه.",
        "li_link": "رابط التحليل الكامل في التعليقات.",
        "and": "و",
    },
    "es": {
        "title_playbook": "El manual de {niche}: análisis completo de este video viral",
        "title_breakdown": "{topic}: el análisis completo de este video de {niche}",
        "fallback_body": "Este análisis de {niche} toma un solo clip corto y lo convierte en un recurso escrito completo.",
        "fallback_core": "Todo en el clip gira en torno a una idea: {primary}.",
        "sec_standout": "Qué hace que este video de {niche} destaque",
        "sec_core": "La idea central, explicada",
        "sec_takeaways": "Conclusiones clave",
        "sec_apply": "Cómo aplicar esto a tu propio contenido",
        "sec_transcript": "La transcripción completa, organizada",
        "sec_faq": "Preguntas frecuentes",
        "sec_bottom": "La conclusión",
        "intro_p1": "Hay una razón concreta por la que este clip de {niche} detiene el scroll, y no es suerte. {body0}",
        "intro_p2": "El video original de {author} dura menos de un minuto, pero las ideas que contiene merecen ampliarse en algo que puedas consultar, citar y reutilizar. Eso es lo que hace este artículo: la transcripción completa, el razonamiento de cada punto y cómo aplicarlo a tu propio contenido sin pasar otra hora escribiendo desde una página en blanco.",
        "apply_p1": "Empieza con el mismo gancho. Lanza la afirmación sobre {primary} en los primeros dos segundos, antes de que el espectador pueda hacer scroll - el clip hace exactamente esto y es el movimiento más copiable que tiene.",
        "apply_p2": "Escribe una idea por momento y amplía cada uno una sola vez en lugar de volver a presentarlo: un párrafo para el artículo, un tuit para el hilo, un párrafo para el post. Pensar solo tiene que pasar una vez.",
        "apply_p3": "Reutiliza con intención en lugar de volver a subir el clip. Un clip debería convertirse en tres piezas en tres formatos distintos, cada uno ajustado a la plataforma de destino en lugar de publicarse de forma idéntica en todas.",
        "take1": "- **{Primary}** es el hilo que sostiene todo el clip.",
        "take2": "- **{Secondary}** es lo que lo hace repetible en lugar de un éxito de una sola vez.",
        "take3": "- El formato importa tanto como el mensaje: ritmo ajustado, una idea por momento.",
        "take_source": " Como dice el clip: «{sentence}».",
        "faq_q": "**¿Qué dice el video sobre {kw}?**",
        "faq_a_none": "Trata {kw} como una de las piezas fundamentales del argumento y no como un detalle secundario.",
        "meta_desc": "Análisis completo del video de {niche} de {author} sobre {primary}{rest}. Conclusiones clave, tácticas y cómo aplicarlas.",
        "bottom_p1": "El clip funciona porque está construido sobre {primary}, y esa misma estructura está disponible para cualquiera dispuesto a guionizarla. Toma el gancho, mantén una idea por momento y deja que un video se convierta en un artículo, un hilo y un post en lugar de un solo post que desaparece en una hora.",
        "thread_hook": "Convertí un video de {niche} en un artículo completo + este hilo.\n\nLa idea central: {primary}.\n\nAquí está todo el análisis en {n} tuits.",
        "thread_steal": "Qué robarle:\n\n- Una idea por momento\n- El gancho abre con {primary}\n- Cada clip se vuelve 3 piezas, no 1 republicación",
        "thread_cta": "Si creas contenido de {niche}, este es tu sistema de reutilización.\n\nAnaliza tu propio enlace y obtén el artículo, este hilo y un post para LinkedIn: Viral Shredder.",
        "li_opener": "Convertí un clip de {niche} en un artículo SEO completo, un hilo y este post.",
        "li_body_intro": "Esto es lo que realmente contenía:",
        "li_fallback": "El clip dura menos de 60 segundos, pero la idea detrás - {primary} - merece una página completa.",
        "li_close": "El punto no es el clip. Es que un solo video de 45 segundos ya contiene sustancia suficiente para una semana de contenido, si tienes un sistema para extraerlo en lugar de simplemente volver a subirlo.",
        "li_link": "Enlace al análisis completo en los comentarios.",
        "and": "y",
    },
    "fr": {
        "title_playbook": "Le guide {niche} : analyse complète de cette vidéo virale",
        "title_breakdown": "{topic} : l'analyse complète de cette vidéo {niche}",
        "fallback_body": "Cette analyse {niche} prend un seul clip court et en fait une ressource écrite complète.",
        "fallback_core": "Tout dans le clip tourne autour d'une seule idée : {primary}.",
        "sec_standout": "Pourquoi cette vidéo {niche} retient l'attention",
        "sec_core": "L'idée centrale, expliquée",
        "sec_takeaways": "Points clés à retenir",
        "sec_apply": "Comment appliquer cela à votre propre contenu",
        "sec_transcript": "La transcription complète, nettoyée",
        "sec_faq": "Questions fréquentes",
        "sec_bottom": "En conclusion",
        "intro_p1": "Il y a une raison précise pour laquelle ce clip {niche} arrête le défilement, et ce n'est pas la chance. {body0}",
        "intro_p2": "La vidéo originale de {author} dure moins d'une minute, mais les idées qu'elle contient méritent d'être développées en quelque chose que vous pouvez réellement consulter, citer et réutiliser. C'est le rôle de cet article : la transcription complète, le raisonnement derrière chaque point, et la manière de l'appliquer à votre propre contenu sans passer une heure de plus devant une page blanche.",
        "apply_p1": "Partez de la même accroche. Annoncez {primary} dans les deux premières secondes, avant que le spectateur ait le temps de défiler - c'est exactement ce que fait le clip, et c'est le mouvement le plus reproductible qu'il contient.",
        "apply_p2": "Écrivez une idée par temps fort, puis développez chacun une seule fois au lieu de le re-présenter : un paragraphe pour l'article, un tweet pour le thread, un paragraphe pour le post. La réflexion n'a lieu qu'une seule fois.",
        "apply_p3": "Réutilisez délibérément plutôt que de republier. Un clip devrait devenir trois éléments dans trois formats différents, chacun adapté à la plateforme de destination plutôt que recopié à l'identique.",
        "take1": "- **{Primary}** est le fil qui relie tout le clip.",
        "take2": "- **{Secondary}** est ce qui le rend répétable plutôt qu'unique.",
        "take3": "- Le format compte autant que le message : rythme serré, une idée par temps fort.",
        "take_source": " Comme le dit le clip : « {sentence} ».",
        "faq_q": "**Que dit la vidéo de {kw} ?**",
        "faq_a_none": "Elle traite {kw} comme l'un des piliers de l'argumentation plutôt que comme un détail secondaire.",
        "meta_desc": "Analyse complète de la vidéo {niche} de {author} sur {primary}{rest}. Points clés, tactiques et manière de les appliquer.",
        "bottom_p1": "Le clip fonctionne parce qu'il est bâti sur {primary}, et cette même structure est disponible pour quiconque accepte de la scripter. Reprenez l'accroche, gardez une idée par temps fort, et laissez une vidéo devenir un article, un thread et un post au lieu d'un seul post qui disparaît en une heure.",
        "thread_hook": "J'ai transformé une vidéo {niche} en un article complet + ce thread.\n\nL'idée centrale : {primary}.\n\nVoici toute l'analyse en {n} tweets.",
        "thread_steal": "Ce qu'il faut retenir :\n\n- Une idée par temps fort\n- L'accroche commence par {primary}\n- Chaque clip devient 3 éléments, pas 1 republication",
        "thread_cta": "Si vous créez du contenu {niche}, c'est votre système de réutilisation.\n\nAnalysez votre propre lien et obtenez l'article, ce thread et un post LinkedIn : Viral Shredder.",
        "li_opener": "J'ai transformé un clip {niche} en un article SEO complet, un thread et ce post.",
        "li_body_intro": "Voici ce qu'il contenait vraiment :",
        "li_fallback": "Le clip dure moins de 60 secondes, mais l'idée derrière - {primary} - mérite une page entière.",
        "li_close": "L'enjeu n'est pas le clip. C'est qu'une seule vidéo de 45 secondes contient déjà assez de substance pour une semaine de contenu, si vous avez un système pour l'extraire au lieu de la republier.",
        "li_link": "Lien vers l'analyse complète en commentaire.",
        "and": "et",
    },
}


# ---------------------------------------------------------------------------
# Tone overrides - the keys that actually carry the voice.
# Layered on top of the base table, per language.
# ---------------------------------------------------------------------------
TONE_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {
    "viral": {
        "en": {
            "intro_p1": "This {niche} clip doesn't go viral by accident - it's engineered to stop the scroll. {body0}",
            "take1": "- **{Primary}** is the single reason this clip blows up.",
            "take2": "- **{Secondary}** is the repeatable formula, not a one-hit wonder.",
            "take3": "- Format beats message: tight pacing, one idea per beat, zero warm-up.",
            "bottom_p1": "The clip wins because it's built on {primary} - and that formula is sitting right there for you to steal. Take the hook, keep one idea per beat, and let one video become an article, a thread and a post instead of a post that dies in an hour.",
            "thread_hook": "I shredded ONE {niche} video into a full article + this thread.\n\nThe hook: {primary}.\n\nAll of it in {n} tweets. Save this one.",
            "thread_steal": "Steal this:\n\n- One idea per beat\n- Hook leads with {primary}\n- 1 clip = 3 assets, not 1 re-upload",
            "li_opener": "One {niche} clip. Three assets. Zero rewriting.\n\nHere's what I made from it:",
            "li_close": "Stop re-uploading. One 45-second video is already a week of content - you just need a system that extracts instead of reposting.",
        },
        "ar": {
            "intro_p1": "هذا المقطع من {niche} لم ينتشر بالصدفة - بل صُمّم خصيصًا ليوقف التمرير. {body0}",
            "take1": "- **{Primary}** هو السبب الوحيد لانتشار هذا المقطع.",
            "take2": "- **{Secondary}** هي الصيغة القابلة للتكرار، لا نجاحًا لمرة واحدة.",
            "take3": "- الشكل يتفوق على الرسالة: إيقاع محكم، فكرة واحدة في كل حقة، دون أي مقدمات.",
            "bottom_p1": "يفوز المقطع لأنه مبني على {primary} - والصيغة موجودة أمامك لكي تستفيد منها. خذ الخطاف، ابقَ على فكرة واحدة في كل حقة، ودع فيديو واحدًا يصبح مقالًا وتقريرًا ومنشورًا بدل منشور يموت في ساعة.",
            "thread_hook": "حلّلت فيديو {niche} واحدًا إلى مقال كامل + هذا التقرير.\n\nالخطاف: {primary}.\n\nكله في {n} تغريدات. احفظ هذا.",
            "thread_steal": "استفد من هذا:\n\n- فكرة واحدة في كل حقة\n- الخطاف يبدأ بـ{primary}\n- مقطع واحد = 3 أصول، لا رفع واحد",
            "li_opener": "مقطع {niche} واحد. ثلاثة أصول. صفر إعادة كتابة.\n\nهذا ما صنعته منه:",
            "li_close": "توقف عن إعادة الرفع. فيديو واحد مدته 45 ثانية هو أسبوع محتوى كامل - تحتاج فقط نظامًا يستخرج بدل أن يعيد النشر.",
        },
        "es": {
            "intro_p1": "Este clip de {niche} no se hace viral por accidente - está diseñado para detener el scroll. {body0}",
            "take1": "- **{Primary}** es la única razón por la que este clip explota.",
            "take2": "- **{Secondary}** es la fórmula repetible, no un éxito de una sola vez.",
            "take3": "- El formato vence al mensaje: ritmo ajustado, una idea por momento, cero preámbulos.",
            "bottom_p1": "El clip gana porque está construido sobre {primary} - y esa fórmula está ahí para que la robes. Toma el gancho, mantén una idea por momento y deja que un video se convierta en un artículo, un hilo y un post en lugar de un post que muere en una hora.",
            "thread_hook": "Convertí UN video de {niche} en un artículo completo + este hilo.\n\nEl gancho: {primary}.\n\nTodo en {n} tuits. Guarda este.",
            "thread_steal": "Roba esto:\n\n- Una idea por momento\n- El gancho abre con {primary}\n- 1 clip = 3 piezas, no 1 republicación",
            "li_opener": "Un clip de {niche}. Tres piezas. Cero reescritura.\n\nEsto es lo que hice con él:",
            "li_close": "Deja de volver a subir. Un video de 45 segundos ya es una semana de contenido - solo necesitas un sistema que extraiga en lugar de republicar.",
        },
        "fr": {
            "intro_p1": "Ce clip {niche} ne devient pas viral par accident - il est conçu pour arrêter le défilement. {body0}",
            "take1": "- **{Primary}** est la seule raison pour laquelle ce clip explose.",
            "take2": "- **{Secondary}** est la formule reproductible, pas un succès unique.",
            "take3": "- Le format bat le message : rythme serré, une idée par temps fort, zéro préambule.",
            "bottom_p1": "Le clip gagne parce qu'il est bâti sur {primary} - et la formule est là, prête à être reprise. Prenez l'accroche, gardez une idée par temps fort, et laissez une vidéo devenir un article, un thread et un post au lieu d'un post qui meurt en une heure.",
            "thread_hook": "J'ai transformé UNE vidéo {niche} en un article complet + ce thread.\n\nL'accroche : {primary}.\n\nTout en {n} tweets. Enregistrez celui-ci.",
            "thread_steal": "Reprenez ceci :\n\n- Une idée par temps fort\n- L'accroche commence par {primary}\n- 1 clip = 3 éléments, pas 1 republication",
            "li_opener": "Un clip {niche}. Trois éléments. Zéro réécriture.\n\nVoici ce que j'en ai tiré :",
            "li_close": "Arrêtez de republier. Une vidéo de 45 secondes, c'est déjà une semaine de contenu - il suffit d'un système qui extrait au lieu de reposter.",
        },
    },
    "storytelling": {
        "en": {
            "intro_p1": "Picture the moment just before the scroll stops. There's a reason you paused on this {niche} clip, and it wasn't an accident. {body0}",
            "take1": "- **{Primary}** is the thread the whole story is pulled along.",
            "take2": "- **{Secondary}** is what makes the story tellable again and again.",
            "take3": "- Every beat carries one idea - that's what keeps the narrative moving.",
            "bottom_p1": "Every clip is a small story built on {primary}, and that structure is there for anyone patient enough to script it. Start with the hook, give each beat one idea, and let a single video become an article, a thread and a post instead of a post that disappears in an hour.",
            "thread_hook": "I took one {niche} video and pulled the story out of it.\n\nWhat it's really about: {primary}.\n\nThe whole thing, in {n} tweets.",
            "thread_steal": "The story you can borrow:\n\n- One idea per beat\n- The hook promises {primary}\n- One clip becomes an article, a thread, a post",
            "li_opener": "A few days ago I watched a {niche} clip that stopped me mid-scroll. I turned it into an article, a thread, and this post.",
            "li_close": "The clip isn't the point. The point is that 45 seconds already holds a week of stories - if you have a system for telling them instead of just reposting them.",
        },
        "ar": {
            "intro_p1": "تخيّل اللحظة التي يتوقف فيها التمرير. هناك سبب توقفت عنده عند مقطع {niche} هذا، ولم يكن صدفة. {body0}",
            "take1": "- **{Primary}** هو الخيط الذي تُسحب عليه القصة كلها.",
            "take2": "- **{Secondary}** هو ما يجعل القصة قابلة للحكي مرارًا وتكرارًا.",
            "take3": "- كل حقة تحمل فكرة واحدة - وهذا ما يبقي السرد متحركًا.",
            "bottom_p1": "كل مقطع قصة صغيرة مبنية على {primary}، وهذا الهيكل متاح لأي شخص يصبر على كتابته مسبقًا. ابدأ بالخطاف، أعطِ كل حقة فكرة واحدة، ودع فيديو واحدًا يصبح مقالًا وتقريرًا ومنشورًا بدل منشور يختفي في ساعة.",
            "thread_hook": "أخذت فيديو {niche} واحدًا وسحبت القصة منه.\n\nما يدور حوله فعلًا: {primary}.\n\nالقصة كاملة، في {n} تغريدات.",
            "thread_steal": "القصة التي يمكنك استعارتها:\n\n- فكرة واحدة في كل حقة\n- الخطاف يَعِدُ بـ{primary}\n- مقطع واحد يصبح مقالًا وتقريرًا ومنشورًا",
            "li_opener": "قبل أيام شاهدت مقطع {niche} أوقفني في منتصف التمرير. حوّلته إلى مقال وتقرير وهذا المشاركة.",
            "li_close": "المقطع ليس هو القصد. القصد أن 45 ثانية تحمل أسبوعًا كاملًا من القصص - إذا كان لديك نظام لحكيها بدل مجرد إعادة نشرها.",
        },
        "es": {
            "intro_p1": "Imagina el momento justo antes de que el scroll se detenga. Hay una razón por la que pausaste en este clip de {niche}, y no fue un accidente. {body0}",
            "take1": "- **{Primary}** es el hilo del que tira toda la historia.",
            "take2": "- **{Secondary}** es lo que permite contar la historia una y otra vez.",
            "take3": "- Cada momento lleva una idea - eso es lo que mantiene la narrativa en movimiento.",
            "bottom_p1": "Cada clip es una pequeña historia construida sobre {primary}, y esa estructura está ahí para cualquiera con la paciencia de guionizarla. Empieza por el gancho, dale a cada momento una idea, y deja que un video se convierta en un artículo, un hilo y un post en lugar de un post que desaparece en una hora.",
            "thread_hook": "Tomé un video de {niche} y le saqué la historia.\n\nDe qué trata realmente: {primary}.\n\nTodo, en {n} tuits.",
            "thread_steal": "La historia que puedes tomar prestada:\n\n- Una idea por momento\n- El gancho promete {primary}\n- Un clip se convierte en artículo, hilo y post",
            "li_opener": "Hace unos días vi un clip de {niche} que me detuvo en medio del scroll. Lo convertí en un artículo, un hilo y este post.",
            "li_close": "El clip no es el punto. El punto es que 45 segundos ya contienen una semana de historias - si tienes un sistema para contarlas en lugar de simplemente republicarlas.",
        },
        "fr": {
            "intro_p1": "Imaginez l'instant juste avant que le défilement s'arrête. Si vous avez fait une pause sur ce clip {niche}, ce n'était pas un accident. {body0}",
            "take1": "- **{Primary}** est le fil sur lequel toute l'histoire vient s'enrouler.",
            "take2": "- **{Secondary}** est ce qui rend l'histoire racontable encore et encore.",
            "take3": "- Chaque temps fort porte une idée - c'est ce qui fait avancer le récit.",
            "bottom_p1": "Chaque clip est une petite histoire bâtie sur {primary}, et cette structure est là pour quiconque accepte de la scripter. Commencez par l'accroche, donnez une idée par temps fort, et laissez une vidéo devenir un article, un thread et un post au lieu d'un post qui disparaît en une heure.",
            "thread_hook": "J'ai pris une vidéo {niche} et j'en ai tiré l'histoire.\n\nCe dont elle parle vraiment : {primary}.\n\nTout, en {n} tweets.",
            "thread_steal": "L'histoire que vous pouvez emprunter :\n\n- Une idée par temps fort\n- L'accroche promet {primary}\n- Un clip devient un article, un thread, un post",
            "li_opener": "Il y a quelques jours, un clip {niche} m'a arrêté en plein défilement. Je l'ai transformé en un article, un thread et ce post.",
            "li_close": "Le clip n'est pas le sujet. Le sujet, c'est que 45 secondes contiennent déjà une semaine d'histoires - si vous avez un système pour les raconter au lieu de les republier.",
        },
    },
}


def resolve(key: str, language: str = DEFAULT_LANGUAGE, tone: str = DEFAULT_TONE,
            **fmt) -> str:
    """Look up a localized string, with the tone layer on top of the language."""
    base = L10N.get(language, L10N[DEFAULT_LANGUAGE])
    table = base
    tone_table = TONE_OVERRIDES.get(tone, {}).get(language)
    if tone_table:
        table = {**base, **tone_table}
    template = table.get(key)
    if template is None:
        template = L10N[DEFAULT_LANGUAGE].get(key, "")
    try:
        return template.format(**fmt)
    except (KeyError, IndexError):
        return template


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def tone_label(code: str) -> str:
    entry = TONES.get(code)
    return entry["label"] if entry else code


def valid_language(code: str | None) -> str:
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def valid_tone(code: str | None) -> str:
    return code if code in TONES else DEFAULT_TONE
