# Kubernetes Online Judge MVP (v2.0)

Kubernetes Job을 이용해 사용자 제출 코드를 독립 Pod에서 실행하고, PostgreSQL을 통해 채점 결과를 안전하게 영구 저장하는 고가용성 온라인 코드 채점 시스템입니다.

사용자가 웹에서 코드를 제출하면 FastAPI 백엔드가 DB에 기록을 남기고 Redis Queue에 작업을 넣습니다. Worker는 Queue에서 요청을 꺼내 Kubernetes Job을 동적으로 생성하며, Judge 컨테이너는 독립 Pod 안에서 제출 코드를 실행한 뒤 그 결과를 직접 DB에 업데이트하고 소멸(TTL)합니다.

---

## 프로젝트 개요

기존 시스템은 K8s 파드의 로그(stdout)를 백엔드가 직접 읽어오는 구조였으나, 파드 소멸 시 결과를 유실하거나 API 부하가 발생하는 치명적인 단점이 있었습니다.

**v2.0 업데이트**를 통해 PostgreSQL DB를 도입하여, 백엔드와 워커, 채점기가 K8s API를 거치지 않고 오직 DB와 Redis를 통해서만 빠르고 안전하게 소통하는 완벽한 클라우드 네이티브 아키텍처로 진화했습니다.

### 핵심 동작 흐름 (v2.0)

```text
1. [웹 제출] → FastAPI Backend
2. Backend → DB에 상태 'Queued'로 저장 & Redis Queue에 작업 Push
3. Worker → Redis에서 작업 Pop (BLPOP)
4. Worker → DB 상태를 'Processing'으로 변경 & K8s Job(Judge v2.0) 동적 생성 (DB 접속 정보 주입)
5. Judge Pod → 독립 환경에서 코드 실행 및 테스트 케이스 채점
6. Judge Pod → 채점 완료 즉시 DB에 결과(JSON) Update 후 종료 (10초 뒤 K8s가 자동 삭제)
7. Backend → 프론트엔드의 폴링 요청 시 DB만 초고속으로 조회하여 결과 반환



## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python FastAPI, SQLAIchemy |
| Database | PostgreSQL 15 |
| Queue | Redis 7 |
| Worker | Python(k8s API Client) |
| Judge | Python, C++, Docker |
| Infrastructure | Docker, Kubernetes |
| Monitoring | Prometheus, Grafana |

---

## 프로젝트 구조

```text
online-judge-k8s/
 ├─ backend/
 │   ├─ main.py         # FastAPI 웹 서버 (DB 읽기/쓰기 전담)
 │   ├─ worker.py       # Redis 큐 소비 및 K8s Job 생성
 │   ├─ database.py     # PostgreSQL 연동 및 테이블 스키마 정의
 │   ├─ models.py       # Pydantic 데이터 모델
 │   └─ requirements.txt
 │
 ├─ frontend/
 │   ├─ index.html
 │   ├─ app.js
 │   └─ style.css
 │
 ├─ judge/
 │   ├─ Dockerfile
 │   ├─ judge.py        # 핵심 채점 로직 및 DB 다이렉트 업데이트 기능
 │   ├─ submission.py
 │   └─ problems/       # 문제별 테스트 케이스 (.in / .out)
 │
 ├─ k8s/
 │   ├─ postgres.yaml   # DB 배포 명세서
 │   ├─ redis.yaml      # Queue 배포 명세서
 │   ├─ backend.yaml    # Backend 배포 명세서
 │   └─ worker.yaml     # Worker 배포 명세서 (기본 2대 상주)
 │
 ├─ .gitignore
 └─ README.md
