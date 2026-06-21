# backend/database.py
import os
import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# K8s 환경변수에서 DB 정보 가져오기
DB_USER = os.getenv("POSTGRES_USER", "judge_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "judge_pass")
DB_HOST = os.getenv("POSTGRES_HOST", "online-judge-db")
DB_NAME = os.getenv("POSTGRES_DB", "online_judge")

# PostgreSQL 연결 주소 생성
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# DB 엔진 및 세션 팩토리 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 제출 기록(Submission) 테이블 스키마 정의
class Submission(Base):
    __tablename__ = "submissions"

    task_id = Column(String, primary_key=True, index=True)
    code = Column(Text)
    status = Column(String, default="Queued") # 상태: Queued, Processing, Completed, Error
    result = Column(Text, nullable=True)      # 채점 결과(JSON) 저장용
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 실행 시 테이블이 없으면 자동 생성
Base.metadata.create_all(bind=engine)