#!/usr/bin/env bash
# 简易导入脚本：支持 neo4j-admin 全量导入和 cypher LOAD CSV 回退导入
# 用法示例：
#   ./scripts/import_neo4j.sh --db neo4j --mode admin
#   ./scripts/import_neo4j.sh --db graph --mode cypher --user neo4j

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
NEO4J_HOME_DEFAULT="${ROOT_DIR}/neo4j-community-5.26.18"
IMPORT_DIR_DEFAULT="${NEO4J_HOME_DEFAULT}/import"
DATA_DIR_DEFAULT="${NEO4J_HOME_DEFAULT}/data/databases"

DB_NAME="neo4j"
MODE="admin"          # admin | cypher
NEO4J_HOME="${NEO4J_HOME:-$NEO4J_HOME_DEFAULT}"
IMPORT_DIR="${IMPORT_DIR:-$IMPORT_DIR_DEFAULT}"
DATA_DIR="${DATA_DIR:-$DATA_DIR_DEFAULT}"
BACKUP_DIR="${ROOT_DIR}/backups"
USER="neo4j"
PASSWORD=""
OVERWRITE=true
VERBOSE=false

# Ensure JAVA_HOME is set (try project-local JDK as fallback)
if [[ -z "${JAVA_HOME:-}" ]]; then
  LOCAL_JDK="$ROOT_DIR/jdk-21.0.9"
  if [[ -d "$LOCAL_JDK" ]]; then
    export JAVA_HOME="$LOCAL_JDK"
    echo "[import_neo4j] JAVA_HOME not set; using default $JAVA_HOME"
  else
    echo "ERROR: JAVA_HOME is not set and no local JDK found at $LOCAL_JDK. Please set JAVA_HOME." >&2
    exit 1
  fi
fi


usage(){
  cat <<EOF
Usage: $0 [options]
Options:
  -d|--db NAME          target database name (default: neo4j)
  -m|--mode MODE        import mode: admin (full import) or cypher (LOAD CSV fallback)
  -n|--neo4j-home PATH  path to neo4j installation (defaults to $NEO4J_HOME_DEFAULT)
  -i|--import PATH      import directory (default: ${IMPORT_DIR})
  -u|--user USER        Neo4j username for cypher mode (default: neo4j)
  -p|--password PASS    Neo4j password for cypher mode (or set NEO4J_PASSWORD env var)
  --no-backup           don't create a backup of existing DB
  -v|--verbose          verbose output
  -h|--help             show this help
Example:
  $0 --db neo4j --mode admin
  $0 --db graph --mode cypher -u neo4j -p mypass
EOF
}

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--db) DB_NAME="$2"; shift 2;;
    -m|--mode) MODE="$2"; shift 2;;
    -n|--neo4j-home) NEO4J_HOME="$2"; shift 2;;
    -i|--import) IMPORT_DIR="$2"; shift 2;;
    -u|--user) USER="$2"; shift 2;;
    -p|--password) PASSWORD="$2"; shift 2;;
    --no-backup) BACKUP_DIR=""; shift 1;;
    -v|--verbose) VERBOSE=true; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$PASSWORD" && -n "${NEO4J_PASSWORD:-}" ]]; then
  PASSWORD="$NEO4J_PASSWORD"
fi

# helpers
log(){ echo "[import_neo4j] $*"; }
logv(){ $VERBOSE && echo "[import_neo4j] $*"; }

# validate paths
if [[ ! -d "$NEO4J_HOME" ]]; then
  echo "ERROR: NEO4J_HOME not found: $NEO4J_HOME" >&2; exit 1
fi
if [[ ! -d "$IMPORT_DIR" ]]; then
  echo "ERROR: import dir not found: $IMPORT_DIR" >&2; exit 1
fi

NEO4J_ADMIN="$NEO4J_HOME/bin/neo4j-admin"
NEO4J_BIN="$NEO4J_HOME/bin/neo4j"
CYPHER_SHELL="$NEO4J_HOME/bin/cypher-shell"

