#!/usr/bin/env python3
import sys
import os
import shlex

def main():
    if "--" not in sys.argv:
        print("Error: '--' not found in arguments", file=sys.stderr)
        sys.exit(1)
        
    dash_index = sys.argv.index("--")
    qsub_args = sys.argv[1:dash_index]
    command_args = sys.argv[dash_index + 1:]

    # Extract any --bind host paths to ensure they exist on disk before Apptainer mounts them
    bind_dirs_to_create = []
    for i, arg in enumerate(command_args):
        if arg == "--bind" and i + 1 < len(command_args):
            bind_spec = command_args[i + 1]
            host_path = bind_spec.split(":")[0]
            bind_dirs_to_create.append(host_path)

    script_path = "sge_submit.sh"
    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("set -e\n")

        # Create any bind mount source directories that Python cleaned up prematurely
        for host_dir in bind_dirs_to_create:
            f.write(f"mkdir -p {shlex.quote(host_dir)}\n")

        # Properly quote all arguments to prevent SGE from breaking them
        quoted_command = " ".join(shlex.quote(arg) for arg in command_args)
        f.write(f"exec {quoted_command}\n")
        
    os.chmod(script_path, 0o755)
    
    # We submit the generated script file instead of running the binary directly
    final_qsub_cmd = qsub_args + [script_path]
    
    # Replace the current process with qsub
    os.execvp(final_qsub_cmd[0], final_qsub_cmd)

if __name__ == "__main__":
    main()