```

---

## 팀원 실행 빠른 시작

이 프로젝트는 Docker Desktop Kubernetes 환경에서 실행됩니다.

### 1. 저장소 Clone

```powershell
git clone <repository-url>
cd online-judge-k8s
```

---

### 2. Docker 이미지 빌드 및 K8s 전송

# 백엔드/워커용 이미지 빌드
docker build --no-cache -t online-judge/backend:v2.0 ./backend
docker save online-judge/backend:v2.0 > backend.tar
sudo k3s ctr images import backend.tar

# 채점기용 이미지 빌드
docker build --no-cache -t online-judge/judge:v2.0 ./judge
docker save online-judge/judge:v2.0 > judge.tar
sudo k3s ctr images import judge.tar

---

### 3. k8s 인프라 전체 배포

# DB, Redis, Backend, Worker 순차 배포
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/worker.yaml

kubectl get pods
# postgres(1), redis(1), backend(1), worker(2) 가 Running 상태여야 합니다.

---

### 4. 포트 포워딩 (로컬 통신용 터널링)
로컬 PC에서 K8s 내부의 Backend에 접근하기 위해 터널을 뚫어줍니다. (터미널 켜두기)

kubectl port-forward svc/online-judge-backend 8000:8000

### 5. 로컬에서 DB (PostgreSQL) 직접 확인하기 (DBeaver)
Kubernetes 내부에 배포된 DB 파드는 보안상 클러스터 외부(로컬 PC)에서 직접 접근할 수 없도록 격리되어 있습니다. 따라서 테이블에 쌓이는 실시간 채점 기록을 GUI 툴로 편하게 조회하려면 **포트 포워딩(Port-Forwarding)** 을 통해 임시 접속 터널을 뚫어주어야 합니다.

```powershell
kubectl port-forward svc/online-judge-db 5432:5432
```

vscode 내에서 terminal->port에서 5432번 추가

### 6. KEDA 오토스케일링 설치 및 적용

kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.14.0/keda-2.14.0.yaml

kubectl apply -f k8s/worker.yaml

kubectl apply -f k8s/keda.yaml

kubectl get pods -w

### GUI DB 툴 연결 설정값

Host: localhost
Port: 5432
Database: online_judge
Username: judge_user
Password: judge_pass

---

### 5. Frontend 실행

cd frontend
python -m http.server 5500

---


## 문제 및 테스트 케이스 구조

현재 Judge 컨테이너는 문제별로 여러 테스트 케이스를 지원합니다.

문제 데이터는 `judge/problems/` 아래에 위치합니다.

```text
judge/problems/
 ├─ sum/
 │   ├─ 1.in / 1.out
 │   ├─ 2.in / 2.out
 │   └─ 3.in / 3.out
 ├─ multiply/
 │   ├─ 1.in / 1.out
 │   ├─ 2.in / 2.out
 │   └─ 3.in / 3.out
 └─ max/
     ├─ 1.in / 1.out
     ├─ 2.in / 2.out
     └─ 3.in / 3.out
```

각 테스트 케이스는 같은 번호의 `.in` / `.out` 파일이 한 쌍입니다.

Judge는 모든 테스트 케이스를 순서대로 실행합니다. 모든 케이스를 통과해야 `Accepted`를 반환합니다.

---

## 현재 지원 문제

### 1. sum

문제 ID: `sum`

설명: 두 정수 A, B가 주어졌을 때 A + B를 출력한다.

테스트 케이스:

```text
1.in: 1 2      → 1.out: 3
2.in: 10 20    → 2.out: 30
3.in: -5 7     → 3.out: 2
```

Python 정답 코드:

```python
a, b = map(int, input().split())
print(a + b)
```

C++ 정답 코드:

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << "\n";
    return 0;
}
```

---

### 2. multiply

문제 ID: `multiply`

설명: 두 정수 A, B가 주어졌을 때 A * B를 출력한다.

테스트 케이스:

```text
1.in: 2 3      → 1.out: 6
2.in: 10 0     → 2.out: 0
3.in: -4 5     → 3.out: -20
```

Python 정답 코드:

```python
a, b = map(int, input().split())
print(a * b)
```

