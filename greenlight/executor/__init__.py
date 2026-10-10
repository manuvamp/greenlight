from .base import ExecResult, Executor, Sandbox


def get_executor(name: str = "docker", **kw) -> Executor:
    if name == "docker":
        from .docker import DockerExecutor
        return DockerExecutor(**kw)
    if name == "contree":
        from .contree import ContreeExecutor
        return ContreeExecutor(**kw)
    raise ValueError(f"unknown executor {name!r}")


__all__ = ["ExecResult", "Executor", "Sandbox", "get_executor"]
