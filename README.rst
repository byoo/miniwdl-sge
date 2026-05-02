miniwdl-sge
=============

Extends miniwdl to run workflows on SGE clusters in singularity containers.

This SGE backend is based on the `miniwdl-slurm <https://github.com/miniwdl-ext/miniwdl-slurm>`_ backend. The codebase for this plugin originally started from miniwdl-slurm and was adapted for SGE. It executes tasks by creating a job script that is submitted to an SGE cluster. In case the job is aborted, the job will be cancelled on the SGE cluster.

Installation
------------

.. code-block:: bash

    pip install .

Usage
-----

A ``miniwdl.cfg`` configuration file (can be placed in the current working directory) example can be used to use miniwdl on an SGE cluster:

.. code-block:: ini

    [scheduler]
    container_backend=sge_singularity
    # task_concurrency defaults to the number of processors on the system.
    # since we submit the jobs to SGE this is not necessary.
    # higher numbers means miniwdl has to monitor more processes simultaneously
    # which might impact performance.
    task_concurrency=200
    
    # This setting allows running tasks to continue, even if one other tasks fails. 
    # Useful in combination with call caching. Prevents wasting resources by
    # cancelling jobs half-way that would probably succeed.
    fail_fast = false

    [call_cache]
    # The following settings create a call cache under the current directory.
    # This prevents wasting unnecessary resources on the cluster by rerunning 
    # jobs that have already succeeded.
    put = true 
    get = true 
    dir = "$PWD/miniwdl_call_cache"

    [task_runtime]
    # Setting a 'maxRetries' default allows jobs that fail due to intermittent
    # errors on the cluster to be retried.
    defaults = {
            "maxRetries": 2,
            "docker": "ubuntu:20.04"
        }
 
    [singularity]
    # This plugin wraps the singularity backend. Make sure the settings are
    # appropriate for your cluster.
    exe = ["singularity"]

    # the miniwdl default options contain options to run as a fake root, which
    # is not available on most clusters. So the run options do need to be
    # overriden.
    # --containall: isolates container environment, does not mount home, and
    # isolates IPC and PID namespace.
    # --no-mount hostfs: Prohibit mounting of any host filesystems unless
    # explicitly mounted.
    # --network none: Do not allow any network traffic inside and outside
    # the container. This is a sane default for reproducible workflows.
    run_options = [
            "--containall",
            "--no-mount", "hostfs",
            "--network", "none"
        ]

    # Location of the singularity images (optional). The miniwdl-sge plugin
    # will set it to a directory inside $PWD. This location must be reachable
    # for the submit nodes.
    image_cache = "$PWD/miniwdl_singularity_cache"

    [sge]
    # Extra arguments to pass to the qsub command.
    extra_args="-j y"

Runtime Variables
-----------------

The following runtime variables are supported for adjusting SGE parameters:
- ``time_minutes``: Mapped to `-l h_rt=`
- ``sge_project``: Mapped to `-P <project>`
- ``sge_queue``: Mapped to `-q <queue>`
- ``sge_w``: Mapped to `-w <w>` (default: n)
- ``sge_pe``: Mapped to `-pe <pe_name> <cpu>` (default: make)
- ``sge_h_vmem``: Mapped to `-l h_vmem=<mem>` (memory reservation is used as fallback)
- ``cpu``: Mapped to the number of slots in `-pe`
- ``gpuCount``: Mapped to `-l gpu=<count>`

License
-------
MIT License.
