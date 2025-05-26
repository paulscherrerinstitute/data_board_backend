#!/bin/sh
set -e

DB_NAME="databoard"
COLLECTION="dashboards"
MONGO_URI="mongodb://mongo:27017"

usage() {
    echo "Usage: $0 export|import [file] [--all]"
    exit 1
}

FILE=""
ALL_FLAG=""

# Parse args (ignoring order)
for arg in "$@"; do
    case "$arg" in
        export|import)
            ACTION="$arg"
            ;;
        --all)
            ALL_FLAG="--all"
            ;;
        --help|-h)
            usage
            ;;
        *)
            # If not action or flag, assume file (only first file)
            if [ -z "$FILE" ]; then
                FILE="$arg"
            fi
            ;;
    esac
done

[ -z "$ACTION" ] && usage

# If no file given, default to this
[ -z "$FILE" ] && FILE="./whitelisted_dashboards.json"

if [ "$ACTION" = "export" ]; then
    if [ "$ALL_FLAG" = "--all" ]; then
        FILTER='{}'
    else
        FILTER='{ "whitelisted": true }'
    fi

    echo "[*] Exporting dashboards to $FILE..."
    mongoexport --uri="$MONGO_URI/$DB_NAME" \
        --collection="$COLLECTION" \
        --query="$FILTER" \
        --out="$FILE" \
        --jsonArray
    echo "[+] Export complete."

elif [ "$ACTION" = "import" ]; then
    if [ ! -f "$FILE" ]; then
        echo "[!] File $FILE not found."
        exit 1
    fi
    echo "[*] Importing dashboards from $FILE..."
    mongoimport --uri="$MONGO_URI/$DB_NAME" \
        --collection="$COLLECTION" \
        --file="$FILE" \
        --jsonArray \
        --mode=upsert \
        --upsertFields="_id"
    echo "[+] Import complete."

else
    usage
fi
