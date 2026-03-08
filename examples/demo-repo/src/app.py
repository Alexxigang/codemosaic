API_BASE_URL = "https://internal.example.com/v1"
SUPPORT_EMAIL = "ops@internal.local"
SECRET_TOKEN = "super-secret-token"


def calculate_customer_revenue(customer_email: str, annual_contract_value: int) -> tuple[str, int]:
    return f"{customer_email}:{SECRET_TOKEN}", annual_contract_value * 12
