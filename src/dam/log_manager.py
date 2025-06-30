#!/usr/bin/env python3
"""
Log Manager Module
로그 저장 및 관리 기능을 담당
"""

from datetime import datetime
from pathlib import Path
from typing import List

class LogManager:
    """로그 관리 클래스"""
    
    def __init__(self, log_file_path: Path):
        self.log_file_path = log_file_path
        
        # 로그 파일 디렉토리 생성
        self.log_file_path.parent.mkdir(exist_ok=True)
        
        # 로그 파일이 없으면 헤더 생성
        if not self.log_file_path.exists():
            self._create_log_file()
    
    def _create_log_file(self):
        """로그 파일 생성 및 헤더 추가"""
        try:
            with self.log_file_path.open("w", encoding="utf8") as f:
                f.write("# Action Log File\n")
                f.write("# Format: TIMESTAMP\\tDESCRIPTION\n")
                f.write("# Created: " + datetime.now().isoformat() + "\n")
                f.write("\n")
            print(f" 로그 파일 생성: {self.log_file_path}")
        except Exception as e:
            print(f" 로그 파일 생성 실패: {e}")
    
    def append_log(self, description: str) -> bool:
        """로그 항목 추가"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 파일에 추가
            with self.log_file_path.open("a", encoding="utf8") as f:
                f.write(f"{timestamp}\t{description}\n")
            
            return True
            
        except Exception as e:
            print(f" 로그 저장 실패: {e}")
            return False
    
    def read_recent_logs(self, count: int = 10) -> List[str]:
        """최근 로그 읽기"""
        try:
            if not self.log_file_path.exists():
                return []
            
            with self.log_file_path.open("r", encoding="utf8") as f:
                lines = f.readlines()
            
            # 주석이 아닌 라인만 필터링
            log_lines = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            
            # 최근 count개 반환
            return log_lines[-count:] if log_lines else []
            
        except Exception as e:
            print(f" 로그 읽기 실패: {e}")
            return []
    
    def clear_logs(self) -> bool:
        """로그 파일 초기화"""
        try:
            self._create_log_file()
            print(" 로그 파일 초기화 완료")
            return True
        except Exception as e:
            print(f" 로그 파일 초기화 실패: {e}")
            return False 