# Copyright (c) 2026 Byunggil Yoo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os
import shlex
import subprocess
import sys
from contextlib import ExitStack
from typing import Callable, Dict, List, Union

from WDL import Type, Value
from WDL.runtime import config
from WDL.runtime.backend.cli_subprocess import _SubprocessScheduler
from WDL.runtime.backend.singularity import SingularityContainer


class SGESingularity(SingularityContainer):
    @classmethod
    def global_init(cls, cfg: config.Loader, logger: logging.Logger) -> None:
        # Set resources to maxsize. The base class (_SubProcessScheduler)
        # looks at the resources of the current host, but since we are
        # dealing with a cluster these limits do not apply.
        cls._resource_limits = {
            "cpu": sys.maxsize,
            "mem_bytes": sys.maxsize,
            "time": sys.maxsize,
        }
        _SubprocessScheduler.global_init(cls._resource_limits)
        # Since we run on the cluster, the images need to be placed in a
        # shared directory. The singularity cache itself cannot be shared
        # across nodes, as it can become corrupted when nodes pull the same
        # image. The solution is to pull image to a shared directory on the
        # submit node. If no image_cache is given, simply place a folder in
        # the current working directory.
        if cfg.get("singularity", "image_cache") == "":
            cfg.override(
                {"singularity": {
                    "image_cache": os.path.join(os.getcwd(),
                                                "miniwdl_singularity_cache")
                }}
            )
        SingularityContainer.global_init(cfg, logger)

    @classmethod
    def detect_resource_limits(cls, cfg: config.Loader,
                               logger: logging.Logger) -> Dict[str, int]:
        return cls._resource_limits  # type: ignore

    @property
    def cli_name(self) -> str:
        return "sge_singularity"

    def process_runtime(self,
                        logger: logging.Logger,
                        runtime_eval: Dict[str, Value.Base]) -> None:
        """Any non-default runtime variables can be parsed here"""
        super().process_runtime(logger, runtime_eval)
        if "time_minutes" in runtime_eval:
            time_minutes = runtime_eval["time_minutes"].coerce(Type.Int()).value
            self.runtime_values["time_minutes"] = time_minutes

        if "sge_project" in runtime_eval:
            sge_project = runtime_eval["sge_project"].coerce(
                Type.String()).value
            self.runtime_values["sge_project"] = sge_project

        if "sge_queue" in runtime_eval:
            sge_queue = runtime_eval["sge_queue"].coerce(
                Type.String()).value
            self.runtime_values["sge_queue"] = sge_queue

        if "sge_pe" in runtime_eval:
            sge_pe = runtime_eval["sge_pe"].coerce(
                Type.String()).value
            self.runtime_values["sge_pe"] = sge_pe
            
        if "sge_h_vmem" in runtime_eval:
            sge_h_vmem = runtime_eval["sge_h_vmem"].coerce(
                Type.String()).value
            self.runtime_values["sge_h_vmem"] = sge_h_vmem

        if "gpuCount" in runtime_eval:
            gpuCount = max(1, runtime_eval["gpuCount"].coerce(Type.Int()).value)
            self.runtime_values["gpuCount"] = gpuCount

        if "sge_w" in runtime_eval:
            sge_w = runtime_eval["sge_w"].coerce(
                Type.String()).value
            self.runtime_values["sge_w"] = sge_w

    def _sge_invocation(self):
        # We use qsub -sync y as this makes the submitted job behave like a
        # local job.
        # -terse gives informative stdout consisting only of the job ID.
        qsub_args = [
            "qsub",
            "-sync", "y",
            "-terse",  # Make job ID parsing easier.
            "-N", self.run_id,
            "-V", # Pass environment variables
            "-cwd", # Execute job from current working directory
        ]

        gpuCount = self.runtime_values.get("gpuCount", None)
        if gpuCount is not None:
            # Different clusters use different GPU specifications.
            # Default is "-l gpu={gpuCount}", but can be overridden or set to "none" to take no action.
            gpu_fmt = "-l gpu={gpuCount}"
            if self.cfg.has_section("sge"):
                gpu_fmt = self.cfg.get("sge", "gpu_resource_format", gpu_fmt).strip()
            if gpu_fmt.lower() not in ("", "none", "off", "false"):
                formatted = gpu_fmt.format(gpuCount=gpuCount)
                qsub_args.extend(shlex.split(formatted))

        project = self.runtime_values.get("sge_project", None)
        if project is not None:
            qsub_args.extend(["-P", project])

        queue = self.runtime_values.get("sge_queue", None)
        if queue is not None:
            qsub_args.extend(["-q", queue])

        sge_w = self.runtime_values.get("sge_w", "n")
        if sge_w:
            qsub_args.extend(["-w", sge_w])

        cpu = self.runtime_values.get("cpu", None)
        sge_pe = self.runtime_values.get("sge_pe", "make")
        if cpu is not None and cpu > 1:
            qsub_args.extend(["-pe", sge_pe, str(cpu)])

        memory = self.runtime_values.get("memory_reservation", None)
        sge_h_vmem = self.runtime_values.get("sge_h_vmem", None)
        if sge_h_vmem is not None:
            qsub_args.extend(["-l", f"h_vmem={sge_h_vmem}"])
        elif memory is not None:
            # Apptainer container runtime overhead requires ~2GB virtual memory address space.
            # Enforce a minimum h_vmem of 4096M so small tasks are not killed by SGE.
            mem_mb = max(4096, round(memory / (1024 ** 2)))
            qsub_args.extend(["-l", f"h_vmem={mem_mb}M"])

        time_minutes = self.runtime_values.get("time_minutes", None)
        if time_minutes is not None:
            qsub_args.extend(["-l", f"h_rt={time_minutes * 60}"])

        if self.cfg.has_section("sge"):
            extra_args = self.cfg.get("sge", "extra_args", "")
            if extra_args:
                qsub_args.extend(shlex.split(extra_args))

            # Optional: dynamic configuration based on run variables could go here
            # Similar to slurm's dynamic partition rule matching.
            pass

        wrapper_script = os.path.join(os.path.dirname(__file__), "scripts",
                                      "qsub_wrapper.py")
        return [sys.executable, wrapper_script] + qsub_args + ["--"]

    def _run_invocation(self, logger: logging.Logger, cleanup: ExitStack,
                        image: str) -> List[str]:
        singularity_command = super()._run_invocation(logger, cleanup, image)

        sge_invocation = self._sge_invocation()
        sge_invocation.extend(singularity_command)
        logger.info("SGE invocation: " + ' '.join(
            shlex.quote(part) for part in sge_invocation))
        return sge_invocation

    def _run(self,
             logger: logging.Logger,
             terminating: Callable[[], bool],
             command: str
             ) -> int:
        # Line copied from base class as value is not publicly exposed.
        cli_log_filename = os.path.join(self.host_dir, f"{self.cli_name}.log.txt")
        try:
            return super()._run(logger, terminating, command)
        finally:
            if terminating():  # Cancel the job if terminating
                with open(cli_log_filename, "rt") as submit_log:
                    # job ID is output with -terse
                    content = submit_log.read().strip()
                    # SGE -terse sometimes outputs the job ID directly, or with array ids
                    # The job ID should be the first dot-separated or space-separated token
                    job_id = content.split()[0].split('.')[0]
                if job_id.isdigit():  # A valid job ID.
                    qdel_args = ["qdel", job_id]
                    subprocess.run(qdel_args)
