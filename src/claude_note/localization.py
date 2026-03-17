"""
Localization support for claude-note.

Provides translations for synthesis prompts, schema descriptions, and UI labels.
"""

from typing import Dict

# =============================================================================
# Translation Data
# =============================================================================

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Synthesis prompt labels
        "no_user_prompts": "(No user prompts)",
        "no_tool_uses": "(No tool uses)",
        "no_files_touched": "(No files touched)",
        "no_errors": "(None)",
        "no_vault_notes": "(No vault notes indexed)",
        "semantic_search_disabled": "(Semantic search disabled)",
        "qmd_not_available": "(qmd not available - using note names only)",
        "no_query_context": "(No query context from session)",
        "no_related_notes": "(No semantically related notes found)",
        "unknown": "unknown",

        # Synthesis prompt sections
        "prompt_header": "You are extracting durable knowledge from a Claude Code session.",
        "session_context": "## Session Context",
        "working_directory": "Working directory:",
        "date": "Date:",
        "session_id": "Session ID:",
        "user_prompts": "## User Prompts",
        "key_tool_uses": "## Key Tool Uses",
        "tool_usage_summary": "Tool usage summary:",
        "notable_operations": "Notable operations:",
        "files_touched": "## Files Touched",
        "errors_encountered": "## Errors Encountered",
        "related_notes": "## Related Notes (semantic matches)",
        "found_related_notes": "Found {count} related notes:",
        "existing_vault_notes": "## Existing Vault Notes (for linking)",
        "vault_has_notes": "Vault has {count} notes.",
        "available_tags": "Available tags:",
        "existing_notes": "Existing notes:",

        # Synthesis task
        "your_task": "## Your Task",
        "extract_knowledge_intro": "Extract knowledge into this exact JSON schema:",

        # Synthesis rules
        "rules": "## Rules",
        "rule_1": "**Only extract genuinely durable knowledge** - things that would be useful in 1 week",
        "rule_2": "**CRITICAL - Check existing notes:** The list above shows ALL notes in the vault. Before generating a note_op:",
        "rule_2a": "   - If a note with that name already exists → use \"upsert_block\" (NEVER \"create\")",
        "rule_2b": "   - Only use \"create\" for topics that have NO existing note",
        "rule_3": "**Use existing tags from the vault** when they fit",
        "rule_4": "**Keep summaries concise** (2-4 sentences for concepts)",
        "rule_5": "**For note_ops:**",
        "rule_5a": "   - \"upsert_block\": Updates existing note with a managed block. Use managed_block_id like \"synth-findings\" or \"synth-howto\"",
        "rule_5b": "   - \"create\": Only for genuinely NEW topics with no existing note",
        "rule_5c": "   - \"append\": Add to a section in existing note (use sparingly)",
        "rule_6": "**Don't extract:**",
        "rule_6a": "   - Trivial file reads/writes with no learning",
        "rule_6b": "   - Debugging steps that didn't lead anywhere",
        "rule_6c": "   - Information that's already well-documented elsewhere",
        "rule_7": "**If the session was trivial** (just navigation, simple fixes), return empty note_ops",
        "return_only_json": "Return ONLY valid JSON matching the schema. No markdown, no explanation, just the JSON object.",

        # UI labels (for CLI output)
        "re_synthesizing": "Re-synthesizing session",
        "using_model": "Using model:",
        "no_knowledge_extracted": "No knowledge extracted from session.",
        "extracted": "Extracted:",
        "title_label": "Title:",
        "highlights_label": "Highlights:",
        "concepts_label": "Concepts:",
        "decisions_label": "Decisions:",
        "open_questions_label": "Open questions:",
        "howtos_label": "How-tos:",
        "note_ops_label": "Note ops:",
        "applying_with_mode": "Applying with mode:",
        "updated_inbox": "Updated inbox",
        "created": "Created:",
        "updated": "Updated:",
        "errors_label": "Errors:",
    },

    "ru": {
        # Synthesis prompt labels
        "no_user_prompts": "(Нет пользовательских запросов)",
        "no_tool_uses": "(Нет использований инструментов)",
        "no_files_touched": "(Файлы не затрагивались)",
        "no_errors": "(Нет)",
        "no_vault_notes": "(Заметки в хранилище не проиндексированы)",
        "semantic_search_disabled": "(Семантический поиск отключен)",
        "qmd_not_available": "(qmd недоступен - используются только имена заметок)",
        "no_query_context": "(Нет контекста запроса из сессии)",
        "no_related_notes": "(Семантически связанные заметки не найдены)",
        "unknown": "неизвестно",

        # Synthesis prompt sections
        "prompt_header": "Вы извлекаете устойчивые знания из сессии Claude Code.",
        "session_context": "## Контекст сессии",
        "working_directory": "Рабочий каталог:",
        "date": "Дата:",
        "session_id": "ID сессии:",
        "user_prompts": "## Пользовательские запросы",
        "key_tool_uses": "## Ключевые использования инструментов",
        "tool_usage_summary": "Сводка использования инструментов:",
        "notable_operations": "Значимые операции:",
        "files_touched": "## Затронутые файлы",
        "errors_encountered": "## Обнаруженные ошибки",
        "related_notes": "## Связанные заметки (семантические совпадения)",
        "found_related_notes": "Найдено {count} связанных заметок:",
        "existing_vault_notes": "## Существующие заметки в хранилище (для связывания)",
        "vault_has_notes": "В хранилище {count} заметок.",
        "available_tags": "Доступные теги:",
        "existing_notes": "Существующие заметки:",

        # Synthesis task
        "your_task": "## Ваша задача",
        "extract_knowledge_intro": "Извлеките знания в следующую точную JSON-схему:",

        # Synthesis rules
        "rules": "## Правила",
        "rule_1": "**Извлекайте только действительно устойчивые знания** - то, что будет полезно через неделю",
        "rule_2": "**КРИТИЧЕСКИ - Проверьте существующие заметки:** Список выше показывает ВСЕ заметки в хранилище. Перед созданием note_op:",
        "rule_2a": "   - Если заметка с таким именем уже существует → используйте \"upsert_block\" (НИКОГДА \"create\")",
        "rule_2b": "   - Используйте \"create\" только для тем, для которых НЕ существует заметки",
        "rule_3": "**Используйте существующие теги из хранилища**, когда они подходят",
        "rule_4": "**Держите описания краткими** (2-4 предложения для концепций)",
        "rule_5": "**Для note_ops:**",
        "rule_5a": "   - \"upsert_block\": Обновляет существующую заметку управляемым блоком. Используйте managed_block_id, например, \"synth-findings\" или \"synth-howto\"",
        "rule_5b": "   - \"create\": Только для действительно НОВЫХ тем без существующей заметки",
        "rule_5c": "   - \"append\": Добавить в раздел существующей заметки (используйте редко)",
        "rule_6": "**Не извлекайте:**",
        "rule_6a": "   - Тривиальные чтения/записи файлов без обучения",
        "rule_6b": "   - Шаги отладки, которые ни к чему не привели",
        "rule_6c": "   - Информация, которая уже хорошо документирована в другом месте",
        "rule_7": "**Если сессия была тривиальной** (только навигация, простые исправления), верните пустой note_ops",
        "return_only_json": "Верните ТОЛЬКО валидный JSON, соответствующий схеме. Без markdown, без объяснений, только JSON-объект.",

        # UI labels (for CLI output)
        "re_synthesizing": "Повторный синтез сессии",
        "using_model": "Используется модель:",
        "no_knowledge_extracted": "Знания из сессии не извлечены.",
        "extracted": "Извлечено:",
        "title_label": "Заголовок:",
        "highlights_label": "Основные результаты:",
        "concepts_label": "Концепции:",
        "decisions_label": "Решения:",
        "open_questions_label": "Открытые вопросы:",
        "howtos_label": "Инструкции:",
        "note_ops_label": "Операции с заметками:",
        "applying_with_mode": "Применение с режимом:",
        "updated_inbox": "Входящие обновлены",
        "created": "Создано:",
        "updated": "Обновлено:",
        "errors_label": "Ошибки:",
    },
}

