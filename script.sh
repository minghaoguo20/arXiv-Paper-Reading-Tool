# Remove all directories in tex/ (keep only .tar.gz files)
find tex -maxdepth 1 -type d ! -name "tex" -exec rm -rf {} +

# Translate all .tar.gz files
for f in tex/*.tar.gz; do
    echo "=========================================="
    echo "Processing: $f"
    echo "=========================================="
    python translate.py --input "$f" --model x
done
