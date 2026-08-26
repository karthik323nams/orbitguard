import pytest
from datetime import datetime, timezone

from app.main import get_object_profile, get_object_full_orbit
from app.database.db import connect, init_db
from app.models.orbital import OrbitalElements
from app.services.cache import refresh_group_from_omm


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM orbital_elements")
        conn.execute("DELETE FROM satellite_launch_metadata")
    yield


def test_satellite_profile_directly():
    # Insert a dummy record into cached elements
    element = OrbitalElements(
        name="TEST_SAT_1",
        catalog_number=12345,
        line1="1 12345U 20001A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 12345  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 12345,
        "OBJECT_NAME": "TEST_SAT_1",
        "OBJECT_ID": "2020-001A",  # COSPAR ID format: YYYY-NNNP
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
        "OBJECT_TYPE": "PAYLOAD",
    }
    refresh_group_from_omm([(element, None, fields)], group="tracked")

    data = get_object_profile(12345, group="tracked")

    # Identity
    assert data["identity"]["name"] == "TEST_SAT_1"
    assert data["identity"]["norad_id"] == 12345
    assert data["identity"]["cospar_id"] == "2020-001A"
    assert data["identity"]["object_type"] == "PAYLOAD"

    # Orbital State
    assert data["orbital_state"]["eccentricity"] == 0.0001
    assert data["orbital_state"]["inclination_deg"] == 51.64
    assert data["orbital_state"]["orbit_regime"] == "LEO"
    assert data["orbital_state"]["period_minutes"] is not None

    # Current position
    assert data["current_position"] is not None
    assert "lat_deg" in data["current_position"]
    assert "lon_deg" in data["current_position"]
    assert "alt_km" in data["current_position"]
    assert "velocity_km_s" in data["current_position"]

    # Launch metadata fallback
    assert data["launch_metadata"]["launch_year"] == 2020
    assert data["launch_metadata"]["launch_number"] == 1
    assert data["launch_metadata"]["piece"] == "A"
    assert data["launch_metadata"]["country"] is None

    # Tracking status
    assert data["tracking_status"]["data_mode"] == "LIVE"


def test_satellite_profile_with_real_satcat_integration(monkeypatch):
    # Mock the celestrak.fetch_satcat_by_catalog_number function
    def mock_fetch_satcat(catalog_number):
        return {
            "OBJECT_NAME": "ISS (ZARYA)",
            "OBJECT_ID": "1998-067A",
            "NORAD_CAT_ID": 25544,
            "OBJECT_TYPE": "PAY",
            "OPS_STATUS_CODE": "+",
            "OWNER": "US",
            "LAUNCH_DATE": "1998-11-20",
            "LAUNCH_SITE": "TYMSC",
            "DECAY_DATE": "",
            "PERIOD": 92.93,
            "INCLINATION": 51.63,
            "APOGEE": 423,
            "PERIGEE": 413,
            "RCS": 399.0524,
            "DATA_STATUS_CODE": "",
            "ORBIT_CENTER": "EA",
            "ORBIT_TYPE": "ORB"
        }

    monkeypatch.setattr("app.main.fetch_satcat_by_catalog_number", mock_fetch_satcat)

    # Insert a dummy record into cached elements for ISS
    element = OrbitalElements(
        name="ISS (ZARYA)",
        catalog_number=25544,
        line1="1 25544U 98067A   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 25544  51.6400 110.1000 0001000  40.2000  33.3000 15.50000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.5,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
        "OBJECT_TYPE": "PAYLOAD",
    }
    refresh_group_from_omm([(element, None, fields)], group="tracked")

    # Call profile endpoint (triggers mock API call and caches in DB)
    data = get_object_profile(25544, group="tracked")

    # Assert real metadata resolved from codes
    assert data["launch_metadata"]["country"] == "United States"
    assert data["launch_metadata"]["launch_date"] == "1998-11-20"
    assert data["launch_metadata"]["launch_site"] == "Baikonur Cosmodrome, Kazakhstan"

    # Make sure it's stored in database
    from app.database.db import get_launch_metadata
    db_record = get_launch_metadata(25544)
    assert db_record is not None
    assert db_record["owner_code"] == "US"
    assert db_record["owner_name"] == "United States"
    assert db_record["launch_site_code"] == "TYMSC"
    assert db_record["launch_site_name"] == "Baikonur Cosmodrome, Kazakhstan"


def test_satellite_full_orbit_directly():
    # Insert a dummy record
    element = OrbitalElements(
        name="TEST_SAT_2",
        catalog_number=67890,
        line1="1 67890U 21002B   26234.00000000  .00000000  00000-0  00000-0 0  9991",
        line2="2 67890  97.4000 110.1000 0002000  40.2000  33.3000 15.00000000  99999",
        epoch=datetime.now(timezone.utc),
    )
    fields = {
        "NORAD_CAT_ID": 67890,
        "OBJECT_NAME": "TEST_SAT_2",
        "OBJECT_ID": "2021-002B",
        "EPOCH": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "MEAN_MOTION": 15.0,  # 15 rev/day -> 96 min period
        "ECCENTRICITY": 0.0002,
        "INCLINATION": 97.4,
        "RA_OF_ASC_NODE": 110.1,
        "ARG_OF_PERICENTER": 40.2,
        "MEAN_ANOMALY": 33.3,
        "BSTAR": 0.0000001,
        "OBJECT_TYPE": "DEBRIS",
    }
    refresh_group_from_omm([(element, None, fields)], group="tracked")

    data = get_object_full_orbit(67890, group="tracked")

    assert data["catalog_number"] == 67890
    assert data["name"] == "TEST_SAT_2"
    assert data["orbital_period_minutes"] == 96.0
    assert len(data["points"]) > 0
    assert data["current_position"] is not None
    assert "lat_deg" in data["current_position"]