# =============================================================================
# Schema descriptions
# =============================================================================

_SCHEMA_DESCRIPTIONS: Dict[str, str] = {
    "en": """{
    "session_id": "string - session identifier",
    "date": "string - ISO date (YYYY-MM-DD)",
    "time": "string - time (HH:MM:SS), optional",
    "title": "string - human-readable session title (5-10 words)",
    "highlights": ["string - 1-3 key outcomes of the session"],
    "concepts": [
        {
            "name": "string - concept name",
            "summary": "string - 2-4 sentence explanation",
            "tags": ["string - relevant tags from vault"],
            "links_suggested": ["string - note names to link to"]
        }
    ],
    "decisions": [
        {
            "decision": "string - what was decided",
            "rationale": "string - why this decision",
            "evidence": ["string - supporting facts"]
        }
    ],
    "open_questions": [
        {
            "question": "string - the question",
            "context": "string - why this matters",
            "suggested_next_step": "string - how to investigate"
        }
    ],
    "howtos": [
        {
            "title": "string - procedure title",
            "steps": ["string - step-by-step instructions"],
            "gotchas": ["string - pitfalls to avoid"]
        }
    ],
    "note_ops": [
        {
            "op": "create | upsert_block | append",
            "path": "string - note filename (e.g., 'my-note.md')",
            "frontmatter": {"tags": [...], ...},  // for create only
            "body_markdown": "string - content to write",
            "managed_block_id": "string",  // for upsert_block only
            "section": "string"  // for append only (e.g., '## Synthesized')
        }
    ]
}""",

    "ru": """{
    "session_id": "строка - идентификатор сессии",
    "date": "строка - ISO дата (ГГГГ-ММ-ДД)",
    "time": "строка - время (ЧЧ:ММ:СС), опционально",
    "title": "строка - читаемый заголовок сессии (5-10 слов)",
    "highlights": ["строка - 1-3 ключевых результата сессии"],
    "concepts": [
        {
            "name": "строка - название концепции",
            "summary": "строка - объяснение из 2-4 предложений",
            "tags": ["строка - соответствующие теги из хранилища"],
            "links_suggested": ["строка - имена заметок для связывания"]
        }
    ],
    "decisions": [
        {
            "decision": "строка - что было решено",
            "rationale": "строка - почему это решение",
            "evidence": ["строка - подтверждающие факты"]
        }
    ],
    "open_questions": [
        {
            "question": "строка - вопрос",
            "context": "строка - почему это важно",
            "suggested_next_step": "строка - как исследовать"
        }
    ],
    "howtos": [
        {
            "title": "строка - заголовок процедуры",
            "steps": ["строка - пошаговые инструкции"],
            "gotchas": ["строка - подводные камни, которых стоит избегать"]
        }
    ],
    "note_ops": [
        {
            "op": "create | upsert_block | append",
            "path": "строка - имя файла заметки (например, 'my-note.md')",
            "frontmatter": {"tags": [...], ...},  // только для create
            "body_markdown": "строка - содержимое для записи",
            "managed_block_id": "строка",  // только для upsert_block
            "section": "строка"  // только для append (например, '## Synthesized')
        }
    ]
}""",
}

