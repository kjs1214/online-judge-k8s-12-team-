const API_BASE = "http://localhost:8000";

const problems = {
  sum: {
    title: "문제: A + B",
    description: "입력으로 두 정수 A, B가 주어진다. 두 수의 합을 출력하라.",
    sampleInput: "1 2",
    sampleOutput: "3",
    pythonAccepted: `a, b = map(int, input().split())
print(a + b)`,
    cppAccepted: `#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << "\\n";
    return 0;
}`
  },
  multiply: {
    title: "문제: A × B",
    description: "입력으로 두 정수 A, B가 주어진다. 두 수의 곱을 출력하라.",
    sampleInput: "2 3",
    sampleOutput: "6",
    pythonAccepted: `a, b = map(int, input().split())
print(a * b)`,
    cppAccepted: `#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a * b << "\\n";
    return 0;
}`
  },
  max: {
    title: "문제: Max",
    description: "입력으로 두 정수 A, B가 주어진다. 두 수 중 더 큰 값을 출력하라.",
    sampleInput: "1 2",
    sampleOutput: "2",
    pythonAccepted: `a, b = map(int, input().split())
print(max(a, b))`,
    cppAccepted: `#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << max(a, b) << "\\n";
    return 0;
}`
  }
};

window.onload = () => {
  onProblemChange();
  loadSample("accepted");
};

function getSelectedProblemId() {
  return document.getElementById("problem").value;
}

function getSelectedProblem() {
  return problems[getSelectedProblemId()];
}

function onProblemChange() {
  const problemId = getSelectedProblemId();
  const problem = getSelectedProblem();

  document.getElementById("problemTitle").textContent = problem.title;
  document.getElementById("problemDescription").textContent = problem.description;
  document.getElementById("problemIdLabel").textContent = `problem_id: ${problemId}`;
  document.getElementById("sampleInput").textContent = problem.sampleInput;
  document.getElementById("sampleOutput").textContent = problem.sampleOutput;

  clearResult();
  loadSample("accepted");
}

function loadSample(type) {
  const problem = getSelectedProblem();
  const languageSelect = document.getElementById("language");

  if (type === "accepted") {
    if (languageSelect.value === "cpp") {
      document.getElementById("code").value = problem.cppAccepted;
    } else {
      document.getElementById("code").value = problem.pythonAccepted;
    }
    return;
  }

  if (type === "wrong") {
    languageSelect.value = "python";
    document.getElementById("code").value = `print(999)`;
    return;
  }

  if (type === "runtime") {
    languageSelect.value = "python";
    document.getElementById("code").value = `a = 1 / 0
print(a)`;
    return;
  }

  if (type === "tle") {
    languageSelect.value = "python";
    document.getElementById("code").value = `while True:
    pass`;
  }
}

function setBadge(status) {
  const badge = document.getElementById("resultBadge");
  badge.textContent = status || "Unknown";

  badge.className = "badge";

  if (!status || status === "Idle") {
    badge.classList.add("idle");
  } else if (status === "Running" || status === "Submitted" || status === "Queued") {
    badge.classList.add("running");
  } else if (status === "Accepted") {
    badge.classList.add("accepted");
  } else if (status === "Wrong Answer") {
    badge.classList.add("wrong");
  } else {
    badge.classList.add("error");
  }
}

function setLoading(isLoading) {
  const btn = document.getElementById("submitBtn");
  const state = document.getElementById("submitState");

  btn.disabled = isLoading;
  btn.textContent = isLoading ? "채점 중..." : "제출";
  state.textContent = isLoading
    ? "Redis Queue → Worker → Kubernetes Job 실행 중"
    : "대기 중";

  if (isLoading) {
    setBadge("Running");
  }
}

