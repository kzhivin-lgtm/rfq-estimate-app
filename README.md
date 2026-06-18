# RFQ Estimate App

Fresh Streamlit app scaffold for Supabase-backed RFQ estimation.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Streamlit Cloud

Set secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
COMPANY_ID = "001"
```

## Core tables expected

- companies
- labor
- overhead_settings
- overhead_monthly
- materials
- work_drivers
- machining_point_rules
- machine_catalog
- company_machines
- works
- estimate_driver_quantities
