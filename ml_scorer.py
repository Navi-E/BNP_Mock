import pandas as pd
import os

# Get the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dataset paths
ACCOUNTS_PATH = os.path.join(BASE_DIR, "dataset", "accounts.csv")
TRANSACTIONS_PATH = os.path.join(BASE_DIR, "dataset", "transactions.csv")

# Load datasets
accounts_df = pd.read_csv(ACCOUNTS_PATH)
transactions_df = pd.read_csv(TRANSACTIONS_PATH)

# Display basic information
print("Accounts Dataset:")
print(accounts_df)

print("\nTransactions Dataset:")
print(transactions_df)

print("\nAccounts shape:", accounts_df.shape)
print("Transactions shape:", transactions_df.shape)