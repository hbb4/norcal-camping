#!/bin/bash
# Logs the Central Sierra Snow Lab season data and checks for a new Dryad archive.
# The lab posts its 8 AM board reading by 9 AM PST on snow days; three runs a day
# cover a laptop that was asleep at 9:30. Crontab entry (crontab -e):
#   30 9,13,18 * * * /bin/bash /Users/bhimes/himesblakeblake/projects/camping/ski_resort_snow/scripts/cssl_cron.sh
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.." || exit 1
mkdir -p data/tuning/cssl
python3 cssl_sync.py >> data/tuning/cssl/sync.log 2>&1
