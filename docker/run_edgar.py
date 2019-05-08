import os
from openedgar.processes.edgar import download_filing_index_data, process_all_filing_index

year = os.getenv("EDGAR_YEAR")
quarter = os.getenv("EDGAR_QUARTER")
month = os.getenv("EDGAR_MONTH")
types = [t.upper().strip() for t in os.getenv("FORM_TYPES").split(",")]


# process_all_filing_index(year=year, quarter=quarter, month=month, form_type_list=["3.1","3.2","10.1"])
# process_all_filing_index(year=year, quarter=quarter, month=month, form_type_list=["10-k"])

# for i in range(1995,2019)
#     process_all_filing_index(year=i, form_type_list=types)

#£
# fix: openedgar.tasks: ERROR    Multiple Filing records found for s3_path=edgar/data/1096325/0001096325-15-000002.txt, skipping...
# fix: openedgar.tasks: ERROR    Unable to create filing documents for Filing id=30186, cik=1024725, form_type=8-K, date_filed=2015-02-02: 'ascii' codec can't encode character '\xa0' in position 20: ordinal not in range(128)
# Reduce log level
process_all_filing_index(year=year, form_type_list=types)

for i in range(1, 10):
    print("###############################################")
