from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

MAX_PROMPT_CHARS = 32_000

PROFILES = (
    "auto",
    "general",
    "photorealistic",
    "illustration",
    "logo",
    "project-hero",
    "ip-character",
    "ad",
    "infographic",
    "academic-diagram",
    "ui-mockup",
    "comic",
    "product",
    "character-sheet",
    "edit",
    "composite",
    "translation",
)

_PROFILE_ALIASES = {
    "photo": "photorealistic",
    "photography": "photorealistic",
    "hero": "project-hero",
    "repo-cover": "project-hero",
    "repository-cover": "project-hero",
    "ip": "ip-character",
    "mascot": "ip-character",
    "diagram": "academic-diagram",
    "scientific-diagram": "academic-diagram",
    "ui": "ui-mockup",
    "mockup": "ui-mockup",
    "image-edit": "edit",
    "compose": "composite",
    "localization": "translation",
}

_OLD_STYLE_CUES = (
    "masterpiece",
    "best quality",
    "8k",
    "16k",
    "ultra detailed",
    "highly detailed",
    "trending on artstation",
    "award winning",
    "cinematic masterpiece",
)


@dataclass(slots=True)
class PromptIssue:
    code: str
    severity: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PromptReview:
    profile: str
    operation: str
    status: str
    issues: list[PromptIssue]
    features: dict[str, Any]

    @property
    def warnings(self) -> list[str]:
        return [issue.message for issue in self.issues if issue.severity == "warning"]

    @property
    def errors(self) -> list[str]:
        return [issue.message for issue in self.issues if issue.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "operation": self.operation,
            "status": self.status,
            "issues": [issue.to_dict() for issue in self.issues],
            "features": self.features,
        }

    def enforce(self, *, strict: bool = False) -> None:
        failures = self.errors
        if strict:
            failures += self.warnings
        if failures:
            prefix = "Prompt validation failed"
            if strict and not self.errors:
                prefix += " in strict mode"
            raise ValueError(prefix + ": " + " ".join(failures))


def normalize_profile(value: str | None) -> str:
    raw = (value or "auto").strip().lower().replace("_", "-")
    raw = _PROFILE_ALIASES.get(raw, raw)
    if raw not in PROFILES:
        raise ValueError(f"Unknown prompt profile {value!r}. Choose from: {', '.join(PROFILES)}.")
    return raw


def list_profiles() -> tuple[str, ...]:
    return PROFILES


