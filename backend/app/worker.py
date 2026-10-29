"""Worker 稳定命令入口；编排实现位于 runtime.worker。"""

from app.runtime.worker import (
    claim_next,
    finish_job,
    process_job,
    settle_interrupted,
    single_worker_lock,
    worker_loop,
)

__all__ = [
    "claim_next",
    "finish_job",
    "process_job",
    "settle_interrupted",
    "single_worker_lock",
    "worker_loop",
]

if __name__ == "__main__":
    worker_loop()