# =============================================================================
# Synthesis prompt templates
# =============================================================================

_SYNTHESIS_PROMPTS: Dict[str, str] = {
    "en": """{prompt_header}

## Session Context
Working directory: {cwd}
Date: {date}
Session ID: {session_id}

## User Prompts
{user_prompts}

## Key Tool Uses
{tool_summary}

## Files Touched
{files_list}

## Errors Encountered
{errors}

## Related Notes (semantic matches)
{related_context}

## Existing Vault Notes (for linking)
{vault_summary}

## Your Task

{extract_knowledge_intro}
{schema}

## Rules

1. {rule_1}
2. {rule_2}
   {rule_2a}
   {rule_2b}
3. {rule_3}
4. {rule_4}
5. {rule_5}
   {rule_5a}
   {rule_5b}
   {rule_5c}
6. {rule_6}
   {rule_6a}
   {rule_6b}
   {rule_6c}
7. {rule_7}

{return_only_json}""",

    "ru": """{prompt_header}

## Контекст сессии
Рабочий каталог: {cwd}
Дата: {date}
ID сессии: {session_id}

## Пользовательские запросы
{user_prompts}

## Ключевые использования инструментов
{tool_summary}

## Затронутые файлы
{files_list}

## Обнаруженные ошибки
{errors}

## Связанные заметки (семантические совпадения)
{related_context}

## Существующие заметки в хранилище (для связывания)
{vault_summary}

## Ваша задача

{extract_knowledge_intro}
{schema}

## Правила

1. {rule_1}
2. {rule_2}
   {rule_2a}
   {rule_2b}
3. {rule_3}
4. {rule_4}
5. {rule_5}
   {rule_5a}
   {rule_5b}
   {rule_5c}
6. {rule_6}
   {rule_6a}
   {rule_6b}
   {rule_6c}
7. {rule_7}

{return_only_json}""",
}

