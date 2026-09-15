import os
import sys
import argparse

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from commons.global_constants import GlobalConstants

def split_large_file(input_file: str, output_dir: str = None, chunk_size: int = None):
    """
    Splits any large CSV/delimited file into smaller readable CSV chunks.
    """
    if not input_file or not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return

    chunk_size = chunk_size or GlobalConstants.DEFAULT_SPLIT_CHUNK_SIZE
    if not output_dir:
        parent_dir = os.path.dirname(os.path.abspath(input_file))
        output_dir = os.path.join(parent_dir, GlobalConstants.DEFAULT_SPLIT_DIR_NAME)

    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.basename(input_file)
    name, ext = os.path.splitext(file_name)

    print(f"🚀 Splitting file into CSV chunks: {input_file}")

    with open(input_file, "r", encoding="utf-8", errors="ignore") as infile:
        header = infile.readline()
        if not header:
            print("❌ Input file is empty!")
            return

        part_num = 1
        current_rows = 0

        def open_next_part(part: int):
            out_path = os.path.join(output_dir, f"{name}_part{part}{ext}")
            f = open(out_path, "w", encoding="utf-8", newline="")
            f.write(header)
            return f

        out_file = open_next_part(part_num)

        for line in infile:
            out_file.write(line)
            current_rows += 1

            if current_rows >= chunk_size:
                out_file.close()
                print(f"  ✅ Created CSV Chunk {part_num}: {name}_part{part_num}{ext} ({current_rows:,} rows)")
                part_num += 1
                current_rows = 0
                out_file = open_next_part(part_num)

        if out_file and not out_file.closed:
            out_file.close()
            if current_rows > 0:
                print(f"  ✅ Created CSV Chunk {part_num}: {name}_part{part_num}{ext} ({current_rows:,} rows)")

    print(f"🎉 Completed! CSV chunks saved to: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=str, required=True)
    parser.add_argument("-o", "--output", type=str, required=False)
    parser.add_argument("-c", "--chunk-size", type=int)
    args = parser.parse_args()

    split_large_file(input_file=args.input, output_dir=args.output, chunk_size=args.chunk_size)