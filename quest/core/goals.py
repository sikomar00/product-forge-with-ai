"""졸업 기준 13개 영역(IA-10, design.md 2.2절).

2026-11-13 결정: 콘텐츠의 content.toml [goals]에 영역마다 미션 키 목록을 두고, 그 미션을
모두 '통과'하면 충족이다. 승급 시험으로 면제된 미션은 인정하지 않는다. 졸업 기준은 실제
산출물 검사라서다. 면제된 미션은 quest mission <ID>로 직접 하면 통과로 바뀐다.
"""

# 영역 ID → 화면 이름. 이름과 순서는 design.md 2.2절(공개)을 따른다.
AREAS = {
    "ai_collab": "AI 협업",
    "planning": "기획",
    "design": "설계",
    "backend": "백엔드",
    "async": "비동기",
    "frontend": "프론트엔드",
    "testing": "테스트",
    "git_cicd": "Git·CI/CD",
    "deploy": "배포",
    "ops": "운영",
    "security": "보안",
    "ai_product": "제품 안의 AI",
    "analytics": "분석·개선",
}


def goal_errors(goals: object, mission_keys: set[str]) -> list[str]:
    """content.toml [goals]의 모양 검사. 콘텐츠를 불러올 때 쓴다."""
    if not isinstance(goals, dict):
        return ["content.toml [goals]는 표여야 합니다"]
    errors = []
    for area, keys in goals.items():
        if area not in AREAS:
            errors.append(f"[goals] 알 수 없는 영역: {area!r}")
        elif not isinstance(keys, list) or not keys:
            errors.append(f"[goals] {area}: 미션 키 목록이 비었거나 목록이 아닙니다")
        else:
            errors += [f"[goals] {area}: 콘텐츠에 없는 미션 키 {k!r}" for k in keys
                       if k not in mission_keys]
    return errors


def area_status(keys: tuple[str, ...], status: dict[str, str]) -> tuple[int, list[str]]:
    """(통과한 미션 수, 면제돼서 아직 인정되지 않은 미션 키 목록)."""
    passed = sum(status.get(k) == "passed" for k in keys)
    return passed, [k for k in keys if status.get(k) == "exempted"]
