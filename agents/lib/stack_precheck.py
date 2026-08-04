# harness-init Phase 2-1 전, LLM 호출 없이 초저비용으로 결정론적 인덱스 추출기 적용 대상 스택인지 감지
import os
import sys
import json
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from now_kst import now_kst

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "out", ".idea", ".vscode", "__pycache__"}
BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")
SPRING_MARKERS = ("org.springframework", "spring-boot", "spring-context", "spring-webmvc")


def _walk_files(root, names_or_suffix, max_files=4000):
    """SKIP_DIRS를 건너뛰며 root 하위를 훑어 이름이 일치하거나(집합) 확장자가 일치하는(문자열)
    파일 경로를 최대 max_files개까지 수집한다."""
    found = []
    is_suffix = isinstance(names_or_suffix, str)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if (is_suffix and fn.endswith(names_or_suffix)) or (not is_suffix and fn in names_or_suffix):
                found.append(os.path.join(dirpath, fn))
                if len(found) >= max_files:
                    return found
    return found


def detect(root):
    evidence = []
    build_files = _walk_files(root, BUILD_FILES, max_files=20)
    if not build_files:
        return {"extractor": "none", "evidence": ["Maven/Gradle 빌드 파일 없음"]}
    evidence.append(f"빌드 파일 발견: {os.path.relpath(build_files[0], root)}")

    spring_hit = None
    for bf in build_files:
        try:
            with open(bf, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        if any(marker in text for marker in SPRING_MARKERS):
            spring_hit = os.path.relpath(bf, root)
            break

    if not spring_hit:
        # 빌드 파일에 없으면 .java 파일 샘플(최대 30개)에서 import 확인
        java_files = _walk_files(root, ".java", max_files=30)
        for jf in java_files:
            try:
                with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(4000)
            except OSError:
                continue
            if "org.springframework" in text:
                spring_hit = os.path.relpath(jf, root)
                break

    if not spring_hit:
        return {"extractor": "none", "evidence": evidence + ["Spring 관련 마커 미발견"]}

    evidence.append(f"Spring 마커 발견: {spring_hit}")
    return {"extractor": "java_spring", "evidence": evidence}


def main():
    parser = argparse.ArgumentParser(description="결정론적 인덱스 추출기 적용 대상 스택 사전 감지 (LLM 미사용)")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    result = detect(args.root)
    result["_meta"] = {"generated_at": now_kst(), "generator": "stack_precheck"}

    out_dir = os.path.join(args.root, "_workspace")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "00_stack_precheck.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"extractor={result['extractor']}")
    for e in result["evidence"]:
        print(f"  - {e}")


if __name__ == "__main__":
    main()
