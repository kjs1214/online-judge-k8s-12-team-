import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

BACKEND_URL = "http://localhost:8000/submit"
TOTAL_SUBMISSIONS = 200  
CONCURRENT_WORKERS = 16  

# Time Limit Exceeded 코드를 제외한 3가지 유형만 유지
CODE_TEMPLATES = {
    "Accepted": "a, b = map(int, input().split())\nprint(a + b)",
    "Wrong Answer": "print(999)",
    "Runtime Error": "a = 1 / 0\nprint(a)"
}

TYPE_KEYS = list(CODE_TEMPLATES.keys())

def send_submission(index):
    """인덱스에 따라 서로 다른 결과가 나오는 코드를 발송합니다."""
    # 남은 3가지 유형이 % 3으로 자동 순환 선택됩니다.
    expected_result = TYPE_KEYS[index % len(TYPE_KEYS)]
    target_code = CODE_TEMPLATES[expected_result]
    
    payload = {
        "problem_id": "sum",
        "language": "python",
        "code": target_code
    }
    
    try:
        start_time = time.time()
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(BACKEND_URL, data=json.dumps(payload), headers=headers, timeout=5)
        
        if response.status_code == 200:
            res_data = response.json()
            print(f"[{index+1:02d}/{TOTAL_SUBMISSIONS}] 유형: [{expected_result:^20}] | ID: {res_data.get('submission_id')}")
            return {
                "id": res_data.get('submission_id'),
                "type": expected_result
            }
        else:
            print(f"[{index+1:02d}/{TOTAL_SUBMISSIONS}] 발송 실패... 상태 코드: {response.status_code}")
    except Exception as e:
        print(f"[{index+1:02d}/{TOTAL_SUBMISSIONS}] 에러 발생: {e}")
    return None

def main():
    try:
        requests.get("http://localhost:8000/docs", timeout=2)
    except requests.exceptions.ConnectionError:
        print("에러: 백엔드 서버(8000 포트)가 닫혀있습니다. 포트포워딩을 확인하세요")
        return

    start_bulk = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        results = list(executor.map(send_submission, range(TOTAL_SUBMISSIONS)))

    print("=" * 65)
    print(f"Completed! 소요 시간: {time.time() - start_bulk:.2f}초")
    print("=" * 65)

if __name__ == "__main__":
    main()