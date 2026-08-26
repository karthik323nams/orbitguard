from app.database.db import init_db
from app.services.cache import refresh_group_from_omm
from app.services.celestrak import fetch_group_omm

init_db()
records = fetch_group_omm(group="active", max_objects=500)
written = refresh_group_from_omm(records, "active")
print(f"Fetched {len(records)} records; cached {written}.")