# =============================================================================
# Public API
# =============================================================================

SUPPORTED_LANGUAGES = ["en", "ru"]


def get_label(key: str, lang: str = "en") -> str:
    """
    Get a translated label.

    Args:
        key: Translation key
        lang: Language code (default: "en")

    Returns:
        Translated string, or key if not found
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    return _TRANSLATIONS.get(lang, {}).get(key, key)


def get_schema_description(lang: str = "en") -> str:
    """
    Get the JSON schema description for KnowledgePack.

    Args:
        lang: Language code (default: "en")

    Returns:
        Schema description in the specified language
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    return _SCHEMA_DESCRIPTIONS.get(lang, _SCHEMA_DESCRIPTIONS["en"])


def get_synthesis_prompt_template(lang: str = "en") -> str:
    """
    Get the synthesis prompt template.

    The template uses {placeholder} syntax for formatting.

    Args:
        lang: Language code (default: "en")

    Returns:
        Prompt template string
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    return _SYNTHESIS_PROMPTS.get(lang, _SYNTHESIS_PROMPTS["en"])


def format_synthesis_prompt(
    lang: str,
    cwd: str,
    date: str,
    session_id: str,
    user_prompts: str,
    tool_summary: str,
    files_list: str,
    errors: str,
    related_context: str,
    vault_summary: str,
    schema: str,
) -> str:
    """
    Format the complete synthesis prompt with all context.

    Args:
        lang: Language code
        cwd: Working directory
        date: Session date
        session_id: Session ID
        user_prompts: Formatted user prompts
        tool_summary: Formatted tool usage summary
        files_list: Formatted files list
        errors: Formatted errors
        related_context: Related notes context
        vault_summary: Vault index summary
        schema: JSON schema description

    Returns:
        Complete formatted prompt
    """
    template = get_synthesis_prompt_template(lang)

    # Get all labels for the language
    labels = _TRANSLATIONS.get(lang, _TRANSLATIONS["en"])

    return template.format(
        prompt_header=labels.get("prompt_header", ""),
        cwd=cwd,
        date=date,
        session_id=session_id,
        user_prompts=user_prompts,
        tool_summary=tool_summary,
        files_list=files_list,
        errors=errors,
        related_context=related_context,
        vault_summary=vault_summary,
        extract_knowledge_intro=labels.get("extract_knowledge_intro", ""),
        schema=schema,
        rule_1=labels.get("rule_1", ""),
        rule_2=labels.get("rule_2", ""),
        rule_2a=labels.get("rule_2a", ""),
        rule_2b=labels.get("rule_2b", ""),
        rule_3=labels.get("rule_3", ""),
        rule_4=labels.get("rule_4", ""),
        rule_5=labels.get("rule_5", ""),
        rule_5a=labels.get("rule_5a", ""),
        rule_5b=labels.get("rule_5b", ""),
        rule_5c=labels.get("rule_5c", ""),
        rule_6=labels.get("rule_6", ""),
        rule_6a=labels.get("rule_6a", ""),
        rule_6b=labels.get("rule_6b", ""),
        rule_6c=labels.get("rule_6c", ""),
        rule_7=labels.get("rule_7", ""),
        return_only_json=labels.get("return_only_json", ""),
    )