def load_brief(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("The brief must be a JSON object.")
    return value


def resolve_prompt_context(
    brief: dict[str, Any],
    *,
    profile: str = "auto",
    operation: str | None = None,
) -> tuple[str, str]:
    explicit_operation = operation or brief.get("operation")
    tentative_operation = str(explicit_operation or "generate").strip().lower()
    if tentative_operation not in {"generate", "edit"}:
        raise ValueError("operation must be generate or edit.")
    selected = normalize_profile(profile)
    if selected == "auto":
        selected = infer_profile(brief, tentative_operation)
    resolved_operation = tentative_operation
    if explicit_operation is None and selected in {"edit", "composite", "translation"}:
        resolved_operation = "edit"
    return selected, resolved_operation


def _text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return "; ".join(_text(item).strip() for item in value if _text(item).strip())
    if isinstance(value, dict):
        return "; ".join(f"{str(k).replace('_', ' ')}: {_text(v)}" for k, v in value.items() if _text(v))
    return str(value).strip()


def _items(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            rendered = _text(item).strip().rstrip(".")
            if rendered:
                result.append(rendered)
        return result
    if isinstance(value, dict):
        return [
            f"{str(key).replace('_', ' ')}: {_text(item).strip().rstrip('.')}"
            for key, item in value.items()
            if _text(item).strip()
        ]
    return [str(value).strip().rstrip(".")]


def _first(brief: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = brief.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def infer_profile(brief: dict[str, Any], operation: str = "generate") -> str:
    explicit = _first(brief, "profile", "task", "type")
    if explicit:
        try:
            return normalize_profile(str(explicit))
        except ValueError:
            pass
    if operation == "edit":
        if _first(brief, "translation", "replacement_text", "text_map"):
            return "translation"
        if _first(brief, "references") and len(_items(brief.get("references"))) > 1:
            return "composite"
        return "edit"

    haystack = " ".join(
        _text(_first(brief, "deliverable", "purpose", "subject", "style", "visual_style")).lower().split()
    )
    checks = (
        ("project-hero", ("github", "repository", "repo cover", "project hero", "open-source", "open source")),
        ("academic-diagram", ("academic", "mechanism diagram", "architecture diagram", "framework diagram", "scientific")),
        ("infographic", ("infographic", "explainer", "timeline")),
        ("product", ("product render", "product mockup", "packaging", "ecommerce")),
        ("ui-mockup", ("ui mockup", "interface mockup", "dashboard", "app interface", "website interface")),
        ("character-sheet", ("character sheet", "turnaround", "expression sheet")),
        ("ip-character", ("mascot", "ip character", "character illustration")),
        ("logo", ("logo", "logomark", "brand mark")),
        ("ad", ("advertisement", "campaign", "poster", "social card")),
        ("comic", ("comic", "manga", "panels")),
        ("photorealistic", ("photorealistic", "photograph", "photo", "camera")),
        ("illustration", ("illustration", "watercolor", "vector", "3d render", "clay")),
    )
    for profile, words in checks:
        if any(word in haystack for word in words):
            return profile
    return "general"


def _section(title: str, value: Any, *, bullets: bool = False) -> str | None:
    values = _items(value)
    if not values:
        return None
    if bullets and len(values) > 1:
        return title + ":\n" + "\n".join(f"- {item}." for item in values)
    return title + ":\n" + " ".join(item + "." for item in values)


def _render_text_section(value: Any, typography: Any = None) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if re.search(r"\b(no text|without text|no rendered text|不(?:要|含|显示)文字|无文字)\b", normalized, re.I):
            return "On-image text:\nDo not render any text, letters, numbers, captions, logos, or watermarks."
        body = normalized
    elif isinstance(value, list):
        quoted = [f'"{str(item).strip()}"' for item in value if str(item).strip()]
        body = "Render only the following text, exactly once and verbatim: " + "; ".join(quoted)
    elif isinstance(value, dict):
        exact = value.get("exact") or value.get("copy") or value.get("verbatim") or value.get("content")
        placement = value.get("placement")
        hierarchy = value.get("hierarchy")
        language = value.get("language")
        spelling = value.get("spelling")
        if isinstance(exact, list):
            items = [str(item).strip() for item in exact if str(item).strip()]
        elif exact not in (None, "", [], {}):
            items = [str(exact).strip()]
        else:
            items = []
        if items:
            quoted = "; ".join(f'"{item}"' for item in items)
            body = f"Render only this copy, exactly and verbatim: {quoted}."
        else:
            body = _text(value)
        extras = []
        if language:
            extras.append(f"Language: {_text(language)}")
        if placement:
            extras.append(f"Placement: {_text(placement)}")
        if hierarchy:
            extras.append(f"Hierarchy: {_text(hierarchy)}")
        if spelling:
            extras.append(f"Spelling aid: {_text(spelling)}")
        if extras:
            body += " " + ". ".join(extras) + "."
    else:
        body = _text(value)
    if typography:
        body = body.rstrip(".") + f". Typography: {_text(typography)}."
    return "On-image text:\n" + body.rstrip() + ("" if body.rstrip().endswith(".") else ".")


def build_prompt(
    brief: dict[str, Any],
    *,
    profile: str = "auto",
    operation: str | None = None,
) -> str:
    if not isinstance(brief, dict):
        raise ValueError("The brief must be a JSON object.")
    selected, operation = resolve_prompt_context(brief, profile=profile, operation=operation)

    deliverable = _first(brief, "deliverable", "output", "asset")
    purpose = _first(brief, "purpose", "intended_use", "goal", "objective")
    audience = _first(brief, "audience", "target_audience")

    if operation == "edit" or selected in {"edit", "composite", "translation"}:
        opening = "Edit the provided image or images."
        if deliverable:
            opening += f" Target asset: {_text(deliverable).rstrip('.')}."
    else:
        opening = (
            f"Create the following asset: {_text(deliverable).rstrip('.')}."
            if deliverable
            else "Create a polished image."
        )
    if purpose:
        opening += f" Intended use: {_text(purpose).rstrip('.')}."
    if audience:
        opening += f" Intended audience: {_text(audience).rstrip('.')}."

    sections: list[str] = [opening]

    if operation == "edit" or selected in {"edit", "composite", "translation"}:
        candidates = [
            _section("Reference-image roles", _first(brief, "references", "reference_roles"), bullets=True),
            _section("Preserve exactly", _first(brief, "preserve", "invariants", "keep"), bullets=True),
            _section("Text replacement map", _first(brief, "translation", "replacement_text", "text_map"), bullets=True),
            _section("Change only", _first(brief, "changes", "change", "edit", "requested_changes"), bullets=True),
            _section("Scene and integration", _first(brief, "scene", "background", "environment", "integration")),
            _section("Composition and geometry", _first(brief, "composition", "layout", "camera", "viewpoint")),
            _section("Visual treatment", [
                _first(brief, "visual_style", "style"),
                _first(brief, "medium"),
                _first(brief, "materials"),
                _first(brief, "rendering"),
            ]),
            _section("Lighting and color", [
                _first(brief, "lighting"),
                _first(brief, "palette", "color_palette"),
            ]),
        ]
    else:
        candidates = [
            _section("Scene and background", _first(brief, "scene", "background", "environment")),
            _section("Main subject", _first(brief, "subject", "subjects", "main_subject")),
            _section("Action and interaction", _first(brief, "action", "pose", "interaction")),
            _section("Key visual details", _first(brief, "key_details", "details", "objects", "supporting_elements"), bullets=True),
            _section("Composition and hierarchy", _first(brief, "composition", "layout", "framing", "spatial_relationships")),
            _section("Camera and viewpoint", _first(brief, "camera", "viewpoint", "perspective")),
            _section("Visual treatment", [
                _first(brief, "visual_style", "style"),
                _first(brief, "medium"),
                _first(brief, "materials"),
                _first(brief, "rendering"),
            ]),
            _section("Lighting and color", [
                _first(brief, "lighting"),
                _first(brief, "palette", "color_palette"),
            ]),
            _section("Reference-image roles", _first(brief, "references", "reference_roles"), bullets=True),
        ]

    for candidate in candidates:
        if candidate:
            sections.append(candidate)

    text_section = _render_text_section(
        _first(brief, "text", "on_image_text", "copy", "typography_text"),
        _first(brief, "typography", "type_style"),
    )
    if text_section:
        sections.append(text_section)

    requirements = _items(_first(brief, "constraints", "requirements"))
    exclusions = _items(_first(brief, "avoid", "exclusions", "do_not"))
    if requirements:
        sections.append("Requirements:\n" + "\n".join(f"- {item}." for item in requirements))
    if exclusions:
        sections.append("Exclusions:\n" + "\n".join(f"- Do not include {item}." for item in exclusions))

    known = {
        "profile", "task", "type", "operation", "deliverable", "output", "asset", "purpose", "intended_use",
        "goal", "objective", "audience", "target_audience", "scene", "background", "environment", "subject",
        "subjects", "main_subject", "action", "pose", "interaction", "key_details", "details", "objects",
        "supporting_elements", "composition", "layout", "framing", "spatial_relationships", "camera", "viewpoint",
        "perspective", "visual_style", "style", "medium", "materials", "rendering", "lighting", "palette",
        "color_palette", "references", "reference_roles", "preserve", "invariants", "keep", "changes", "change",
        "edit", "requested_changes", "integration", "text", "on_image_text", "copy", "typography_text",
        "typography", "type_style", "constraints", "requirements", "avoid", "exclusions", "do_not", "translation",
        "replacement_text", "text_map",
    }
    extras = [(key, value) for key, value in brief.items() if key not in known and value not in (None, "", [], {})]
    if extras:
        sections.append(
            "Additional direction:\n"
            + "\n".join(f"- {key.replace('_', ' ').capitalize()}: {_text(value)}." for key, value in extras)
        )

    prompt = "\n\n".join(section.strip() for section in sections if section and section.strip()).strip()
    if not prompt or prompt == "Create a polished image.":
        raise ValueError("The brief contains no usable prompt fields.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"The compiled prompt exceeds {MAX_PROMPT_CHARS:,} characters.")
    return prompt




def infer_profile_from_prompt(prompt: str, operation: str = "generate", image_count: int = 0) -> str:
    lower = " ".join(prompt.lower().split())
    if operation == "edit":
        if re.search(r"\btranslate|locali[sz]e|replacement map\b|翻译|本地化", lower):
            return "translation"
        if image_count > 1 and re.search(r"\b(image|reference)\s*[1-9]|第[一二三四五六七八九]张图", lower):
            return "composite"
        return "edit"
    checks = (
        ("project-hero", ("repository hero", "github readme", "repo cover", "social preview", "open-source project")),
        ("academic-diagram", ("academic diagram", "mechanism diagram", "architecture diagram", "framework diagram", "scientific diagram")),
        ("infographic", ("infographic", "educational visual", "visual explainer", "timeline")),
        ("ui-mockup", ("ui mockup", "interface mockup", "dashboard", "mobile app ui", "desktop ui")),
        ("character-sheet", ("character sheet", "turnaround", "expression sheet")),
        ("ip-character", ("ip character", "mascot", "brand character")),
        ("logo", ("logo mark", "logomark", "brand mark", "app icon")),
        ("comic", ("comic", "manga", "panel 1", "storyboard")),
        ("product", ("product mockup", "product render", "packaging", "ecommerce")),
        ("ad", ("advertisement", "campaign image", "launch poster", "social media poster")),
        ("photorealistic", ("photorealistic", "real photograph", "professional photography", "shot on", "camera")),
        ("illustration", ("illustration", "watercolor", "vector art", "3d render", "clay render")),
    )
    for candidate, markers in checks:
        if any(marker in lower for marker in markers):
            return candidate
    return "general"


def _contains_text_request(prompt: str) -> bool:
    if re.search(r"\b(no text|without text|do not render any text)\b|无文字|不要文字", prompt, re.I):
        return False
    candidate = re.sub(
        r"\b(?:do not|don't|without|no)\b[^.\n]{0,180}\b(?:text|title|headline|tagline|caption|label|copy|typography|lettering|wordmark)\b[^.\n]*",
        "",
        prompt,
        flags=re.I,
    )
    active_patterns = (
        r"(?mi)^On-image text:\s*(?!Do not render)",
        r"\b(render|write|display|show|include|add|place|set|use)\b.{0,100}\b(text|title|headline|tagline|caption|label|copy|typography|lettering|wordmark)\b",
        r"\bwith\s+(?:the\s+)?(?:exact\s+)?(?:text|title|headline|tagline|caption|label|copy|wordmark)\b",
        r"(?:渲染|写入|显示|添加|放置|使用).{0,50}(?:文字|标题|标语|标签|文案|字标)",
    )
    return any(re.search(pattern, candidate, re.I) for pattern in active_patterns)


def _has_exact_copy(prompt: str) -> bool:
    return bool(re.search(r'["“”][^"“”]{1,300}["“”]', prompt)) or bool(
        re.search(r"\bverbatim\s*:\s*[^\n]{1,300}", prompt, re.I)
    )


def _mentions_text_content(prompt: str) -> bool:
    return bool(
        re.search(
            r"\b(text|title|headline|tagline|caption|label|copy|typography|lettering|wordmark|verbatim)\b|"
            r"文字|标题|标语|标签|文案|排版",
            prompt,
            re.I,
        )
    )


def _keyword_pile(prompt: str) -> bool:
    compact = " ".join(prompt.split())
    comma_count = compact.count(",")
    sentence_count = len(re.findall(r"[.!?。！？\n]", prompt))
    verbish = bool(re.search(r"\b(create|show|place|preserve|change|render|use|keep|include|replace)\b", prompt, re.I))
    return len(compact) > 180 and comma_count >= 12 and sentence_count <= 2 and not verbish


def lint_prompt(
    prompt: str,
    *,
    operation: str = "generate",
    profile: str = "auto",
    model: str = "gpt-image-2",
    model_family: str = "auto",
    image_count: int = 0,
    has_mask: bool = False,
    quality: str = "auto",
    size: str = "auto",
    background: str = "auto",
) -> PromptReview:
    text = prompt.strip()
    operation = operation.strip().lower()
    if operation not in {"generate", "edit"}:
        raise ValueError("operation must be generate or edit.")
    selected = normalize_profile(profile)
    if selected == "auto":
        selected = infer_profile_from_prompt(text, operation, image_count)

    issues: list[PromptIssue] = []
    lower = text.lower()
    normalized_model = model.strip().lower()
    is_image2 = model_family == "gpt-image-2" or (
        model_family == "auto"
        and (normalized_model == "gpt-image-2" or normalized_model.startswith("gpt-image-2-"))
    )
    text_requested = _contains_text_request(text)
    exact_copy = _has_exact_copy(text)
    no_text = bool(re.search(r"\b(no text|without text|do not render any text)\b|无文字|不要文字", text, re.I))
    mentions_text = _mentions_text_content(text)

    if not text:
        issues.append(PromptIssue("empty", "error", "The prompt is empty."))
    elif len(text) > MAX_PROMPT_CHARS:
        issues.append(
            PromptIssue(
                "too-long",
                "error",
                f"The prompt exceeds the {MAX_PROMPT_CHARS:,}-character limit.",
                "Remove repeated style adjectives and keep only task-relevant direction.",
            )
        )

    old_hits = [cue for cue in _OLD_STYLE_CUES if cue in lower]
    if old_hits:
        issues.append(
            PromptIssue(
                "legacy-quality-suffix",
                "warning",
                "The prompt uses legacy quality-suffix language: " + ", ".join(old_hits) + ".",
                "Replace generic quality incantations with concrete material, lighting, composition, and intended-use decisions.",
            )
        )
    if _keyword_pile(text):
        issues.append(
            PromptIssue(
                "keyword-pile",
                "warning",
                "The prompt looks like a dense keyword list rather than a maintainable creative brief.",
                "Use short labeled sections in a stable order: scene, subject, key details, composition, visual treatment, text, constraints.",
            )
        )

    if selected == "photorealistic" and not re.search(
        r"\b(photorealistic|real photograph|professional photography|iphone photo|shot on|camera)\b", text, re.I
    ):
        issues.append(
            PromptIssue(
                "photorealism-not-explicit",
                "warning",
                "A photorealistic task should explicitly request photorealism or a real-camera look.",
                "Add a direct phrase such as 'photorealistic candid photograph' and describe natural texture and lighting.",
            )
        )

    if operation == "edit":
        if not re.search(r"\b(preserve|keep|unchanged|do not change|same)\b|保持|保留|不改变|不修改", text, re.I):
            issues.append(
                PromptIssue(
                    "missing-edit-invariants",
                    "warning",
                    "The edit prompt does not state what must remain unchanged.",
                    "List identity, geometry, layout, camera angle, lighting, labels, or other invariants explicitly.",
                )
            )
        if not re.search(r"\b(change only|replace only|only change|edit only|do not change anything else)\b|仅修改|只替换|只改变", text, re.I):
            issues.append(
                PromptIssue(
                    "edit-scope-not-surgical",
                    "warning",
                    "The edit scope is not bounded with a 'change only X' instruction.",
                    "State the exact change, then add 'keep everything else the same.'",
                )
            )
        if image_count > 1 and not re.search(r"\b(image|reference)\s*[1-9]|第[一二三四五六七八九]张图", text, re.I):
            issues.append(
                PromptIssue(
                    "multi-image-roles-missing",
                    "warning",
                    "Multiple input images are supplied, but the prompt does not assign each image a role.",
                    "Identify inputs explicitly, for example: Image 1 = primary canvas; Image 2 = style reference.",
                )
            )
        if has_mask and not re.search(r"\b(mask|masked|selected region|transparent area|edit region)\b|蒙版|选区|透明区域", text, re.I):
            issues.append(
                PromptIssue(
                    "mask-role-unstated",
                    "warning",
                    "A mask is supplied, but the prompt does not describe the intended masked-region edit.",
                    "State what should change inside the masked area and what outside it must remain unchanged.",
                )
            )

    if selected in {"infographic", "academic-diagram"}:
        if not re.search(r"\b(column|row|panel|node|arrow|left|right|top|bottom|grid|flow)\b|列|行|面板|节点|箭头|从左到右", text, re.I):
            issues.append(
                PromptIssue(
                    "diagram-layout-underspecified",
                    "warning",
                    "The structured visual lacks explicit layout or flow direction.",
                    "Specify columns/panels, arrow direction, label language, spacing, and visual hierarchy.",
                )
            )
    if selected == "comic" and not re.search(r"\bpanel\s*1|第 ?1 ?格|第一格", text, re.I):
        issues.append(
            PromptIssue(
                "comic-beats-missing",
                "warning",
                "The comic prompt does not define panel-by-panel visual beats.",
                "Describe one concrete action beat per panel and keep the character description invariant.",
            )
        )
    if selected == "ui-mockup" and re.search(r"\bconcept art|fantasy interface|sci-fi hud\b", text, re.I):
        issues.append(
            PromptIssue(
                "ui-concept-art-language",
                "warning",
                "Concept-art language can make a UI mockup look decorative instead of usable.",
                "Describe the product as a real shipped interface with layout, hierarchy, spacing, and actual controls.",
            )
        )

    if selected == "project-hero":
        if not re.search(r"\b(repository|github|readme|social preview|hero|project)\b|仓库|项目头图|开源项目", text, re.I):
            issues.append(
                PromptIssue(
                    "project-surface-missing",
                    "warning",
                    "The project-hero prompt does not state the repository or launch surface.",
                    "Name the intended surface, such as GitHub README header, repository social preview, or launch card.",
                )
            )
        if text_requested and not re.search(r"\b(negative space|text-safe|safe region|left|right|center|top|bottom)\b|留白|文字安全区|左侧|右侧|居中", text, re.I):
            issues.append(
                PromptIssue(
                    "project-text-zone-missing",
                    "warning",
                    "The project hero requests text without defining a text-safe placement region.",
                    "Reserve a specific quiet region and define social-card crop margins.",
                )
            )
    if selected == "logo" and not re.search(
        r"\b(silhouette|small size|32 ?px|favicon|app icon|redraw|figure-ground|simple geometric)\b|剪影|小尺寸|图标|易于重绘",
        text,
        re.I,
    ):
        issues.append(
            PromptIssue(
                "logo-scalability-missing",
                "warning",
                "The logo prompt does not address small-size readability or redrawable shape language.",
                "Specify a distinctive silhouette, limited detail, strong figure-ground separation, and target icon sizes.",
            )
        )
    if selected == "ip-character" and not re.search(
        r"\b(silhouette|proportion|shape language|signature motif|distinctive|body shape)\b|轮廓|比例|造型语言|标志性",
        text,
        re.I,
    ):
        issues.append(
            PromptIssue(
                "character-identity-underspecified",
                "warning",
                "The IP character prompt lacks stable identity anchors.",
                "Define silhouette, proportions, face language, signature motif, palette, and no-go features.",
            )
        )
    if selected == "character-sheet" and not re.search(
        r"\b(front view|side view|back view|three-quarter|turnaround|expression)\b|正面|侧面|背面|三视图|表情",
        text,
        re.I,
    ):
        issues.append(
            PromptIssue(
                "character-sheet-views-missing",
                "warning",
                "The character-sheet prompt does not define required views or expressions.",
                "List front, side, back, three-quarter, expression, and consistency requirements.",
            )
        )
    if selected == "translation":
        if not re.search(r"\b(replacement map|translate only|source|target)\b|替换表|仅翻译|源文本|目标文本", text, re.I):
            issues.append(
                PromptIssue(
                    "translation-map-missing",
                    "warning",
                    "The localization prompt does not provide a bounded source-to-target replacement map.",
                    "Quote each source string and exact target string, then preserve typography and all non-text elements.",
                )
            )
        if not re.search(r"\b(typography|placement|spacing|layout|preserve)\b|字体|位置|间距|布局|保持", text, re.I):
            issues.append(
                PromptIssue(
                    "translation-invariants-missing",
                    "warning",
                    "The localization prompt does not preserve typography and layout invariants.",
                    "State that typography style, placement, hierarchy, spacing, imagery, icons, and crop must remain unchanged.",
                )
            )

    if text_requested and not exact_copy:
        issues.append(
            PromptIssue(
                "text-not-verbatim",
                "warning",
                "The prompt appears to request text but does not quote the exact copy.",
                "Put literal copy in quotation marks, request verbatim rendering exactly once, and forbid extra text.",
            )
        )
    if text_requested and quality == "low":
        issues.append(
            PromptIssue(
                "text-low-quality",
                "warning",
                "Low quality is risky for small or dense in-image text.",
                "Compare medium or high quality before shipping text-heavy assets.",
            )
        )
    if no_text and mentions_text and re.search(r'["“”][^"“”]{1,300}["“”]', text):
        issues.append(
            PromptIssue(
                "text-conflict",
                "warning",
                "The prompt contains both a no-text instruction and language that may request rendered text.",
                "Separate layout placeholders from actual rendered copy and state the final intent once.",
            )
        )

    if is_image2 and (background == "transparent" or "transparent background" in lower):
        issues.append(
            PromptIssue(
                "transparent-unsupported",
                "error",
                "Official gpt-image-2 does not support transparent output backgrounds.",
                "Generate on an opaque/plain background and remove it downstream when transparency is required.",
            )
        )

    if re.search(r"\bnegative[_ -]?prompt\b", text, re.I):
        issues.append(
            PromptIssue(
                "negative-prompt-syntax",
                "warning",
                "GPT Image 2 does not require a separate negative-prompt syntax inside the prompt.",
                "Write natural constraints such as 'Do not include watermarks, extra text, or unrelated logos.'",
            )
        )

    status = "fail" if any(issue.severity == "error" for issue in issues) else (
        "warn" if any(issue.severity == "warning" for issue in issues) else "pass"
    )
    features = {
        "characters": len(text),
        "has_labeled_sections": bool(re.search(r"(?m)^[A-Za-z][^\n:]{1,40}:\s*$", text)),
        "requests_text": text_requested,
        "mentions_text": mentions_text,
        "has_exact_copy": exact_copy,
        "declares_no_text": no_text,
        "image_count": image_count,
        "has_mask": has_mask,
        "quality": quality,
        "size": size,
        "background": background,
        "model": model,
        "model_family": model_family,
    }
    return PromptReview(selected, operation, status, issues, features)


def read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if bool(prompt) == bool(prompt_file):
        raise ValueError("Provide exactly one of --prompt or --prompt-file.")
    if prompt_file:
        text = Path(prompt_file).read_text(encoding="utf-8")
    else:
        text = prompt or ""
    text = text.strip()
    if not text:
        raise ValueError("The prompt is empty.")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValueError(f"The prompt exceeds the {MAX_PROMPT_CHARS:,}-character GPT Image limit.")
    return text


def brief_schema() -> dict[str, Any]:
    string_or_list = {
        "oneOf": [
            {"type": "string"},
            {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
            {"type": "object"},
        ]
    }
    properties: dict[str, Any] = {
        "profile": {"type": "string", "enum": list(PROFILES[1:])},
        "operation": {"type": "string", "enum": ["generate", "edit"]},
        "deliverable": {"type": "string", "minLength": 1},
        "purpose": string_or_list,
        "audience": string_or_list,
        "scene": string_or_list,
        "subject": string_or_list,
        "action": string_or_list,
        "key_details": string_or_list,
        "composition": string_or_list,
        "camera": string_or_list,
        "style": string_or_list,
        "materials": string_or_list,
        "lighting": string_or_list,
        "palette": string_or_list,
        "text": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
                {
                    "type": "object",
                    "properties": {
                        "exact": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ]
                        },
                        "placement": {"type": "string"},
                        "hierarchy": {"type": "string"},
                        "language": {"type": "string"},
                        "spelling": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            ]
        },
        "typography": string_or_list,
        "references": string_or_list,
        "preserve": string_or_list,
        "translation": string_or_list,
        "changes": string_or_list,
        "constraints": string_or_list,
        "avoid": string_or_list,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://techdou.com/schemas/image2-prompt-brief.schema.json",
        "title": "GPT Image 2 prompt brief",
        "type": "object",
        "minProperties": 1,
        "properties": properties,
        "additionalProperties": True,
    }
