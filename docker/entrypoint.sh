#!/usr/bin/env bash
# Entrypoint of the frappe container. When the command is `bench start` (the default), it first
# brings the bench to a runnable state (code, Python environment, config, site, apps), then starts it.
# Every step checks before it acts: existing setup is reused, and lab_core's browser files are
# rebuilt only when they are missing or their sources changed.
# Any other command (for example `bash`) runs as is.
set -euo pipefail

if [ "${1:-}" != "bench" ] || [ "${2:-}" != "start" ]; then
	exec "$@"
fi

SITE_NAME="${SITE_NAME:-lab.localhost}"
log() { echo "[init] $*"; }
fail() { echo "[init] ERROR: $*" >&2; exit 1; }

[ -n "${MARIADB_ROOT_PASSWORD:-}" ] || fail "MARIADB_ROOT_PASSWORD is not set in docker/.env."
BENCH_DIR="$(pwd)"

# 0. The code. An empty bench folder gets Frappe, then ERPNext and CRM, at the branches of
#    docker/versions.env. The folder is shared with the host, so the code appears there too.
if ! grep -qx frappe sites/apps.txt 2>/dev/null; then
	[ ! -e apps/frappe ] || fail "apps/frappe exists but the bench is incomplete (an earlier download stopped half way). Remove the frappe-bench folder on the host and start again."
	log "downloading Frappe (${FRAPPE_BRANCH:?FRAPPE_BRANCH is not set}); this takes several minutes"
	(cd / && bench init --ignore-exist --no-backups --skip-redis-config-generation \
		--frappe-branch "$FRAPPE_BRANCH" --python python3 "$BENCH_DIR")
fi
for spec in "erpnext:${ERPNEXT_BRANCH:-}" "crm:${CRM_BRANCH:-}"; do
	app="${spec%%:*}" branch="${spec#*:}"
	if [ -n "$branch" ] && [ ! -d "apps/$app" ]; then
		log "downloading $app ($branch)"
		bench get-app --branch "$branch" "$app"
	fi
done

# 1. The container's own Python environment, and the Python packages of every app in apps.txt.
if [ ! -x env/bin/python ]; then
	log "creating the Python environment"
	bench setup env --python python3
fi
apps_now="$(sha256sum sites/apps.txt | cut -d' ' -f1)"
if [ "$(cat env/.lab-apps 2>/dev/null || true)" != "$apps_now" ]; then
	log "installing Python packages of the apps"
	bench setup requirements --python
	echo "$apps_now" >env/.lab-apps
fi

# 2. Point the bench at the compose services.
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
if [ -f Procfile ]; then sed -i '/^redis/d' Procfile; fi

# 3. The site. Create it when it is missing; recreate it when its folder is still there but its
#    database is gone (after `down -v`).
create_site() { # extra flags as arguments
	[ -n "${ADMIN_PASSWORD:-}" ] || fail "ADMIN_PASSWORD is not set in docker/.env (needed to create the site)."
	bench new-site "$SITE_NAME" \
		--db-root-password "$MARIADB_ROOT_PASSWORD" \
		--admin-password "$ADMIN_PASSWORD" \
		--mariadb-user-host-login-scope=% "$@"
	bench --site "$SITE_NAME" set-config developer_mode 1
}
if [ ! -f "sites/$SITE_NAME/site_config.json" ]; then
	log "creating site $SITE_NAME"
	create_site
else
	db_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["db_name"])' "sites/$SITE_NAME/site_config.json")"
	found="$(mariadb -h mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -N -e "SHOW DATABASES LIKE '$db_name'")" \
		|| fail "cannot reach MariaDB as root; check MARIADB_ROOT_PASSWORD in docker/.env."
	if [ -z "$found" ]; then
		log "site folder exists but its database is gone: recreating site $SITE_NAME"
		create_site --force
	fi
fi
bench use "$SITE_NAME"

# 3b. Lab settings of the site, applied on every start so an existing site gets them too.
#     allow_tests: without it `bench run-tests` refuses to run on the site.
if [ "${LAB_ALLOW_TESTS:-1}" = "1" ]; then
	bench --site "$SITE_NAME" set-config allow_tests true
fi

# 4. Install on the site every app of the bench that is not installed yet
#    (or only those named in INSTALL_APPS, space separated).
installed="$(bench --site "$SITE_NAME" list-apps | awk '{print $1}')"
wanted="${INSTALL_APPS:-$(grep -v '^frappe$' sites/apps.txt | grep -v '^[[:space:]]*$' || true)}"
for app in $wanted; do
	if ! grep -qx "$app" <<<"$installed"; then
		log "installing app $app on $SITE_NAME"
		bench --site "$SITE_NAME" install-app "$app"
	fi
done

# 5. Browser files of our app. bench is the build tool: `bench build --app lab_core` links the
#    app's public folder, bundles its Desk assets, and runs the app's own "build" script
#    (apps/lab_core/package.json), which builds the SPA with Vite. It runs only when the SPA was
#    never built, or a frontend source file is newer than the last build.
if [ -f apps/lab_core/package.json ]; then
	spa_src=apps/lab_core/frontend
	spa_built=apps/lab_core/lab_core/public/frontend/index.html
	if [ ! -f "$spa_built" ] \
		|| [ -n "$(find "$spa_src" -path "$spa_src/node_modules" -prune -o -type f -newer "$spa_built" -print -quit)" ]; then
		log "building lab_core browser files (never built, or frontend sources changed)"
		bench build --app lab_core
	fi
fi

log "bench is ready: starting"
if [ "${LAB_DEBUG:-0}" = "1" ]; then
	# Debug mode replaces `bench start`: only the web server runs, under the debugger.
	log "DEBUG MODE (LAB_DEBUG=1): web server only. No worker, scheduler, socketio or asset watcher, and no reload on Python edits."
	log "ensuring debugpy 1.8.22 is installed"
	uv pip install --quiet --python "$BENCH_DIR/env/bin/python" debugpy==1.8.22
	cd "$BENCH_DIR/sites"
	exec ../env/bin/python -m debugpy \
		--listen 0.0.0.0:5678 \
		-m frappe.utils.bench_helper \
		frappe --site "$SITE_NAME" serve --port 8000 --noreload
fi
exec "$@"
