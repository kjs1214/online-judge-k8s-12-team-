import os
import json
import redis
from kubernetes import client, config
from database import SessionLocal, Submission
from prometheus_client import start_http_server, Counter

try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

batch_v1 = client.BatchV1Api()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

STREAM_KEY = "submission_stream"
GROUP_NAME = "judge_group"
CONSUMER_NAME = os.getenv("HOSTNAME", "local-worker")

JOBS_PROCESSED = Counter('judge_worker_jobs_processed_total', 'Total number of jobs processed by worker')
JOBS_FAILED = Counter('judge_worker_jobs_failed_total', 'Total number of jobs that worker failed to create')

JUDGE_IMAGE = os.getenv("JUDGE_IMAGE", "online-judge/judge:v2.0")
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "10"))

def create_judge_job(submission_id, code, language, problem_id):
    db = SessionLocal()
    sub = db.query(Submission).filter(Submission.task_id == submission_id).first()
    if sub:
        sub.status = "Processing"
        db.commit()
    db.close()

    job_name = f"judge-job-{submission_id}"
    
    env_vars = [
        client.V1EnvVar(name="TASK_ID", value=submission_id),
        client.V1EnvVar(name="SUBMITTED_CODE", value=code),
        client.V1EnvVar(name="LANGUAGE", value=language),
        client.V1EnvVar(name="PROBLEM_ID", value=problem_id),
        client.V1EnvVar(name="POSTGRES_USER", value=os.getenv("POSTGRES_USER", "judge_user")),
        client.V1EnvVar(name="POSTGRES_PASSWORD", value=os.getenv("POSTGRES_PASSWORD", "judge_pass")),
        client.V1EnvVar(name="POSTGRES_HOST", value=os.getenv("POSTGRES_HOST", "online-judge-db")),
        client.V1EnvVar(name="POSTGRES_DB", value=os.getenv("POSTGRES_DB", "online_judge"))
    ]

    container = client.V1Container(
        name="judge",
        image=JUDGE_IMAGE,
        image_pull_policy="IfNotPresent",
        env=env_vars,
        command=["python", "judge.py"],

        resources=client.V1ResourceRequirements(
            limits={"cpu": "1", "memory": "256Mi"},        
            requests={"cpu": "100m", "memory": "64Mi"}     
        ),
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,               
            seccomp_profile=client.V1SeccompProfile(
                type="RuntimeDefault"                       
            )
        )
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "judge-job"}),
        spec=client.V1PodSpec(restart_policy="Never", containers=[container])
    )

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=template,
            backoff_limit=0,
            ttl_seconds_after_finished=JOB_TTL_SECONDS
        )
    )

    batch_v1.create_namespaced_job(body=job, namespace="default")

def main():
    start_http_server(8001)
    
    try:
        redis_client.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass
        
    print(f"Worker ({CONSUMER_NAME}) started. Metrics exposed on port 8001. Waiting for jobs in stream...")
    
    while True:
        messages = redis_client.xreadgroup(GROUP_NAME, CONSUMER_NAME, {STREAM_KEY: ">"}, count=1, block=5000)
        
        if messages:
            for stream, message_list in messages:
                for message_id, data in message_list:
                    submission_id = data.get("task_id")
                    code = data.get("code")
                    language = data.get("language", "python")
                    problem_id = data.get("problem_id", "sum")

                    print(f"Processing stream message {message_id} -> submission: {submission_id}")
                    try:
                        create_judge_job(submission_id, code, language, problem_id)
                        print(f"K8s Job created: judge-job-{submission_id}")
                        
                        redis_client.xack(STREAM_KEY, GROUP_NAME, message_id)
                        JOBS_PROCESSED.inc()
                    except Exception as exc:
                        print(f"Failed to create K8s Job for {submission_id}: {exc}")
                        JOBS_FAILED.inc()

if __name__ == "__main__":
    main()