if [[ "$MODE" == "admin" ]]; then
  log "Using neo4j-admin full import mode"
  # ensure neo4j is stopped
  log "Stopping Neo4j (if running)..."
  "$NEO4J_BIN" stop || true

  # backup existing database
  if [[ -n "$BACKUP_DIR" ]]; then
    mkdir -p "$BACKUP_DIR"
    if [[ -d "$DATA_DIR/$DB_NAME" ]]; then
      TS=$(date +%Y%m%d%H%M%S)
      ARCHIVE="$BACKUP_DIR/${DB_NAME}-backup-$TS.tgz"
      log "Backing up existing database $DB_NAME to $ARCHIVE"
      tar -C "$DATA_DIR" -czf "$ARCHIVE" "$DB_NAME"
    else
      logv "No existing $DB_NAME database to backup"
    fi
  else
    logv "Skipping backup as requested"
  fi

  # remove destination
  if [[ -d "$DATA_DIR/$DB_NAME" ]]; then
    log "Removing existing database directory $DATA_DIR/$DB_NAME"
    rm -rf "$DATA_DIR/$DB_NAME"
  fi

  # build node/relationship args
  node_args=()
  rel_args=()
  shopt -s nullglob
  for f in "$IMPORT_DIR"/node_*.csv; do
    node_args+=("--nodes=$f")
  done
  for f in "$IMPORT_DIR"/rel_*.csv; do
    rel_args+=("--relationships=$f")
  done
  shopt -u nullglob

  if [[ ${#node_args[@]} -eq 0 ]]; then
    echo "No node CSV files found in $IMPORT_DIR" >&2; exit 1
  fi
  if [[ ${#rel_args[@]} -eq 0 ]]; then
    echo "No relationship CSV files found in $IMPORT_DIR" >&2; exit 1
  fi

  # run import
  cmd=("$NEO4J_ADMIN" database import full "${node_args[@]}" "${rel_args[@]}" --overwrite-destination=true "$DB_NAME")
  log "Running: ${cmd[*]}"
  if [[ "$VERBOSE" == "true" ]]; then
    "${cmd[@]}"
  else
    "${cmd[@]}" >/dev/null
  fi
  rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "neo4j-admin import failed with code $rc" >&2
    exit $rc
  fi

  log "Import completed successfully. Starting Neo4j..."
  "$NEO4J_BIN" start
  log "Neo4j started. Use Browser to connect and select DB: $DB_NAME"

elif [[ "$MODE" == "cypher" ]]; then
  log "Using cypher LOAD CSV mode"
  log "Starting Neo4j (if not running)..."
  "$NEO4J_BIN" start || true
  sleep 2
  if [[ -z "$PASSWORD" ]]; then
    read -s -p "Enter password for user $USER: " PASSWORD
    echo
  fi

  echo "// Generated LOAD CSV import" > /tmp/__import_load_csv.cypher
  echo "// Nodes" >> /tmp/__import_load_csv.cypher
  for f in "$IMPORT_DIR"/node_*.csv; do
    label=$(basename "$f" | sed -E 's/node_(.*)\.csv/\1/' )
    echo "LOAD CSV WITH HEADERS FROM 'file:///import/$(basename "$f")' AS row" >> /tmp/__import_load_csv.cypher
    echo "MERGE (n:$label {$(awk -F, 'NR==1{for(i=1;i<=NF;i++){if($i ~ /:ID/){id=i; split($i,a,":"); idname=a[1]; printf idname ": row." idname }} }' "$f")})" >> /tmp/__import_load_csv.cypher || true
    echo >> /tmp/__import_load_csv.cypher
  done
  echo >> /tmp/__import_load_csv.cypher
  echo "// Relationships" >> /tmp/__import_load_csv.cypher
  for f in "$IMPORT_DIR"/rel_*.csv; do
    echo "// importing $(basename "$f")" >> /tmp/__import_load_csv.cypher
    # simplistic: user can refine if necessary
    awk 'NR==1{print "LOAD CSV WITH HEADERS FROM \"file:///import/'$(basename "$f")'\" AS row"; header=$0; split(header,h,","); for(i in h){gsub(/\r/,"",h[i]); if(h[i] ~ /START_ID/){startcol=i} if(h[i] ~ /END_ID/){endcol=i}}} NR>1{print "MATCH (a {" h[startcol] ": row." h[startcol] ", }) MATCH (b {" h[endcol] ": row." h[endcol] "}) CREATE (a)-[r:`"$0"`]->(b)"}' "$f" >> /tmp/__import_load_csv.cypher || true
  done

  log "Executing cypher script via cypher-shell"
  cat /tmp/__import_load_csv.cypher | "$CYPHER_SHELL" -u "$USER" -p "$PASSWORD" --format plain
  log "Cypher import complete"
else
  echo "Unknown mode: $MODE" >&2; usage; exit 1
fi

log "Done."