function clearResult() {
  document.getElementById("summary").classList.add("hidden");
  document.getElementById("submissionId").textContent = "-";
  document.getElementById("jobName").textContent = "-";
  document.getElementById("resultLanguage").textContent = "-";
  document.getElementById("timeMs").textContent = "-";
  document.getElementById("caseResult").textContent = "-";
  document.getElementById("failedCase").textContent = "-";
  document.getElementById("stdoutBox").textContent = "-";
  document.getElementById("stderrBox").textContent = "-";
  document.getElementById("rawResult").textContent = "{}";
  document.getElementById("caseList").innerHTML =
    `<p class="muted">아직 채점 결과가 없습니다.</p>`;
  setBadge("Idle");
}

function renderResult(data) {
  const result = data.result || {};

  document.getElementById("summary").classList.remove("hidden");

  document.getElementById("submissionId").textContent = data.submission_id || "-";
  document.getElementById("jobName").textContent = data.job_name || "-";
  document.getElementById("resultLanguage").textContent = result.language || "-";
  document.getElementById("timeMs").textContent =
    result.time_ms !== undefined ? `${result.time_ms} ms` : "-";

  document.getElementById("caseResult").textContent =
    result.total_cases !== undefined
      ? `${result.passed_cases} / ${result.total_cases}`
      : "-";

  document.getElementById("failedCase").textContent =
    result.failed_case || "-";

  document.getElementById("stdoutBox").textContent = result.stdout || "-";
  document.getElementById("stderrBox").textContent = result.stderr || "-";
  document.getElementById("rawResult").textContent = JSON.stringify(data, null, 2);

  renderCases(result.cases || []);

  setBadge(result.status || data.status || "Unknown");
}

function renderCases(cases) {
  const caseList = document.getElementById("caseList");

  if (!caseList) {
    return;
  }

  if (!cases || cases.length === 0) {
    caseList.innerHTML = `<p class="muted">테스트 케이스 상세 결과가 없습니다.</p>`;
    return;
  }

  caseList.innerHTML = cases.map(item => {
    const statusClass =
      item.status === "Accepted"
        ? "accepted"
        : item.status === "Wrong Answer"
          ? "wrong"
          : "error";

    return `
      <div class="case-card">
        <div class="case-card-header">
          <strong>Case ${escapeHtml(item.case || "-")}</strong>
          <span class="case-status ${statusClass}">
            ${escapeHtml(item.status || "-")}
          </span>
        </div>

        <div class="case-grid">
          <div>
            <span>Input</span>
            <pre>${escapeHtml(item.input || "-")}</pre>
          </div>
          <div>
            <span>Expected</span>
            <pre>${escapeHtml(item.expected || "-")}</pre>
          </div>
          <div>
            <span>Output</span>
            <pre>${escapeHtml(item.output || "-")}</pre>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function submitCode() {
  const language = document.getElementById("language").value;
  const code = document.getElementById("code").value;
  const problemId = getSelectedProblemId();

  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        code,
        language,
        problem_id: problemId
      })
    });

    if (!response.ok) {
      throw new Error(`Submit failed: ${response.status}`);
    }

    const submitted = await response.json();
    const submissionId = submitted.submission_id;

    document.getElementById("rawResult").textContent =
      JSON.stringify(submitted, null, 2);
    setBadge(submitted.status || "Queued");

    let finalResult = null;

    for (let i = 0; i < 30; i++) {
      await sleep(1000);

      const resultResponse = await fetch(`${API_BASE}/result/${submissionId}`);
      const resultData = await resultResponse.json();

      document.getElementById("rawResult").textContent =
        JSON.stringify(resultData, null, 2);

      if (resultData.status === "Succeeded" || resultData.status === "Error") {
        finalResult = resultData;
        break;
      }
    }

    if (!finalResult) {
      throw new Error("Result polling timeout");
    }

    renderResult(finalResult);
  } catch (error) {
    setBadge("Error");
    document.getElementById("rawResult").textContent =
      `Error: ${error.message}`;
  } finally {
    setLoading(false);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}