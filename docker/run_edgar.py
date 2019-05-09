import logging
import os
from openedgar.processes.edgar import download_filing_index_data, process_all_filing_index

year = os.getenv("EDGAR_YEAR")
quarter = os.getenv("EDGAR_QUARTER")
month = os.getenv("EDGAR_MONTH")
types = [t.upper().strip() for t in os.getenv("FORM_TYPES").split(",")]

if len(quarter) == 0:
    quarter = None
if len(month) == 0:
    month = None

print("Edgar analysis started")
print("Analysing year {} types {}".format(year, types))
process_all_filing_index(year=year, quarter=quarter, month=month, form_type_list=types)

for i in range(1, 10):
    print("###############################################")
