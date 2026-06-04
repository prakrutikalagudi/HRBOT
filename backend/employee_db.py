# employee_db.py
import pandas as pd
import os

EMP_CSV = os.path.join("data", "employee.csv")

def load_employee():
    """Load employee data from CSV file."""
    if not os.path.exists(EMP_CSV):
        raise FileNotFoundError(f"{EMP_CSV} not found")
    
    # Read CSV and handle missing values
    df = pd.read_csv(EMP_CSV, dtype=str).fillna("")
    
    # Validate required columns
    required_columns = ["Employee_Id", "Name", "Email", "Position", "Department"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Warning: Missing columns in employee CSV: {missing_columns}")
    
    return df

# Load employee data once at module import
try:
    employee_df = load_employee()
    print(f"Loaded {len(employee_df)} employee records.")
except FileNotFoundError as e:
    print(f"Warning: {e}")
    employee_df = pd.DataFrame()  # Empty dataframe as fallback

def get_employee(emp_id: str):
    """Fetch employee record by ID."""
    if emp_id is None or employee_df.empty:
        return None
    
    # Convert emp_id to string for comparison
    emp_id_str = str(emp_id).strip()
    
    # Find matching employee
    row = employee_df[employee_df["Employee_Id"].astype(str).str.strip() == emp_id_str]
    if row.empty:
        return None
    
    return row.iloc[0].to_dict()

def format_emp(emp_id: str) -> str:
    """Format employee information for display."""
    rec = get_employee(emp_id)
    if rec is None:
        return ""
    
    # Fixed typos and formatting
    return (
        f"Name: {rec.get('Name', '')}\n"
        f"Email: {rec.get('Email', '')}\n"
        f"Position: {rec.get('Position', '')}\n"  # Fixed typo: "Psition"
        f"Department: {rec.get('Department', '')}\n"  # Fixed bracket
        f"Joining Date: {rec.get('Joining_Date', '')}\n"
        f"Paid Leaves: {rec.get('Paid_Leave', '')}\n"
        f"Sick Leaves: {rec.get('Sick_Leave', '')}\n"  # Fixed underscore
        f"Paid Leave Remaining: {rec.get('Remaining_PL', '')}\n"  # Fixed typo
        f"Sick Leave Remaining: {rec.get('Remaining_SL', '')}\n"
        f"Salary: {rec.get('Salary', '')}\n"
        f"Employee Status: {rec.get('Emp_Status', '')}\n"
    )

def get_all_employees():
    """Get all employee records."""
    if employee_df.empty:
        return []
    return employee_df.to_dict('records')

def search_employees(name_query: str = None, department: str = None):
    """Search employees by name or department."""
    if employee_df.empty:
        return []
    
    filtered_df = employee_df.copy()
    
    if name_query:
        filtered_df = filtered_df[
            filtered_df["Name"].str.contains(name_query, case=False, na=False)
        ]
    
    if department:
        filtered_df = filtered_df[
            filtered_df["Department"].str.contains(department, case=False, na=False)
        ]
    
    return filtered_df.to_dict('records')
