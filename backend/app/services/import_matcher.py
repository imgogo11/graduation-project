from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any
import unicodedata

import pandas as pd


try:
    from rapidfuzz import fuzz  # type: ignore[import-not-found]

    RAPIDFUZZ_AVAILABLE = True
except Exception:  # pragma: no cover - exercised in environments without rapidfuzz
    fuzz = None
    RAPIDFUZZ_AVAILABLE = False


HEADER_WEIGHT = 0.65
VALUE_WEIGHT = 0.35
TEMPLATE_BONUS = 0.10
HIGH_CONFIDENCE_THRESHOLD = 0.90
MEDIUM_CONFIDENCE_THRESHOLD = 0.72
CONFLICT_GAP_THRESHOLD = 0.10
MIN_CANDIDATE_SCORE = 0.20
SAMPLE_LIMIT = 300

NUMERIC_COLUMNS = {"open", "high", "low", "close", "volume", "amount", "turnover"}
STOCK_CODE_PATTERN = re.compile(r"^\d{6}\.(?:SH|SZ|BJ)$", re.IGNORECASE)
GENERIC_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9._-]{1,15}$")
NUMERIC_CODE_PATTERN = re.compile(r"^\d{6}$")


def normalize_header_token(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    lowered = text.replace("\ufeff", "").strip().lower()
    collapsed = re.sub(r"[\s\-./\\]+", "_", lowered)
    collapsed = re.sub(r"_+", "_", collapsed).strip("_")
    return collapsed


@dataclass(frozen=True, slots=True)
class ColumnCandidate:
    original_column: str
    header_score: float
    value_score: float
    template_bonus: float
    total_score: float
    confidence: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldSuggestion:
    canonical_column: str
    required: bool
    selected_original_column: str | None
    selected_score: float | None
    selected_confidence: str
    candidates: tuple[ColumnCandidate, ...]


@dataclass(frozen=True, slots=True)
class MappingConflict:
    canonical_column: str
    primary_original_column: str
    secondary_original_column: str
    gap: float
    message: str


@dataclass(frozen=True, slots=True)
class ColumnMatchResult:
    matcher_engine: str
    suggested_mapping: dict[str, str]
    field_suggestions: tuple[FieldSuggestion, ...]
    missing_required: tuple[str, ...]
    conflicts: tuple[MappingConflict, ...]
    ignored_columns: tuple[str, ...]
    can_auto_commit: bool
    action_hints: tuple[str, ...]


class ColumnMatcher:
    def __init__(
        self,
        *,
        required_columns: tuple[str, ...],
        optional_columns: tuple[str, ...],
        alias_tiers_by_column: dict[str, dict[str, tuple[str, ...]]],
        template_mapping: dict[str, str] | None = None,
    ):
        self.required_columns = required_columns
        self.optional_columns = optional_columns
        self.canonical_columns = required_columns + tuple(item for item in optional_columns if item not in required_columns)
        self.alias_tiers_by_column = alias_tiers_by_column
        self.template_mapping = template_mapping or {}
        self.matcher_engine = "rapidfuzz" if RAPIDFUZZ_AVAILABLE else "sequence_matcher"

    def match(self, *, original_columns: list[str], sample_values: dict[str, list[Any]]) -> ColumnMatchResult:
        candidate_map: dict[str, list[ColumnCandidate]] = {}
        conflicts: list[MappingConflict] = []
        for canonical in self.canonical_columns:
            candidates = self._build_candidates(
                canonical=canonical,
                original_columns=original_columns,
                sample_values=sample_values,
            )
            candidate_map[canonical] = candidates
            if len(candidates) >= 2:
                gap = candidates[0].total_score - candidates[1].total_score
                if gap < CONFLICT_GAP_THRESHOLD:
                    conflicts.append(
                        MappingConflict(
                            canonical_column=canonical,
                            primary_original_column=candidates[0].original_column,
                            secondary_original_column=candidates[1].original_column,
                            gap=round(max(gap, 0.0), 6),
                            message=(
                                f"{canonical} 的前两名候选列过于接近："
                                f"{candidates[0].original_column} / {candidates[1].original_column}"
                            ),
                        )
                    )

        suggested_mapping = self._choose_unique_mapping(candidate_map)
        missing_required = tuple(column for column in self.required_columns if column not in suggested_mapping)
        ignored_columns = tuple(column for column in original_columns if column not in set(suggested_mapping.values()))

        conflict_columns = {item.canonical_column for item in conflicts}
        required_ready = True
        for required_column in self.required_columns:
            if required_column not in suggested_mapping:
                required_ready = False
                break
            selected = self._find_selected(candidate_map[required_column], suggested_mapping[required_column])
            if selected is None or selected.confidence != "high":
                required_ready = False
                break
            if required_column in conflict_columns:
                required_ready = False
                break

        can_auto_commit = (
            RAPIDFUZZ_AVAILABLE
            and not missing_required
            and required_ready
        )

        action_hints: list[str] = []
        if missing_required:
            action_hints.append("请先补齐必填列映射后再提交。")
        if conflicts:
            action_hints.append("存在列头歧义，请在确认面板手动选择正确映射。")
        if not RAPIDFUZZ_AVAILABLE:
            action_hints.append("当前自动识别能力受限，请人工确认列头映射后再导入。")
        if not action_hints and not can_auto_commit:
            action_hints.append("请检查中低置信度字段，并确认后提交。")
        if can_auto_commit:
            action_hints.append("匹配置信度足够高，可一键确认导入。")

        field_suggestions = tuple(
            self._build_field_suggestion(
                canonical=canonical,
                required=canonical in self.required_columns,
                candidates=candidate_map[canonical],
                selected_original=suggested_mapping.get(canonical),
            )
            for canonical in self.canonical_columns
        )
        return ColumnMatchResult(
            matcher_engine=self.matcher_engine,
            suggested_mapping=suggested_mapping,
            field_suggestions=field_suggestions,
            missing_required=missing_required,
            conflicts=tuple(conflicts),
            ignored_columns=ignored_columns,
            can_auto_commit=can_auto_commit,
            action_hints=tuple(action_hints),
        )

    def _build_candidates(
        self,
        *,
        canonical: str,
        original_columns: list[str],
        sample_values: dict[str, list[Any]],
    ) -> list[ColumnCandidate]:
        output: list[ColumnCandidate] = []
        alias_tiers = self.alias_tiers_by_column.get(canonical, {})
        for original_column in original_columns:
            normalized_original = normalize_header_token(original_column)
            header_score, header_reasons = self._score_header(
                canonical=canonical,
                normalized_original=normalized_original,
                alias_tiers=alias_tiers,
            )
            value_score, value_reasons = self._score_value(canonical, sample_values.get(original_column, []))
            template_bonus = TEMPLATE_BONUS if self.template_mapping.get(canonical) == original_column else 0.0
            if template_bonus > 0:
                value_reasons.append("命中历史用户模板")
            total_score = min(1.0, HEADER_WEIGHT * header_score + VALUE_WEIGHT * value_score + template_bonus)
            if total_score < MIN_CANDIDATE_SCORE:
                continue
            output.append(
                ColumnCandidate(
                    original_column=original_column,
                    header_score=round(header_score, 6),
                    value_score=round(value_score, 6),
                    template_bonus=round(template_bonus, 6),
                    total_score=round(total_score, 6),
                    confidence="low",
                    reasons=tuple(header_reasons + value_reasons),
                )
            )

        output.sort(key=lambda item: item.total_score, reverse=True)
        for index, item in enumerate(output):
            delta = item.total_score - (output[index + 1].total_score if index + 1 < len(output) else 0.0)
            confidence = self._resolve_confidence(item.total_score, delta)
            output[index] = ColumnCandidate(
                original_column=item.original_column,
                header_score=item.header_score,
                value_score=item.value_score,
                template_bonus=item.template_bonus,
                total_score=item.total_score,
                confidence=confidence,
                reasons=item.reasons,
            )
        return output

    def _build_field_suggestion(
        self,
        *,
        canonical: str,
        required: bool,
        candidates: list[ColumnCandidate],
        selected_original: str | None,
    ) -> FieldSuggestion:
        selected = self._find_selected(candidates, selected_original) if selected_original else None
        return FieldSuggestion(
            canonical_column=canonical,
            required=required,
            selected_original_column=selected_original,
            selected_score=selected.total_score if selected else None,
            selected_confidence=selected.confidence if selected else "low",
            candidates=tuple(candidates[:5]),
        )

    def _find_selected(self, candidates: list[ColumnCandidate], selected_original: str) -> ColumnCandidate | None:
        for item in candidates:
            if item.original_column == selected_original:
                return item
        return None

    def _resolve_confidence(self, score: float, delta: float) -> str:
        if score >= HIGH_CONFIDENCE_THRESHOLD and delta >= CONFLICT_GAP_THRESHOLD:
            return "high"
        if score >= MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        return "low"

    def _choose_unique_mapping(self, candidate_map: dict[str, list[ColumnCandidate]]) -> dict[str, str]:
        rows: list[tuple[str, ColumnCandidate]] = []
        for canonical, candidates in candidate_map.items():
            if not candidates:
                continue
            rows.append((canonical, candidates[0]))
        rows.sort(key=lambda item: item[1].total_score, reverse=True)

        used_original_columns: set[str] = set()
        selected: dict[str, str] = {}
        for canonical, _ in rows:
            candidates = candidate_map[canonical]
            for candidate in candidates:
                if candidate.original_column in used_original_columns:
                    continue
                selected[canonical] = candidate.original_column
                used_original_columns.add(candidate.original_column)
                break
        return selected

    def _score_header(
        self,
        *,
        canonical: str,
        normalized_original: str,
        alias_tiers: dict[str, tuple[str, ...]],
    ) -> tuple[float, list[str]]:
        canonical_norm = normalize_header_token(canonical)
        base_similarity = self._string_similarity(canonical_norm, normalized_original)
        reasons = [f"名称相似度={base_similarity:.3f}"]

        alias_score = 0.0
        for tier, tier_score in (("strong", 0.98), ("medium", 0.90), ("weak", 0.78)):
            aliases = alias_tiers.get(tier, ())
            normalized_aliases = {normalize_header_token(item) for item in aliases if normalize_header_token(item)}
            if normalized_original in normalized_aliases:
                alias_score = max(alias_score, tier_score)
                reasons.append(f"命中{tier}等价列头")
        return max(base_similarity, alias_score), reasons

    def _score_value(self, canonical: str, values: list[Any]) -> tuple[float, list[str]]:
        sampled = [value for value in values[:SAMPLE_LIMIT] if value is not None and not pd.isna(value)]
        if not sampled:
            return 0.0, ["样本为空"]

        if canonical == "stock_code":
            score = 0.0
            for item in sampled:
                text = str(item).strip().upper()
                if STOCK_CODE_PATTERN.match(text):
                    score += 1.0
                elif GENERIC_CODE_PATTERN.match(text):
                    score += 0.9
                elif NUMERIC_CODE_PATTERN.match(text):
                    score += 0.8
            ratio = score / len(sampled)
            return ratio, [f"代码模式命中率={ratio:.3f}"]

        if canonical == "trade_date":
            parsed = pd.to_datetime(pd.Series(sampled), errors="coerce", format="mixed")
            ratio = float(parsed.notna().mean())
            return ratio, [f"日期可解析率={ratio:.3f}"]

        if canonical in NUMERIC_COLUMNS:
            parsed = pd.to_numeric(pd.Series(sampled), errors="coerce")
            ratio = float(parsed.notna().mean())
            return ratio, [f"数值可解析率={ratio:.3f}"]

        if canonical == "stock_name":
            non_empty = [str(item).strip() for item in sampled if str(item).strip()]
            ratio = len(non_empty) / len(sampled)
            return ratio * 0.8, [f"文本非空率={ratio:.3f}"]

        return 0.0, ["未配置值特征"]

    def _string_similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if RAPIDFUZZ_AVAILABLE and fuzz is not None:
            ratio = fuzz.ratio(left, right) / 100.0
            token_sort = fuzz.token_sort_ratio(left, right) / 100.0
            token_set = fuzz.token_set_ratio(left, right) / 100.0
            return max(ratio, token_sort, token_set)
        return SequenceMatcher(a=left, b=right).ratio()