C++ 정답 코드:

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a * b << "\n";
    return 0;
}
```

---

### 3. max

문제 ID: `max`

설명: 두 정수 A, B가 주어졌을 때 더 큰 값을 출력한다.

테스트 케이스:

```text
1.in: 1 2      → 1.out: 2
2.in: 10 3     → 2.out: 10
3.in: -1 -5    → 3.out: -1
```

Python 정답 코드:

```python
a, b = map(int, input().split())
print(max(a, b))
```

C++ 정답 코드:

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << max(a, b) << "\n";
    return 0;
}
```

---

## 채점 결과 JSON

채점 결과 예시입니다.

```json
{
  "submission_id": "628532229250",
  "job_name": "judge-job-628532229250",
  "status": "Succeeded",
  "result": {
    "status": "Accepted",
    "stdout": "2\n",
    "stderr": "",
    "time_ms": 25,
    "problem_id": "sum",
    "language": "python",
    "passed_cases": 3,
    "total_cases": 3,
    "failed_case": null,
    "cases": [
      {
        "case": "1",
        "input": "1 2\n",
        "expected": "3\n",
        "output": "3\n",
        "status": "Accepted"
      },
      {
        "case": "2",
        "input": "10 20\n",
        "expected": "30\n",
        "output": "30\n",
        "status": "Accepted"
      },
      {
        "case": "3",
        "input": "-5 7\n",
        "expected": "2\n",
        "output": "2\n",
        "status": "Accepted"
      }
    ]
  }
}
```

### 주요 필드 설명

| 필드 | 의미 |
|---|---|
| submission_id | 제출 ID |
| job_name | Kubernetes Job 이름 |
| status | Kubernetes Job 상태 |
| result.status | 채점 결과 |
| result.stdout | 마지막으로 실행된 테스트 케이스의 표준 출력 |
| result.stderr | 에러 메시지 |
| result.time_ms | 전체 실행 시간 |
| result.problem_id | 제출한 문제 ID |
| result.language | 제출 언어 |
| result.passed_cases | 통과한 테스트 케이스 수 |
| result.total_cases | 전체 테스트 케이스 수 |
| result.failed_case | 실패한 테스트 케이스 번호 |
| result.cases | 테스트 케이스별 상세 결과 배열 |

`stdout`은 예제 입력의 출력이 아니라, 마지막으로 실행된 테스트 케이스의 출력일 수 있습니다.  
정확한 케이스별 결과는 `result.cases`를 기준으로 확인합니다.

---

## 판정 종류

| 판정 | 의미 |
|---|---|
| Accepted | 모든 테스트 케이스 통과 |
| Wrong Answer | 실행은 되었지만 출력이 정답과 다름 |
| Runtime Error | 실행 중 에러 발생 |
| Time Limit Exceeded | 제한 시간 초과 |
| Compilation Error | C++ 컴파일 실패 |
| Judge Error | Judge 내부 오류 |

---

## 테스트 코드

### Python Accepted

```python
a, b = map(int, input().split())
print(a + b)
```

### Python Wrong Answer

```python
print(999)
```

### Python Runtime Error

```python
a = 1 / 0
print(a)
```

### Python Time Limit Exceeded

```python
while True:
    pass
```

### C++ Accepted

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << "\n";
    return 0;
}
```

### C++ Wrong Answer

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    cout << 999 << "\n";
    return 0;
}
```

---

## API 테스트

Backend와 Worker가 실행 중인 상태에서 PowerShell로 직접 API를 테스트할 수 있습니다.

### 제출

```powershell
$body = @{
    code = "a, b = map(int, input().split())`nprint(a + b)"
    language = "python"
    problem_id = "sum"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/submit" -Method POST -ContentType "application/json" -Body $body
```

정상 응답 예시:

```json
{
  "submission_id": "abc123def456",
  "job_name": "judge-job-abc123def456",
  "status": "Queued"
}
```

### 결과 조회

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/result/abc123def456"
```

상태 흐름:

```text
Queued   → Worker가 아직 처리하기 전
Running  → Kubernetes Job 실행 중
Succeeded / Failed → 채점 완료
```

---


## 새 문제 추가 방법 (v2.0 기준)

