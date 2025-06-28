from dataclasses import dataclass
from typing import List

@dataclass
class RoutePoint:
    name: str
    lat: float
    lon: float

# Define key routes/points to monitor in Bengaluru
MONITOR_POINTS = [
    # Major Roads and Junctions
    RoutePoint("MG Road", 12.9758, 77.6045),
    RoutePoint("Silk Board", 12.9177, 77.6226),
    RoutePoint("Hosur Road", 12.8999, 77.6207),
    RoutePoint("Outer Ring Road", 12.9667, 77.6833),
    RoutePoint("Airport Road", 13.0039, 77.6505),
    RoutePoint("Bellary Road", 13.0179, 77.6186),
    RoutePoint("Sarjapur Road", 12.8999, 77.6676),
    RoutePoint("Bannerghatta Road", 12.8878, 77.5970),
    RoutePoint("Kanakapura Road", 12.8914, 77.5620),
    RoutePoint("Mysore Road", 12.9773, 77.5669),
    
    # Tech Parks and Business Hubs
    RoutePoint("Manyata Tech Park", 13.0419, 77.6189),
    RoutePoint("Electronics City", 12.8456, 77.6603),
    RoutePoint("ITPL", 12.9912, 77.7311),
    RoutePoint("Ecospace", 12.9133, 77.6557),
    RoutePoint("Cessna Business Park", 12.9992, 77.6961),
    RoutePoint("Bagmane Tech Park", 12.9716, 77.6412),
    RoutePoint("RMZ Ecoworld", 12.8976, 77.6701),
    RoutePoint("Prestige Tech Park", 12.9992, 77.6961),
    
    # Residential Areas
    RoutePoint("Indiranagar", 12.9784, 77.6408),
    RoutePoint("Jayanagar", 12.9279, 77.5937),
    RoutePoint("JP Nagar", 12.8906, 77.5777),
    RoutePoint("HSR Layout", 12.9085, 77.6426),
    RoutePoint("Koramangala", 12.9352, 77.6245),
    RoutePoint("Whitefield", 12.9698, 77.7500),
    RoutePoint("Marathahalli", 12.9592, 77.6974),
    RoutePoint("Bellandur", 12.9259, 77.6696),
    RoutePoint("Yelahanka", 13.0825, 77.5785),
    RoutePoint("Hebbal", 13.0399, 77.5989),
    RoutePoint("BTM Layout", 12.9141, 77.6103),
    RoutePoint("Banashankari", 12.9259, 77.5485),
    RoutePoint("Malleshwaram", 13.0076, 77.5667),
    RoutePoint("Basavanagudi", 12.9423, 77.5665),
    
    # Shopping and Commercial Areas
    RoutePoint("Brigade Road", 12.9748, 77.6094),
    RoutePoint("Commercial Street", 12.9769, 77.6131),
    RoutePoint("Forum Mall", 12.9259, 77.6696),
    RoutePoint("Phoenix Marketcity", 12.9949, 77.6974),
    RoutePoint("Orion Mall", 13.0069, 77.5756),
    RoutePoint("UB City", 12.9716, 77.5946),
    
    # Educational Institutions
    RoutePoint("IISc Bangalore", 13.0219, 77.5671),
    RoutePoint("Christ University", 12.9245, 77.6021),
    RoutePoint("RV College", 12.9254, 77.4987),
    RoutePoint("PES University", 13.0102, 77.5524),
    RoutePoint("MS Ramaiah", 13.0405, 77.5505),
    
    # Transportation Hubs
    RoutePoint("Kempegowda Airport", 13.1986, 77.7066),
    RoutePoint("Majestic Bus Stand", 12.9774, 77.5665),
    RoutePoint("Yeshwantpur Railway", 13.0252, 77.5488),
    RoutePoint("KSR Railway Station", 12.9773, 77.5669),
    RoutePoint("Shantinagar TTMC", 12.9626, 77.5842),
    RoutePoint("Shivajinagar Bus Stand", 12.9811, 77.6008),
    
    # Major Hospitals
    RoutePoint("Manipal Hospital", 12.9424, 77.6646),
    RoutePoint("Apollo Hospital", 12.9724, 77.6407),
    RoutePoint("Narayana Health City", 12.8924, 77.5835),
    RoutePoint("Fortis Hospital", 12.9318, 77.6288),
    
    # Metro Stations
    RoutePoint("MG Road Metro", 12.9758, 77.6102),
    RoutePoint("Indiranagar Metro", 12.9784, 77.6408),
    RoutePoint("Byappanahalli Metro", 12.9917, 77.6382),
    RoutePoint("Majestic Metro", 12.9773, 77.5669),
    RoutePoint("Vijayanagar Metro", 12.9737, 77.5283),
    
    # Tourist Attractions
    RoutePoint("Lalbagh", 12.9507, 77.5848),
    RoutePoint("Cubbon Park", 12.9764, 77.5928),
    RoutePoint("Bangalore Palace", 13.0100, 77.5907),
    RoutePoint("ISKCON Temple", 13.0105, 77.5512),
    
    # Key Intersections
    RoutePoint("Hudson Circle", 12.9734, 77.5937),
    RoutePoint("Shivajinagar", 12.9811, 77.6008),
    RoutePoint("Domlur", 12.9616, 77.6398),
    RoutePoint("Tin Factory", 13.0194, 77.6860),
    RoutePoint("Hebbal Flyover", 13.0399, 77.5989),
    
    # Upcoming Areas
    RoutePoint("Sarjapur-ORR Junction", 12.8999, 77.6676),
    RoutePoint("Kengeri", 12.9063, 77.4817),
    RoutePoint("Yelahanka", 13.0825, 77.5785),
    RoutePoint("Electronic City Phase 2", 12.8383, 77.6745)
]

# Data collection settings
COLLECTION_INTERVAL = 5  # minutes between each data collection cycle
DATA_RETENTION_DAYS = 90  # days to keep data in the database

# API Settings
API_TIMEOUT = 10  # seconds to wait for API response
MAX_RETRIES = 3  # number of retries for failed API calls

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
