# Traffic Data Collection System Migration Guide

This guide explains how to migrate the traffic data collection system to a new machine while preserving all existing data.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for version control)

## Files to Transfer

1. **Core Files**:
   - `traffic_data.db` - SQLite database containing all collected data
   - `traffic_config.py` - Configuration settings
   - `traffic_collector.py` - Data collection script
   - `traffic_dashboard_main.py` - Dashboard application
   - `requirements.txt` - Python dependencies (if exists)

2. **Optional Files**:
   - `.env` - Environment variables (if used)
   - Any custom scripts or utilities

## Setup Instructions

### 1. Install Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt

# Or install them manually if requirements.txt doesn't exist
pip install streamlit pandas numpy plotly folium streamlit-folium requests python-dotenv
```

### 2. Database Migration

#### Option 1: Simple Copy (Recommended)
1. Copy the `traffic_data.db` file to the same directory on the new system
2. Ensure the application has write permissions to this file

#### Option 2: SQL Dump (Alternative)
```bash
# On source machine
sqlite3 traffic_data.db ".backup traffic_data_backup.db"

# Transfer the backup file to the new system and restore
sqlite3 traffic_data.db ".restore traffic_data_backup.db"
```

### 3. Configuration Updates

1. Review `traffic_config.py` for any system-specific paths or settings
2. Update API keys if needed (TomTom, Google Maps, etc.)
3. Verify monitor points in `MONITOR_POINTS` are still relevant

### 4. Test the System

```bash
# Start the data collector
python traffic_collector.py

# In a separate terminal, start the dashboard
streamlit run traffic_dashboard_main.py
```

## Verifying Data Integrity

1. Check the dashboard loads without errors
2. Verify historical data is visible
3. Confirm new data is being collected and stored

## Troubleshooting

- **Permission Issues**: Ensure the application has write access to the database file
- **Missing Dependencies**: Check all required Python packages are installed
- **API Keys**: Verify all external service API keys are valid
- **Database Location**: The application looks for `traffic_data.db` in the same directory by default

## Maintenance

- Regularly back up the database file
- Monitor disk space as the database grows
- Keep the Python environment updated

## Support

For assistance, please refer to the project documentation or contact the development team.