새 문제를 추가하려면 `judge/problems/` 폴더 내부에 문제 ID 이름으로 폴더를 생성하고, 프론트엔드 UI에 문제 정보를 추가한 뒤 채점기 이미지를 갱신해야 합니다.

### 1. 테스트 케이스 추가
`judge/problems/` 아래에 문제 ID(예: `min`)로 폴더를 만들고 `.in` / `.out` 파일 쌍을 넣습니다.

```text
judge/problems/min/
 ├─ 1.in / 1.out
 ├─ 2.in / 2.out
 └─ 3.in / 3.out

```

### 2. 프론트엔드 UI 업데이트 (frontend/index.html)

<option value="min">Min</option>


### 3. 프론트엔드 문제 데이터 추가 (frontend/app.js)

problems 변수(객체)에 새 문제의 설명과 예제, 언어별 기본 제공 코드를 추가합니다.

min: {
  title: "문제: Min",
  description: "입력으로 두 정수 A, B가 주어진다. 두 수 중 더 작은 값을 출력하라.",
  sampleInput: "1 2",
  sampleOutput: "1",
  pythonAccepted: `a, b = map(int, input().split())\nprint(min(a, b))`,
  cppAccepted: `#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    int a, b;\n    cin >> a >> b;\n    cout << min(a, b) << "\\n";\n    return 0;\n}`
}
---

### 4. 채점기(Judge) 이미지 재빌드 및 클러스터 적용

새로운 문제가 포함된 채점기 이미지를 다시 빌드하고 K3s 클러스터 내부에 덮어씌웁니다.

docker build --no-cache -t online-judge/judge:v2.0 ./judge
docker save online-judge/judge:v2.0 > judge.tar
sudo k3s ctr images import judge.tar

## 자주 발생한 오류와 해결법

### 1. ErrImageNeverPull

증상:

```text
ErrImageNeverPull
```

원인: Kubernetes Job이 사용할 Docker 이미지를 로컬에서 찾지 못한 경우입니다.

해결:

```powershell
docker build --no-cache -t online-judge/judge:v4 ./judge
```

`backend/k8s_job.py`와 `k8s/judge-job-test.yaml`의 이미지 이름이 `online-judge/judge:v4`인지 확인합니다.

---

### 2. Worker가 처리를 안 함

증상:

```text
/result 응답이 계속 status: Queued
```

원인: Worker가 실행 중이 아닌 경우입니다.

해결:

```powershell
cd backend
.venv\Scripts\activate
python worker.py
```

---

### 3. Redis 연결 실패

증상:

```text
Failed to enqueue submission: Connection refused
```

원인: Redis 컨테이너가 실행 중이 아닌 경우입니다.

해결:

```powershell
docker start online-judge-redis
```

컨테이너가 없다면:

```powershell
docker run -d --name online-judge-redis -p 6379:6379 redis:7
```

---

### 4. ContainerCreating 상태에서 로그 확인 에러

증상:

```text
container "judge" in pod is waiting to start: ContainerCreating
```

원인: Pod가 아직 시작 중인데 너무 빨리 로그를 확인한 경우입니다.

해결:

```powershell
kubectl get pods
kubectl logs job/<job-name>
```

---

### 5. Kubernetes API 연결 실패

증상:

```text
Unable to connect to the server
```

원인: Docker Desktop Kubernetes가 실행 중이 아니거나 context가 다른 경우입니다.

해결:

```powershell
kubectl config use-context docker-desktop
kubectl get nodes
```

---

### 6. 테스트 케이스 입력 첫 글자 오류

증상:

```text
ValueError: invalid literal for int() with base 10: '﻿1'
```

원인: Windows PowerShell에서 만든 파일에 BOM 문자가 들어간 경우입니다.

해결: `judge.py`에서 테스트 케이스 파일을 `utf-8-sig`로 읽도록 처리했습니다.

---

### 7. 프론트 화면이 수정 전 상태로 보임

증상:

```text
Raw JSON에는 cases가 있는데 테스트 케이스 카드가 보이지 않음
```

원인: 브라우저가 이전 `app.js`를 캐시한 경우입니다.

