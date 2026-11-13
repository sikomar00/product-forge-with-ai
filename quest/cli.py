"""quest 명령의 입구. 명령 해석(IA-1~IA-20)은 T0-4부터 채운다."""

from importlib.metadata import version


def main() -> int:
    print(f"quest {version('quest')}")
    return 0
