# AML Platform Backend

Backend for the Transaction Network Analysis / AML hackathon project.

## Responsibilities

- PostgreSQL database access
- FastAPI REST APIs
- Transaction network construction with NetworkX
- Feature extraction for the ML teammate
- Integration point for the Random Forest model
- Dashboard/account/transaction endpoints

## Database

Create a PostgreSQL database named `aml_platform`, then run:

```bash
psql -U postgres -d aml_platform -f database/init.sql
```

Copy `.env.example` to `.env` and set the PostgreSQL password.

## Run backend

From the `backend` directory:

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

Open the API documentation at:

`http://127.0.0.1:8000/docs`

## Random Forest integration

The backend does not implement a competing ML model.

When the ML teammate has trained the final Random Forest, place the model at:

`backend/random_forest_model.pkl`

Then update `DEFAULT_FEATURES` in `ml_scorer.py` so it exactly matches the model's training feature order.

The feature names and model output should be agreed between the backend and ML teammate before integration.
