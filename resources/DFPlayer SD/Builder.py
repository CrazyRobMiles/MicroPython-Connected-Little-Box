import os
import json
import shutil
import sys

# -------------------- CONFIG --------------------
SOURCE = r"C:\Users\robmi\OneDrive\2026 Year\Projects\Immy Alarm\audio\card"          # contains group folders
SD_ROOT = r"I:\\"                      # SD card root
FIRMWARE_DIR = r"firmware"             # project firmware folder

ORDER_FILE = r"tracks_source.json"     # generated from SOURCE
MANIFEST_NAME = "tracks.json"          # output consumed by Tracks on device

# Ordering rule when generating ORDER_FILE:
#   "name" = lexicographic filename order (recommended, stable)
#   "ctime" = creation time (unstable across copies; not recommended)
ORDER_RULE = "name"

MAX_FOLDERS = 99
MAX_FILES_PER_FOLDER = 255

# Remove existing numeric folders (01..NN) on SD before writing
CLEAN_SD_NUMERIC_FOLDERS = True

# If True, fail if ORDER_FILE exists but doesn't match SOURCE (extra/missing files)
STRICT_MATCH = False
# ------------------------------------------------


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def is_mp3(fn: str) -> bool:
    return fn.lower().endswith(".mp3")


def safe_rmtree(path: str):
    base = os.path.basename(path.rstrip("\\/"))
    if len(base) == 2 and base.isdigit():
        shutil.rmtree(path)
    else:
        raise RuntimeError(f"Refusing to delete non-numeric folder: {path}")


def clean_sd_numeric_folders(sd_root: str, max_folder: int):
    for n in range(1, max_folder + 1):
        folder = os.path.join(sd_root, f"{n:02d}")
        if os.path.isdir(folder):
            print(f"[CLEAN] Removing {folder}")
            safe_rmtree(folder)


def norm_key(s: str) -> str:
    return s.replace("\\", "/")


def list_groups(source_root: str):
    groups = [
        d for d in sorted(os.listdir(source_root))
        if os.path.isdir(os.path.join(source_root, d))
    ]
    return groups


def list_mp3s_in_group(group_dir: str, order_rule: str):
    files = [
        f for f in os.listdir(group_dir)
        if os.path.isfile(os.path.join(group_dir, f)) and is_mp3(f)
    ]

    if order_rule == "name":
        files.sort(key=lambda s: s.lower())
        return files

    if order_rule == "ctime":
        files.sort(key=lambda f: os.path.getctime(os.path.join(group_dir, f)))
        return files

    raise RuntimeError(f"Unknown ORDER_RULE: {order_rule}")