해결:

```text
Ctrl + F5
```

또는 브라우저 캐시를 비운 뒤 다시 접속합니다.
---


### 🛡️ 신뢰성(Reliability) 강화: At-Least-Once Delivery 보장
**문제점:** 기존 Redis `BLPOP` 방식은 Worker가 큐에서 데이터를 가져가는 즉시 데이터가 삭제되어, K8s Job을 생성하기 직전 Worker가 다운(OOM 등)될 경우 채점 요청이 영구 유실되는 Ghost Job 문제가 있었습니다.

**해결 방안:** 데이터 소실을 원천 차단하기 위해 작업 큐를 **Redis Streams** 기반의 컨슈머 그룹(Consumer Group) 모델로 업그레이드했습니다. 
* Worker는 스트림에서 작업을 읽되(`XREADGROUP`), Kubernetes에 Judge 파드를 성공적으로 배포한 것을 확인한 직후에만 처리 완료 승인(`XACK`)을 보냅니다.
* 만약 `XACK`를 보내기 전 Worker 노드가 죽더라도 데이터는 스트림에 안전하게 남아 있으며, 다른 Worker가 이를 인지하고 작업을 재개할 수 있는 **최소 1회 전송 보장(At-Least-Once Delivery)** 메커니즘을 완성했습니다.

### Redis Stream 메모리 누수(Memory Leak) 방지 (MAXLEN)
**도입 배경:** 작업 유실 방지를 위해 도입한 Redis Streams는 기본적으로 '로그 기반(Log-based)' 아키텍처이기 때문에, Consumer(Worker)가 작업 완료 후 `XACK`(확인 응답)를 보내더라도 데이터는 스트림 장부에 계속 남아있습니다. 만약 트래픽이 몰려 작업 건수가 수십만 개를 넘어가면 Redis 파드의 메모리가 팽창(OOM)하여 전체 시스템이 다운될 위험이 큽니다.

**개선 사항 (MAXLEN=10000 적용):**
* 백엔드가 Redis 큐에 작업을 넣을 때(`XADD`), 스트림의 최대 길이를 제한하는 `maxlen` 옵션을 추가했습니다.
* `maxlen=10000, approximate=True` 설정을 통해, Redis가 성능에 무리를 주지 않는 선에서 오래된 데이터를 알아서 잘라내도록 최적화했습니다.
* 이를 통해 트래픽이 아무리 폭주해도 Redis 큐는 항상 가장 최근에 들어온 1만 개의 작업만 유지하며, 서버 리소스를 극도로 효율적으로 관리할 수 있는 견고한 데이터 파이프라인을 구축했습니다.

### 5. 데이터 영속성 (Data Persistence) 보장
**도입 배경:** Kubernetes의 Pod는 휘발성(Ephemeral)을 가지므로, PostgreSQL 파드가 재시작되거나 노드에서 퇴출(Eviction)될 경우 내부 컨테이너에 저장된 모든 채점 기록 데이터가 초기화되는 치명적인 문제가 발생했습니다.

**개선 사항 (Persistent Volume 적용):**
* PostgreSQL Deployment에 `PersistentVolumeClaim(PVC)`을 도입하여 데이터베이스 스토리지를 컨테이너 생명주기와 완벽하게 분리했습니다.
* DB 파드가 생성될 때 K8s 클러스터의 영구 볼륨을 `/var/lib/postgresql/data` 경로에 마운트하도록 아키텍처를 수정했습니다.
* 이를 통해 DB 파드가 예기치 않게 종료되거나 클러스터를 재부팅하더라도 사용자 제출 데이터와 채점 결과가 영구적으로 보존되는 Stateless 인프라 위의 Stateful 데이터 환경을 구축했습니다.

### PVC 용량 늘리기 (수정 방법)

# postgres.yaml 
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      # storage: 1Gi  <- 기존 1GB
      storage: 5Gi   # <- 5GB로 늘려줍니다

# Command
kubectl delete pvc postgres-pvc

kubectl apply -f k8s/postgres.yaml