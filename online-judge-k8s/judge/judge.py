import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine, text

PROBLEM_ID = os.getenv("PROBLEM_ID", "sum")
LANGUAGE = os.getenv("LANGUAGE", "python")
TIME_LIMIT_SEC = float(os.getenv("TIME_LIMIT_SEC", "2"))
COMPILE_LIMIT_SEC = float(os.getenv("COMPILE_LIMIT_SEC", "10"))
WORKDIR = Path(os.getenv("WORKDIR", "/work"))
APPDIR = Path(os.getenv("APPDIR", "/app"))

TASK_ID = os.getenv("TASK_ID")
DB_USER = os.getenv("POSTGRES_USER", "judge_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "judge_pass")
DB_HOST = os.getenv("POSTGRES_HOST", "online-judge-db")
DB_NAME = os.getenv("POSTGRES_DB", "online_judge")


def normalize_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def emit_result(
    status: str,
    stdout: str = "",
    stderr: str = "",
    time_ms: int = 0,
    passed_cases: int = 0,
    total_cases: int = 0,
    failed_case: str | None = None,
    case_results: list[dict] | None = None,
):
    result_dict = {
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "time_ms": time_ms,
        "problem_id": PROBLEM_ID,
        "language": LANGUAGE,
        "passed_cases": passed_cases,
        "total_cases": total_cases,
        "failed_case": failed_case,
        "cases": case_results or [],
    }
    
    result_json = json.dumps(result_dict, ensure_ascii=False)
    
    print(result_json)
    
    # DB에 결과 저장 (프론트엔드 상태 동기화 패치 적용!)
    if TASK_ID:
        db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
        try:
            engine = create_engine(db_url)
            with engine.begin() as conn:
                # 프론트엔드 폴링 종료를 위해 DB status 컬럼은 'Completed'나 'Error'로 고정
                job_status = "Failed" if status in ["Judge Error", "Compilation Error"] else "Succeeded"
                
                conn.execute(
                    text("UPDATE submissions SET status = :status, result = :res WHERE task_id = :tid"),
                    {"status": job_status, "res": result_json, "tid": TASK_ID}
                )
            print(f"[{TASK_ID}] Successfully saved result to DB.", file=sys.stderr)
        except Exception as e:
            print(f"[{TASK_ID}] Failed to save to DB: {e}", file=sys.stderr)


def load_test_cases():
    problem_dir = APPDIR / "problems" / PROBLEM_ID

    if not problem_dir.exists():
        emit_result("Judge Error", stderr=f"Problem directory not found: {problem_dir}")
        sys.exit(1)

    in_files = sorted(problem_dir.glob("*.in"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)

    if not in_files:
        input_path = problem_dir / "input.txt"
        answer_path = problem_dir / "answer.txt"

        if input_path.exists() and answer_path.exists():
            return [{
                "name": "1",
                "input": input_path.read_text(encoding="utf-8-sig"),
                "answer": answer_path.read_text(encoding="utf-8-sig"),
            }]

        emit_result("Judge Error", stderr=f"No test cases found in: {problem_dir}")
        sys.exit(1)

    cases = []
    for in_path in in_files:
        out_path = problem_dir / f"{in_path.stem}.out"

        if not out_path.exists():
            emit_result("Judge Error", stderr=f"Answer file not found: {out_path}")
            sys.exit(1)

        cases.append({
            "name": in_path.stem,
            "input": in_path.read_text(encoding="utf-8-sig"),
            "answer": out_path.read_text(encoding="utf-8-sig"),
        })

    return cases


def run_python(code_path: Path, input_data: str):
    return subprocess.run(
        [sys.executable, str(code_path)],
        input=input_data,
        text=True,
        capture_output=True,
        timeout=TIME_LIMIT_SEC,
        cwd=str(code_path.parent),
    )


def compile_cpp(code_path: Path):
    exe_path = code_path.parent / "main"

    compile_proc = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-pipe", str(code_path), "-o", str(exe_path)],
        text=True,
        capture_output=True,
        timeout=COMPILE_LIMIT_SEC,
        cwd=str(code_path.parent),
    )

    if compile_proc.returncode != 0:
        return None, compile_proc.stdout, compile_proc.stderr

    return exe_path, compile_proc.stdout, compile_proc.stderr


def run_cpp(exe_path: Path, input_data: str):
    return subprocess.run(
        [str(exe_path)],
        input=input_data,
        text=True,
        capture_output=True,
        timeout=TIME_LIMIT_SEC,
        cwd=str(exe_path.parent),
    )


def make_case_result(case: dict, output: str, status: str) -> dict:
    return {
        "case": case["name"],
        "input": case["input"],
        "expected": case["answer"],
        "output": output,
        "status": status,
    }


def main():
    test_cases = load_test_cases()

    extension = "py" if LANGUAGE == "python" else "cpp"
    submitted_code = os.getenv("SUBMITTED_CODE")

    with tempfile.TemporaryDirectory(dir=str(WORKDIR) if WORKDIR.exists() else None) as temp_dir:
        code_path = Path(temp_dir) / f"submission.{extension}"

        if submitted_code:
            code_path.write_text(submitted_code, encoding="utf-8")
        else:
            fallback = APPDIR / f"submission.{extension}"
            if not fallback.exists():
                emit_result(
                    "Judge Error",
                    stderr="No submitted code found. Set SUBMITTED_CODE env or mount submission file.",
                    total_cases=len(test_cases),
                )
                return
            code_path.write_text(fallback.read_text(encoding="utf-8-sig"), encoding="utf-8")

        exe_path = None

        if LANGUAGE == "cpp":
            try:
                exe_path, compile_stdout, compile_stderr = compile_cpp(code_path)
            except subprocess.TimeoutExpired:
                emit_result(
                    "Compilation Timeout",
                    stderr=f"Compile limit {COMPILE_LIMIT_SEC}s exceeded",
                    total_cases=len(test_cases),
                )
                return
            except Exception as exc:
                emit_result(
                    "Judge Error",
                    stderr=str(exc),
                    total_cases=len(test_cases),
                )
                return

            if exe_path is None:
                emit_result(
                    "Compilation Error",
                    stdout=compile_stdout,
                    stderr=compile_stderr,
                    total_cases=len(test_cases),
                )
                return

        elif LANGUAGE != "python":
            emit_result(
                "Judge Error",
                stderr=f"Unsupported language: {LANGUAGE}",
                total_cases=len(test_cases),
            )
            return

        passed = 0
        total_time_ms = 0
        last_stdout = ""
        last_stderr = ""
        case_results = []

        for case in test_cases:
            start = time.perf_counter()

            try:
                if LANGUAGE == "python":
                    proc = run_python(code_path, case["input"])
                else:
                    proc = run_cpp(exe_path, case["input"])

                elapsed_ms = int((time.perf_counter() - start) * 1000)
                total_time_ms += elapsed_ms
                last_stdout = proc.stdout
                last_stderr = proc.stderr

            except subprocess.TimeoutExpired:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                total_time_ms += elapsed_ms

                case_results.append(make_case_result(
                    case=case,
                    output="",
                    status="Time Limit Exceeded",
                ))

                emit_result(
                    "Time Limit Exceeded",
                    stderr=f"Time limit {TIME_LIMIT_SEC}s exceeded on case {case['name']}",
                    time_ms=total_time_ms,
                    passed_cases=passed,
                    total_cases=len(test_cases),
                    failed_case=case["name"],
                    case_results=case_results,
                )
                return

            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                total_time_ms += elapsed_ms

                case_results.append(make_case_result(
                    case=case,
                    output="",
                    status="Judge Error",
                ))

                emit_result(
                    "Judge Error",
                    stderr=str(exc),
                    time_ms=total_time_ms,
                    passed_cases=passed,
                    total_cases=len(test_cases),
                    failed_case=case["name"],
                    case_results=case_results,
                )
                return

            if proc.returncode != 0:
                is_oom = (proc.returncode == -9 or proc.returncode == 137)
                status_str = "Memory Limit Exceeded" if is_oom else "Runtime Error"
                err_msg = "Memory limit exceeded (OOMKilled)" if is_oom else proc.stderr

                case_results.append(make_case_result(
                    case=case,
                    output=proc.stdout,
                    status=status_str,
                ))

                emit_result(
                    status_str,
                    stdout=proc.stdout,
                    stderr=err_msg,
                    time_ms=total_time_ms,
                    passed_cases=passed,
                    total_cases=len(test_cases),
                    failed_case=case["name"],
                    case_results=case_results,
                )
                return

            actual = normalize_output(proc.stdout)
            expected = normalize_output(case["answer"])

            if actual != expected:
                case_results.append(make_case_result(
                    case=case,
                    output=proc.stdout,
                    status="Wrong Answer",
                ))

                emit_result(
                    "Wrong Answer",
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    time_ms=total_time_ms,
                    passed_cases=passed,
                    total_cases=len(test_cases),
                    failed_case=case["name"],
                    case_results=case_results,
                )
                return

            case_results.append(make_case_result(
                case=case,
                output=proc.stdout,
                status="Accepted",
            ))

            passed += 1

        emit_result(
            "Accepted",
            stdout=last_stdout,
            stderr=last_stderr,
            time_ms=total_time_ms,
            passed_cases=passed,
            total_cases=len(test_cases),
            failed_case=None,
            case_results=case_results,
        )


if __name__ == "__main__":
    main()