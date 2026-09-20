import os

output_filename = "jarvis_pipeline_summary.txt"
ignore_folders = {".venv", "venv", ".git", "__pycache__", ".cursor", "node_modules", "build", "dist"}

print("🔍 Searching project folder for Python files...")

found_files = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ignore_folders]
    for file in files:
        if file.endswith(".py") and file != "export_files.py":
            found_files.append(os.path.join(root, file))

print(f"\n📦 Found {len(found_files)} Python file(s):")
for f in found_files:
    print(f"  • {f}")

with open(output_filename, "w", encoding="utf-8") as out:
    for filepath in found_files:
        out.write(f"\n==========================================\n")
        out.write(f"FILE: {filepath}\n")
        out.write(f"==========================================\n\n")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                out.write(f.read())
        except Exception as e:
            out.write(f"# Error reading file: {e}\n")

print(f"\n✅ SUCCESS: All file contents saved into '{output_filename}'!")