def generate_order_file(source_root: str, order_file: str, order_rule: str):
    if not os.path.isdir(source_root):
        raise RuntimeError(f"SOURCE not found: {source_root}")

    groups = list_groups(source_root)
    if not groups:
        raise RuntimeError(f"No group folders found under: {source_root}")

    if len(groups) > MAX_FOLDERS:
        raise RuntimeError(f"Too many groups ({len(groups)}). Max is {MAX_FOLDERS}.")

    data = {
        "version": 1,
        "order_rule": order_rule,
        "groups": {}
    }

    for g in groups:
        group_dir = os.path.join(source_root, g)
        mp3s = list_mp3s_in_group(group_dir, order_rule)

        if len(mp3s) > MAX_FILES_PER_FOLDER:
            raise RuntimeError(f"Group '{g}' has {len(mp3s)} files; max is {MAX_FILES_PER_FOLDER}.")

        # Detect duplicates ignoring case (Windows reality)
        seen = set()
        for fn in mp3s:
            base = fn.lower()
            if base in seen:
                raise RuntimeError(f"Duplicate filename differing only by case in '{g}': {fn}")
            seen.add(base)

        data["groups"][g] = mp3s

    with open(order_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[ORDER] Wrote {order_file} (groups={len(groups)})")
    return data


def load_order_file(order_file: str):
    with open(order_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = data.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise RuntimeError("ORDER_FILE must contain non-empty 'groups' object.")
    return data


def strict_check_order_matches_source(order_data, source_root: str):
    groups = order_data["groups"]

    # Check every group exists and every file exists; also optionally detect extras
    for g, files in groups.items():
        group_dir = os.path.join(source_root, g)
        if not os.path.isdir(group_dir):
            raise RuntimeError(f"ORDER_FILE group folder missing in SOURCE: {group_dir}")

        disk_files = {
            f for f in os.listdir(group_dir)
            if os.path.isfile(os.path.join(group_dir, f)) and is_mp3(f)
        }

        listed = set(files)
        missing = [f for f in files if f not in disk_files]
        extra = sorted(list(disk_files - listed))

        if missing:
            raise RuntimeError(f"ORDER_FILE lists missing files in '{g}': {missing}")
        if extra:
            raise RuntimeError(f"SOURCE contains mp3s not listed in ORDER_FILE for '{g}': {extra}")


def build_sd_and_manifest(order_data, source_root: str, sd_root: str, firmware_dir: str):
    groups = order_data["groups"]
    group_names = list(groups.keys())

    # folder numbers assigned in JSON insertion order (stable in Python 3.7+)
    folder_map = {g: i for i, g in enumerate(group_names, start=1)}

    if CLEAN_SD_NUMERIC_FOLDERS:
        clean_sd_numeric_folders(sd_root, len(group_names))

    manifest = {
        "version": 1,
        "folders": {},
        "tracks": {}
    }

    for g in group_names:
        folder_num = folder_map[g]
        src_dir = os.path.join(source_root, g)
        sd_dir = os.path.join(sd_root, f"{folder_num:02d}")
        ensure_dir(sd_dir)

        files = groups[g]
        if len(files) > MAX_FILES_PER_FOLDER:
            raise RuntimeError(f"Group '{g}' too large: {len(files)}")

        manifest["folders"][str(folder_num)] = {"name": g, "count": len(files)}

        for file_num, fn in enumerate(files, start=1):
            src_file = os.path.join(src_dir, fn)
            if not os.path.isfile(src_file):
                raise RuntimeError(f"Missing source file: {src_file}")

            dst_file = os.path.join(sd_dir, f"{file_num:03d}.mp3")
            print(f"[{g}] {fn} -> {folder_num:02d}/{file_num:03d}.mp3")
            shutil.copyfile(src_file, dst_file)

            key = norm_key(f"{g}/{os.path.splitext(fn)[0]}")
            if key in manifest["tracks"]:
                raise RuntimeError(f"Duplicate manifest key '{key}'")
            manifest["tracks"][key] = {"folder": folder_num, "file": file_num}

    # Write manifest to SD root
    sd_manifest_path = os.path.join(sd_root, MANIFEST_NAME)
    with open(sd_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[MANIFEST] Wrote SD: {sd_manifest_path}")

    # Write manifest to firmware dir (for device filesystem copy)
    ensure_dir(firmware_dir)
    fw_manifest_path = os.path.join(firmware_dir, MANIFEST_NAME)
    with open(fw_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[MANIFEST] Wrote firmware: {fw_manifest_path}")

    print(f"\nDone. Folders={len(group_names)} Tracks={len(manifest['tracks'])}")


def main():
    if not os.path.isdir(SOURCE):
        raise RuntimeError(f"SOURCE not found: {SOURCE}")
    if not os.path.isdir(SD_ROOT):
        raise RuntimeError(f"SD_ROOT not found/mounted: {SD_ROOT}")

    # Step 1: generate order file from SOURCE structure
    order_data = generate_order_file(SOURCE, ORDER_FILE, ORDER_RULE)

    # Step 2: optionally enforce that SOURCE and ORDER_FILE are in lockstep
    if STRICT_MATCH:
        strict_check_order_matches_source(order_data, SOURCE)

    # Step 3: build SD + tracks.json manifest from order file
    build_sd_and_manifest(order_data, SOURCE, SD_ROOT, FIRMWARE_DIR)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
