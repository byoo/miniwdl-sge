==========
Changelog
==========

version 0.2.0
----------------------------
+ Add support for customizable ``gpu_resource_format`` under ``[sge]`` section in ``miniwdl.cfg``.
+ Support setting ``gpu_resource_format = none`` (or ``off``/``false``/``""``) to disable taking action for ``gpuCount``.

version 0.1.0
----------------------------
Initial release with the following features:

+ Utilize miniwdl's singularity backend to create a singularity command that
  is then submitted using qsub.
+ Create a singularity image cache so singularity images are available on
  the cluster nodes.
+ Support for ``cpu``, ``memory`` and ``time_minutes`` runtime attributes.
