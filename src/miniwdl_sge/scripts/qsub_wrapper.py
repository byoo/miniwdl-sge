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

    # Extract any --bind host paths to ensure they exist on disk appropriately
    bind_paths = []
    for i, arg in enumerate(command_args):
        if arg == "--bind" and i + 1 < len(command_args):
            bind_spec = command_args[i + 1]
            host_path = bind_spec.split(":")[0]
            bind_paths.append(host_path)

    script_path = "sge_submit.sh"
    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("set -e\n")

        # Ensure directories exist and files are created as regular files rather than directories
        for host_path in bind_paths:
            if "_singularity_tmpdir_" in host_path:
                f.write(f"mkdir -p {shlex.quote(host_path)}\n")
            elif not os.path.exists(host_path):
                _, ext = os.path.splitext(host_path)
                is_file = bool(ext) or os.path.basename(host_path) == "command"

                if is_file:
                    parent = os.path.dirname(host_path)
                    if parent:
                        f.write(f"mkdir -p {shlex.quote(parent)}\n")
                    f.write(f"touch {shlex.quote(host_path)}\n")
                else:
                    f.write(f"mkdir -p {shlex.quote(host_path)}\n")

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
